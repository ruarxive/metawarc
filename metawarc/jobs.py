"""Durable, authenticated batch-job surface for long-running exports.

Jobs are persisted as JSON files under ``<data_dir>/jobs/<id>.json``
and executed by an asyncio runner started from the FastAPI lifespan
handler. The MVP registers one job kind, ``export-records``, which
materialises a ``QueryService.list_records`` query into a JSON, CSV,
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
import json
import logging
import os
import tempfile
import uuid
from collections.abc import Awaitable as TypingAwaitable
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from .query import QueryService, RecordQuery
from .workspace import Workspace

LOGGER = logging.getLogger("metawarc.jobs")

EXPORT_FORMATS = ("json", "csv", "parquet")
EXPORT_DEFAULT_LIMIT = 1_000
EXPORT_HARD_LIMIT = 100_000

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

    def result_path(self, job: Job, suffix: str) -> Path:
        out = self.data_dir / "jobs" / job.id
        out.mkdir(parents=True, exist_ok=True)
        return out / f"result{suffix}"

    def save(self, job: Job) -> None:
        target = self._path(job.id)
        fd, tmp_name = tempfile.mkstemp(prefix=".job-", suffix=".json.tmp", dir=self.jobs_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(job.to_dict(), handle, ensure_ascii=False, sort_keys=True)
            os.replace(tmp_name, target)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

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
        limit: int = 50,
    ) -> list[Job]:
        if limit < 1:
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
        self._timeout = int(getattr(settings, "request_timeout_seconds", 30))
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._cancels: set[str] = set()
        self._wake = asyncio.Event()

    @property
    def wake(self) -> asyncio.Event:
        return self._wake

    def register(self, kind: JobKind, handler: JobHandler) -> None:
        self.handlers[kind] = handler

    async def start_background(self) -> None:
        """Resume any pending jobs left over from a previous run."""
        for job in self.store.list():
            if job.status == JobStatus.PENDING.value:
                self._schedule(job.id)
        self._wake.set()

    async def stop_background(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        for task in list(self._tasks.values()):
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError, Exception):
                await asyncio.wait_for(task, timeout=self._timeout)
        self._tasks.clear()

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
        self._cancels.add(job_id)
        task = self._tasks.get(job_id)
        if task is not None:
            task.cancel()
        return self.store.load(job_id)  # type: ignore[return-value]

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
            # Called from a sync context (FastAPI sync handler or CLI
            # submit). The job stays ``pending``; the lifespan-managed
            # runner picks it up on the next startup, or another
            # server process running the same workspace claims it.
            return
        self._tasks[job_id] = loop.create_task(self._run(job_id))

    async def _run(self, job_id: str) -> None:
        job = self.store.load(job_id)
        if job is None:
            return
        kind = JobKind(job.kind)
        handler = self.handlers[kind]
        try:
            async with self._semaphore:
                if job_id in self._cancels:
                    self._mark_cancelled(job_id)
                    return
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
                    if job_id in self._cancels:
                        self._mark_cancelled(job_id)
                    else:
                        job.status = JobStatus.FAILED.value
                        job.error = "cancelled without await"
                    return
                except Exception as exc:  # noqa: BLE001
                    job.status = JobStatus.FAILED.value
                    job.error = str(exc)
                    LOGGER.exception("job %s failed", job_id)
                else:
                    job.status = JobStatus.SUCCEEDED.value
                from .workspace import utc_now

                job.ended_at = utc_now()
                self.store.save(job)
        except Exception:
            LOGGER.exception("runner failed for job %s", job_id)
        finally:
            self._tasks.pop(job_id, None)

    def _mark_cancelled(self, job_id: str) -> None:
        job = self.store.load(job_id)
        if job is None:
            return
        from .workspace import utc_now

        job.status = JobStatus.CANCELLED.value
        job.ended_at = utc_now()
        self.store.save(job)
        self._cancels.discard(job_id)


async def run_export_records(job: Job, context: JobContext) -> dict[str, Any]:
    """Materialise a ``QueryService.list_records`` query to a file.

    The handler respects the existing ``RecordQuery`` allowlist and
    reuses the same export formats the local CLI already supports
    (``json``, ``csv``, ``parquet``).
    """
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
    with Workspace(db_path, data_dir=data_dir, read_only=True, create=False) as workspace:
        query_service = QueryService(workspace)
        total, rows = query_service.list_records(selected)
        if raw_format == "json":
            target.write_text(
                json.dumps(rows, ensure_ascii=False, default=str, indent=2),
                encoding="utf-8",
            )
        elif raw_format == "csv":
            with target.open("w", encoding="utf-8", newline="") as handle:
                fieldnames = list(rows[0]) if rows else []
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        else:  # parquet
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pa.Table.from_pylist(rows)
            pq.write_table(table, target, compression="zstd")
    return {
        "path": str(target),
        "format": raw_format,
        "rows": len(rows),
        "size": target.stat().st_size,
        "total": total,
    }


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
