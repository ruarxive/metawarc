"""Durable, authenticated batch-job surface for long-running exports.

Jobs are persisted as JSON files under ``<data_dir>/jobs/<id>.json``
and executed by an asyncio runner started from the FastAPI lifespan
handler. The MVP registers one job kind, ``export-records``, which
materialises a ``QueryService.iter_records`` query into a JSON, CSV,
or Parquet file.

The module exposes:

* :class:`JobStatus` and :class:`JobKind` — the documented enums
* :class:`Job` — the dataclass that is serialised to JSON
* :class:`JobStore` — atomic file-backed persistence
* :class:`JobRunner` — the asyncio background loop
* :func:`run_export_records` — the export-records handler

The runner is intentionally read-only with respect to source archives. It
opens a short-lived ``Workspace`` per job, mirroring the synchronous
query path, so jobs do not hold a long-lived DuckDB connection.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import heapq
import json
import logging
import math
import os
import stat
import tempfile
import time
import uuid
from collections.abc import Awaitable as TypingAwaitable
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from filelock import FileLock, Timeout

from .indexer import RECORD_SCHEMA
from .query import QueryService, RecordQuery
from .workspace import Workspace

LOGGER = logging.getLogger("metawarc.jobs")

EXPORT_FORMATS = ("json", "csv", "parquet")
EXPORT_DEFAULT_LIMIT = 1_000
EXPORT_HARD_LIMIT = 100_000
JOB_METRICS_DEFAULT_LIMIT = 1_000
JOB_METRICS_HARD_LIMIT = 10_000
JOB_CLEANUP_INTERVAL_SECONDS = 60.0

JobHandler = Callable[["Job", "JobContext"], TypingAwaitable[dict[str, Any]]]
F = TypeVar("F", bound=Callable[..., Any])


class JobStatus(str, Enum):
    """Documented job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)


class JobKind(str, Enum):
    """Registered ``JobKind`` values; the MVP ships one."""

    EXPORT_RECORDS = "export-records"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        return tuple(item.value for item in cls)


@dataclass
class JobContext:
    """Per-job resources assembled by the runner before the handler runs."""

    settings: Any
    store: JobStore


@dataclass
class Job:
    """One persisted batch-job. Serialised to JSON."""

    id: str
    kind: str
    status: str = JobStatus.PENDING.value
    input: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: str = ""
    started_at: str | None = None
    ended_at: str | None = None

    @classmethod
    def new(cls, kind: JobKind, input: dict[str, Any]) -> Job:
        from .workspace import utc_now

        return cls(
            id=f"job-{uuid.uuid4().hex}",
            kind=kind.value,
            status=JobStatus.PENDING.value,
            input=input,
            created_at=utc_now(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JobStore:
    """JSON-file backed job persistence."""

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.jobs_dir = self.data_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path:
        if not job_id or "/" in job_id or "\\" in job_id or job_id.startswith("."):
            raise ValueError(f"invalid job id: {job_id!r}")
        return self.jobs_dir / f"{job_id}.json"

    def job_directory(self, job_id: str) -> Path:
        self._path(job_id)  # Validate the id before using it as a directory name.
        out = self.jobs_dir / job_id
        out.mkdir(parents=True, exist_ok=True)
        return out

    def result_path(self, job: Job, suffix: str) -> Path:
        return self.job_directory(job.id) / f"result{suffix}"

    def resolve_result(self, job: Job) -> Path | None:
        """Resolve a regular result file without trusting persisted paths."""
        format_ = job.result.get("format")
        if format_ not in EXPORT_FORMATS:
            return None
        try:
            directory = self.job_directory(job.id).resolve(strict=True)
            candidate = self.result_path(job, f".{format_}")
            if candidate.is_symlink():
                return None
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(directory) or not resolved.is_file():
                return None
        except (OSError, RuntimeError, ValueError):
            return None
        return resolved

    def claim(self, job_id: str) -> FileLock:
        return FileLock(self.job_directory(job_id) / ".runner.lock")

    @staticmethod
    def _atomic_write(target: Path, payload: dict[str, Any], *, prefix: str) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=prefix, suffix=".json.tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            os.replace(tmp_name, target)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    def save(self, job: Job) -> None:
        self._atomic_write(self._path(job.id), job.to_dict(), prefix=".job-")

    def progress_path(self, job_id: str) -> Path:
        self._path(job_id)
        return self.jobs_dir / job_id / "progress.json"

    def load_progress(self, job_id: str) -> dict[str, Any] | None:
        path = self.progress_path(job_id)
        try:
            if path.is_symlink() or not path.is_file():
                return None
            with path.open("rb") as handle:
                raw = handle.read(65_537)
            if len(raw) > 65_536:
                return None
            payload = json.loads(raw)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        processed = payload.get("processed_rows")
        total = payload.get("total_rows")
        updated_at = payload.get("updated_at")
        if (
            type(processed) is not int
            or type(total) is not int
            or not isinstance(updated_at, str)
            or not updated_at
            or processed < 0
            or total < 0
            or processed > total
        ):
            return None
        try:
            parsed_updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            if parsed_updated.tzinfo is None or parsed_updated.utcoffset() is None:
                return None
        except (TypeError, ValueError, OverflowError):
            return None
        return {
            "processed_rows": processed,
            "total_rows": total,
            "updated_at": updated_at,
        }

    @staticmethod
    def _metric_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                return None
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None

    def _metric_candidate(
        self, path: Path
    ) -> tuple[datetime, str, str, datetime | None, datetime | None]:
        if path.is_symlink():
            raise ValueError("job candidate is a symlink")
        with path.open("rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("job candidate is not a regular file")
            raw = handle.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("job candidate exceeds the metrics read bound")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("job candidate is not an object")
        job_id = payload.get("id")
        if not isinstance(job_id, str) or job_id != path.stem:
            raise ValueError("job id does not match its path")
        self._path(job_id)
        if not isinstance(payload.get("kind"), str) or not payload["kind"]:
            raise ValueError("job kind is invalid")
        status = payload.get("status")
        if status not in JobStatus.values():
            raise ValueError("job status is invalid")
        created_at = self._metric_timestamp(payload.get("created_at"))
        if created_at is None:
            raise ValueError("job created_at is invalid")
        started_at = self._metric_timestamp(payload.get("started_at"))
        ended_at = self._metric_timestamp(payload.get("ended_at"))
        return created_at, job_id, status, started_at, ended_at

    def metrics(self, *, limit: int = JOB_METRICS_DEFAULT_LIMIT) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= JOB_METRICS_HARD_LIMIT:
            raise ValueError(f"limit must be between 1 and {JOB_METRICS_HARD_LIMIT}")
        selected: list[tuple[datetime, str, str, datetime | None, datetime | None]] = []
        total = 0
        invalid = 0
        for path in self.jobs_dir.glob("*.json"):
            try:
                candidate = self._metric_candidate(path)
            except FileNotFoundError:
                continue
            except (OSError, ValueError, TypeError):
                invalid += 1
                continue
            total += 1
            heapq.heappush(selected, candidate)
            if len(selected) > limit:
                heapq.heappop(selected)

        counts = dict.fromkeys(JobStatus.values(), 0)
        queue_samples = 0
        queue_total = 0.0
        queue_max: float | None = None
        execution_samples = 0
        execution_total = 0.0
        execution_max: float | None = None
        terminal = {
            JobStatus.SUCCEEDED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        }
        for created_at, _job_id, status, started_at, ended_at in sorted(
            selected, key=lambda item: (item[0], item[1]), reverse=True
        ):
            counts[status] += 1
            if started_at is not None:
                queue_seconds = (started_at - created_at).total_seconds()
                if queue_seconds >= 0:
                    queue_samples += 1
                    queue_total += queue_seconds
                    queue_max = (
                        queue_seconds if queue_max is None else max(queue_max, queue_seconds)
                    )
                if status in terminal and ended_at is not None:
                    execution_seconds = (ended_at - started_at).total_seconds()
                    if execution_seconds >= 0:
                        execution_samples += 1
                        execution_total += execution_seconds
                        execution_max = (
                            execution_seconds
                            if execution_max is None
                            else max(execution_max, execution_seconds)
                        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "limit": limit,
            "total": total,
            "included": len(selected),
            "truncated": len(selected) < total,
            "counts": counts,
            "invalid": invalid,
            "queue_wait_seconds": {
                "samples": queue_samples,
                "mean": queue_total / queue_samples if queue_samples else None,
                "max": queue_max,
            },
            "execution_seconds": {
                "samples": execution_samples,
                "mean": execution_total / execution_samples if execution_samples else None,
                "max": execution_max,
            },
        }

    def write_progress(self, job_id: str, processed_rows: int, total_rows: int) -> dict[str, Any]:
        if (
            type(processed_rows) is not int
            or type(total_rows) is not int
            or processed_rows < 0
            or total_rows < 0
            or processed_rows > total_rows
        ):
            raise ValueError("progress counts must satisfy 0 <= processed_rows <= total_rows")
        current = self.load_progress(job_id)
        if current is not None and (
            processed_rows < current["processed_rows"] or total_rows != current["total_rows"]
        ):
            raise ValueError("progress must be monotonic and retain its planned total")
        from .workspace import utc_now

        payload = {
            "processed_rows": processed_rows,
            "total_rows": total_rows,
            "updated_at": utc_now(),
        }
        self.job_directory(job_id)
        self._atomic_write(self.progress_path(job_id), payload, prefix=".progress-")
        return payload

    def prune(
        self,
        retention_days: float,
        apply: bool = False,
        now: datetime | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Preview or delete expired terminal jobs without trusting result paths."""
        try:
            retention = float(retention_days)
        except (TypeError, ValueError) as exc:
            raise ValueError("retention_days must be a finite non-negative number") from exc
        if not math.isfinite(retention) or retention < 0:
            raise ValueError("retention_days must be a finite non-negative number")
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be at least 1")
        current_time = now if now is not None else datetime.now(timezone.utc)
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        try:
            cutoff = current_time - timedelta(days=retention)
        except OverflowError as exc:
            raise ValueError("retention_days produces an invalid cutoff") from exc

        terminal = {
            JobStatus.SUCCEEDED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        }

        def read_job(path: Path) -> Job:
            if path.is_symlink():
                raise ValueError("job lifecycle path is a symlink")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("id") != path.stem:
                raise ValueError("job id does not match its lifecycle path")
            self._path(payload["id"])
            if not isinstance(payload.get("status"), str):
                raise ValueError("job status is invalid")
            return Job(
                id=payload["id"],
                kind=payload["kind"],
                status=payload["status"],
                input=payload.get("input") or {},
                result=payload.get("result") or {},
                error=payload.get("error"),
                created_at=payload.get("created_at") or "",
                started_at=payload.get("started_at"),
                ended_at=payload.get("ended_at"),
            )

        def ineligible_reason(job: Job) -> str | None:
            if job.status not in terminal:
                return "not_terminal"
            if not isinstance(job.ended_at, str) or not job.ended_at.strip():
                return "invalid_ended_at"
            try:
                ended_at = datetime.fromisoformat(job.ended_at.replace("Z", "+00:00"))
                if ended_at.tzinfo is None or ended_at.utcoffset() is None:
                    return "invalid_ended_at"
            except (TypeError, ValueError, OverflowError):
                return "invalid_ended_at"
            if ended_at >= cutoff:
                return "not_expired"
            return None

        def unlink_owned(path: Path) -> None:
            try:
                if path.is_symlink() or not path.is_dir():
                    path.unlink(missing_ok=True)
            except OSError:
                # Known artifacts may be absent, inaccessible, or directories;
                # never recursively remove an unexpected directory.
                pass

        candidates: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        eligible_count = 0
        for path in sorted(self.jobs_dir.glob("*.json")):
            job_id = path.stem
            try:
                job = read_job(path)
            except (OSError, ValueError, TypeError, KeyError):
                skipped.append({"job_id": job_id, "reason": "malformed"})
                continue
            reason = ineligible_reason(job)
            if reason is not None:
                skipped.append({"job_id": job.id, "reason": reason})
                continue
            eligible_count += 1
            if len(candidates) < limit:
                candidates.append(
                    {"job_id": job.id, "status": job.status, "ended_at": job.ended_at}
                )

        deleted: list[dict[str, Any]] = []
        if apply:
            for candidate in candidates:
                job_id = candidate["job_id"]
                main_path = self._path(job_id)
                directory = self.jobs_dir / job_id
                lock_path = directory / ".runner.lock"
                if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
                    skipped.append({"job_id": job_id, "reason": "unsafe_job_directory"})
                    continue
                if lock_path.is_symlink():
                    skipped.append({"job_id": job_id, "reason": "unsafe_lock"})
                    continue
                try:
                    claim = self.claim(job_id)
                    claim.acquire(timeout=0)
                except Timeout:
                    skipped.append({"job_id": job_id, "reason": "locked"})
                    continue
                except (OSError, ValueError):
                    skipped.append({"job_id": job_id, "reason": "claim_failed"})
                    continue
                try:
                    if directory.is_symlink() or main_path.is_symlink():
                        skipped.append({"job_id": job_id, "reason": "unsafe_path"})
                        continue
                    try:
                        fresh = read_job(main_path)
                    except (OSError, ValueError, TypeError, KeyError):
                        skipped.append({"job_id": job_id, "reason": "changed_or_malformed"})
                        continue
                    reason = ineligible_reason(fresh)
                    if reason is not None:
                        skipped.append({"job_id": job_id, "reason": reason})
                        continue
                    try:
                        main_path.unlink()
                    except FileNotFoundError:
                        skipped.append({"job_id": job_id, "reason": "missing"})
                        continue
                    except OSError:
                        skipped.append({"job_id": job_id, "reason": "delete_failed"})
                        continue
                    for name in (
                        "progress.json",
                        "result.json",
                        "result.csv",
                        "result.parquet",
                    ):
                        unlink_owned(directory / name)
                    with contextlib.suppress(OSError):
                        for staged in directory.glob(".result-*.tmp"):
                            unlink_owned(staged)
                    with contextlib.suppress(OSError):
                        for staged in directory.glob(".progress-*.json.tmp"):
                            unlink_owned(staged)
                    deleted.append({"job_id": job_id})
                finally:
                    with contextlib.suppress(OSError, RuntimeError):
                        claim.release()
                    with contextlib.suppress(OSError):
                        lock_path.unlink()
                    with contextlib.suppress(OSError):
                        directory.rmdir()

        return {
            "dry_run": not apply,
            "retention_days": retention,
            "cutoff": cutoff.isoformat(),
            "candidates": candidates,
            "deleted": deleted,
            "skipped": skipped,
            "remaining": max(eligible_count - len(candidates), 0),
        }

    def load(self, job_id: str) -> Job | None:
        path = self._path(job_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return Job(
            id=payload["id"],
            kind=payload["kind"],
            status=payload["status"],
            input=payload.get("input") or {},
            result=payload.get("result") or {},
            error=payload.get("error"),
            created_at=payload.get("created_at") or "",
            started_at=payload.get("started_at"),
            ended_at=payload.get("ended_at"),
        )

    def list(
        self,
        *,
        status: str | None = None,
        limit: int | None = 50,
    ) -> list[Job]:
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        jobs: list[Job] = []
        for candidate in self.jobs_dir.glob("*.json"):
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if status and payload.get("status") != status:
                continue
            jobs.append(
                Job(
                    id=payload["id"],
                    kind=payload["kind"],
                    status=payload["status"],
                    input=payload.get("input") or {},
                    result=payload.get("result") or {},
                    error=payload.get("error"),
                    created_at=payload.get("created_at") or "",
                    started_at=payload.get("started_at"),
                    ended_at=payload.get("ended_at"),
                )
            )
        jobs.sort(key=lambda item: item.created_at, reverse=True)
        return jobs[:limit]


class JobRunner:
    """Asyncio background runner for the documented :class:`JobKind` values."""

    def __init__(
        self,
        store: JobStore,
        *,
        settings: Any,
        handlers: dict[JobKind, JobHandler] | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.handlers: dict[JobKind, JobHandler] = dict(
            handlers if handlers is not None else {JobKind.EXPORT_RECORDS: run_export_records}
        )
        self._semaphore = asyncio.Semaphore(int(getattr(settings, "job_max_concurrent", 4)))
        self._timeout = int(getattr(settings, "job_timeout_seconds", 300))
        self._retention_days = float(getattr(settings, "job_retention_days", 0.0))
        if not math.isfinite(self._retention_days) or self._retention_days < 0:
            raise ValueError("job_retention_days must be a finite non-negative number")
        self._last_cleanup = 0.0
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._poll_task: asyncio.Task[None] | None = None
        self._cancels: set[str] = set()
        self._wake = asyncio.Event()

    @property
    def wake(self) -> asyncio.Event:
        return self._wake

    def register(self, kind: JobKind, handler: JobHandler) -> None:
        self.handlers[kind] = handler

    async def _cleanup_expired(self) -> None:
        if self._retention_days <= 0:
            return
        self._last_cleanup = time.monotonic()
        try:
            await asyncio.to_thread(
                self.store.prune,
                retention_days=self._retention_days,
                apply=True,
                limit=50,
            )
        except Exception:
            LOGGER.exception("job retention cleanup failed")

    async def start_background(self) -> None:
        """Resume pending jobs and watch for submissions from other processes."""
        await self._cleanup_expired()
        self._schedule_pending()
        self._wake.set()
        if self._poll_task is None or self._poll_task.done():
            self._poll_task = asyncio.create_task(self._watch_pending())

    async def stop_background(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None
        for task in list(self._tasks.values()):
            task.cancel()
        for task in list(self._tasks.values()):
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError, Exception):
                await asyncio.wait_for(task, timeout=self._timeout)
        self._tasks.clear()

    def _schedule_pending(self) -> None:
        for status in (JobStatus.PENDING.value, JobStatus.RUNNING.value):
            for job in self.store.list(status=status, limit=None):
                self._schedule(job.id)

    async def _watch_pending(self) -> None:
        while True:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._wake.wait(), timeout=0.2)
            self._wake.clear()
            self._schedule_pending()
            if (
                self._retention_days > 0
                and time.monotonic() - self._last_cleanup >= JOB_CLEANUP_INTERVAL_SECONDS
            ):
                await self._cleanup_expired()

    def submit(self, kind: JobKind | str, input: dict[str, Any]) -> Job:
        if isinstance(kind, str):
            try:
                kind_enum = JobKind(kind)
            except ValueError as exc:
                raise ValueError(
                    f"Unsupported job kind {kind!r}; choose from {', '.join(JobKind.values())}"
                ) from exc
        else:
            kind_enum = kind
        if kind_enum not in self.handlers:
            raise ValueError(
                f"Unsupported job kind {kind_enum.value!r}; "
                f"choose from {', '.join(item.value for item in self.handlers)}"
            )
        if kind_enum == JobKind.EXPORT_RECORDS:
            format_ = input.get("format") or "json"
            if format_ not in EXPORT_FORMATS:
                raise ValueError(
                    f"Unsupported export format {format_!r}; "
                    f"choose from {', '.join(EXPORT_FORMATS)}"
                )
            limit = input.get("limit")
            limit = EXPORT_DEFAULT_LIMIT if limit is None else limit
            if type(limit) is not int or not 1 <= limit <= EXPORT_HARD_LIMIT:
                raise ValueError(f"limit must be between 1 and {EXPORT_HARD_LIMIT}")
            filters = input.get("filters")
            filters = {} if filters is None else filters
            if not isinstance(filters, dict):
                raise ValueError("filters must be an object")
            from .errors import QueryValidationError

            try:
                RecordQuery.from_values(**filters, limit=limit).validate(max_page=EXPORT_HARD_LIMIT)
            except (TypeError, QueryValidationError) as exc:
                raise ValueError(str(exc)) from exc
        job = Job.new(kind_enum, input)
        self.store.save(job)
        self._schedule(job.id)
        self._wake.set()
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.store.load(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.status in {
            JobStatus.SUCCEEDED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        }:
            raise ValueError(f"job {job_id} is already {job.status}")
        from .workspace import utc_now

        job.status = JobStatus.CANCELLED.value
        job.ended_at = utc_now()
        self.store.save(job)
        self._cancels.add(job_id)
        task = self._tasks.get(job_id)
        if task is not None:
            task.cancel()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.store.load(job_id)

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[Job]:
        return self.store.list(status=status, limit=limit)

    def _schedule(self, job_id: str) -> None:
        if job_id in self._tasks:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # A standalone CLI submission has no event loop. It stays
            # ``pending`` until a running server's store watcher sees it.
            return
        self._tasks[job_id] = loop.create_task(self._run(job_id))

    def _acquire_claim(self, job_id: str) -> FileLock | None:
        claim = self.store.claim(job_id)
        try:
            claim.acquire(timeout=0)
        except Timeout:
            return None
        return claim

    async def _run(self, job_id: str) -> None:
        job = self.store.load(job_id)
        if job is None:
            return
        try:
            async with self._semaphore:
                claim = self._acquire_claim(job_id)
                if claim is None:
                    return
                try:
                    job = self.store.load(job_id)
                    if job is None:
                        return
                    if job_id in self._cancels or job.status == JobStatus.CANCELLED.value:
                        self._mark_cancelled(job_id)
                        return
                    if job.status == JobStatus.RUNNING.value:
                        self._mark_interrupted(job)
                        return
                    if job.status != JobStatus.PENDING.value:
                        return
                    kind = JobKind(job.kind)
                    handler = self.handlers[kind]
                    job.status = JobStatus.RUNNING.value
                    from .workspace import utc_now

                    job.started_at = utc_now()
                    self.store.save(job)
                    try:
                        job.result = await asyncio.wait_for(
                            handler(job, JobContext(settings=self.settings, store=self.store)),
                            timeout=self._timeout,
                        )
                    except asyncio.TimeoutError:
                        job.status = JobStatus.FAILED.value
                        job.error = "timeout"
                    except asyncio.CancelledError:
                        current = self.store.load(job_id)
                        if job_id in self._cancels or (
                            current is not None and current.status == JobStatus.CANCELLED.value
                        ):
                            self._mark_cancelled(job_id)
                        else:
                            job.status = JobStatus.FAILED.value
                            job.error = "cancelled without await"
                            self.store.save(job)
                        return
                    except _JobCancelledError:
                        job.status = JobStatus.CANCELLED.value
                    except Exception as exc:  # noqa: BLE001
                        current = self.store.load(job_id)
                        if current is not None and current.status == JobStatus.CANCELLED.value:
                            job.status = JobStatus.CANCELLED.value
                        else:
                            job.status = JobStatus.FAILED.value
                            job.error = str(exc)
                            LOGGER.exception("job %s failed", job_id)
                    else:
                        current = self.store.load(job_id)
                        if current is not None and current.status == JobStatus.CANCELLED.value:
                            job.status = JobStatus.CANCELLED.value
                        else:
                            job.status = JobStatus.SUCCEEDED.value
                    from .workspace import utc_now

                    job.ended_at = utc_now()
                    self.store.save(job)
                finally:
                    claim.release()
        except Exception:
            LOGGER.exception("runner failed for job %s", job_id)
        finally:
            self._tasks.pop(job_id, None)

    def _mark_interrupted(self, job: Job) -> None:
        from .workspace import utc_now

        job.status = JobStatus.FAILED.value
        job.error = "interrupted"
        job.ended_at = utc_now()
        self.store.save(job)
        for staged in self.store.job_directory(job.id).glob(".result-*.tmp"):
            staged.unlink(missing_ok=True)

    def _mark_cancelled(self, job_id: str) -> None:
        job = self.store.load(job_id)
        if job is None:
            return
        from .workspace import utc_now

        job.status = JobStatus.CANCELLED.value
        job.ended_at = utc_now()
        self.store.save(job)
        self._cancels.discard(job_id)


class _JobCancelledError(Exception):
    """Stop an export after its persisted job reaches a terminal state."""


def _ensure_job_active(store: JobStore, job: Job) -> None:
    current = store.load(job.id)
    if current is not None and current.status in {
        JobStatus.CANCELLED.value,
        JobStatus.FAILED.value,
        JobStatus.SUCCEEDED.value,
    }:
        raise _JobCancelledError(job.id)


@contextlib.contextmanager
def _staged_result(target: Path, *, before_publish: Callable[[], None]) -> Iterator[Path]:
    """Write a result beside its destination and publish it atomically."""
    fd, tmp_name = tempfile.mkstemp(
        prefix=".result-", suffix=f"{target.suffix}.tmp", dir=target.parent
    )
    os.close(fd)
    staged = Path(tmp_name)
    try:
        yield staged
        before_publish()
        os.replace(staged, target)
    finally:
        with contextlib.suppress(FileNotFoundError):
            staged.unlink()


def _write_export_records(job: Job, context: JobContext) -> dict[str, Any]:
    """Synchronous streaming exporter; called in a worker thread."""
    raw_format = (job.input.get("format") or "json").lower()
    if raw_format not in EXPORT_FORMATS:
        raise ValueError(
            f"Unsupported export format {raw_format!r}; choose from {', '.join(EXPORT_FORMATS)}"
        )
    limit = int(job.input.get("limit") or EXPORT_DEFAULT_LIMIT)
    if limit < 1 or limit > EXPORT_HARD_LIMIT:
        raise ValueError(f"limit must be between 1 and {EXPORT_HARD_LIMIT}")
    filters = job.input.get("filters") or {}
    settings = context.settings
    db_path = getattr(settings, "db_path", "warcindex.db")
    data_dir = getattr(settings, "data_dir", None) or str(Path(db_path).with_suffix(".data"))
    suffix = ".json" if raw_format == "json" else ".csv" if raw_format == "csv" else ".parquet"
    target = context.store.result_path(job, suffix)
    selected = RecordQuery.from_values(**filters, limit=limit)
    written = 0
    _ensure_job_active(context.store, job)
    with Workspace(db_path, data_dir=data_dir, read_only=True, create=False) as workspace:
        query_service = QueryService(workspace)
        total = query_service.count_records(replace(selected, limit=1))
        planned_total = min(max(total - selected.offset, 0), limit)

        def report_progress() -> None:
            _ensure_job_active(context.store, job)
            context.store.write_progress(job.id, written, planned_total)

        report_progress()
        rows = query_service.iter_records(selected, export_limit=limit)
        with _staged_result(target, before_publish=report_progress) as staged:
            if raw_format == "json":
                with staged.open("w", encoding="utf-8") as handle:
                    handle.write("[\n")
                    for row in rows:
                        if written % 256 == 0:
                            _ensure_job_active(context.store, job)
                        if written:
                            handle.write(",\n")
                        json.dump(row, handle, ensure_ascii=False, default=str, indent=2)
                        written += 1
                        if written % 256 == 0:
                            report_progress()
                    handle.write("\n]\n")
            elif raw_format == "csv":
                with staged.open("w", encoding="utf-8", newline="") as handle:
                    row_iterator = iter(rows)
                    first = next(row_iterator, None)
                    fieldnames = list(first) if first is not None else []
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    if first is not None:
                        writer.writerow(first)
                        written = 1
                        if written % 256 == 0:
                            report_progress()
                    for row in row_iterator:
                        if written % 256 == 0:
                            _ensure_job_active(context.store, job)
                        writer.writerow(row)
                        written += 1
                        if written % 256 == 0:
                            report_progress()
            else:  # parquet
                import pyarrow as pa
                import pyarrow.parquet as pq

                writer = pq.ParquetWriter(staged, RECORD_SCHEMA, compression="zstd")
                batch: list[dict[str, Any]] = []
                try:
                    for row in rows:
                        batch.append(row)
                        if len(batch) < 256:
                            continue
                        _ensure_job_active(context.store, job)
                        table = pa.Table.from_pylist(batch, schema=RECORD_SCHEMA)
                        writer.write_table(table)
                        written += len(batch)
                        batch.clear()
                        report_progress()
                    if batch:
                        _ensure_job_active(context.store, job)
                        table = pa.Table.from_pylist(batch, schema=RECORD_SCHEMA)
                        writer.write_table(table)
                        written += len(batch)
                        report_progress()
                finally:
                    writer.close()
    return {
        "path": str(target),
        "format": raw_format,
        "rows": written,
        "size": target.stat().st_size,
        "total": total,
    }


async def run_export_records(job: Job, context: JobContext) -> dict[str, Any]:
    """Stream a bounded export without blocking the server's event loop."""
    worker = asyncio.get_running_loop().run_in_executor(None, _write_export_records, job, context)
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        # Signal the synchronous writer before waiting for it to stop. The
        # runner must retain its claim until no stale publisher remains.
        current = context.store.load(job.id)
        if current is not None and current.status == JobStatus.RUNNING.value:
            from .workspace import utc_now

            current.status = JobStatus.FAILED.value
            current.error = "cancelled without await"
            current.ended_at = utc_now()
            context.store.save(current)
        with contextlib.suppress(Exception):
            await worker
        raise


__all__ = [
    "EXPORT_DEFAULT_LIMIT",
    "EXPORT_FORMATS",
    "EXPORT_HARD_LIMIT",
    "Job",
    "JobContext",
    "JobHandler",
    "JobKind",
    "JobRunner",
    "JobStatus",
    "JobStore",
    "run_export_records",
]
