"""Unit tests for :mod:`metawarc.jobs`."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from metawarc.indexer import Indexer
from metawarc.jobs import (
    EXPORT_DEFAULT_LIMIT,
    EXPORT_FORMATS,
    EXPORT_HARD_LIMIT,
    Job,
    JobContext,
    JobKind,
    JobRunner,
    JobStatus,
    JobStore,
    run_export_records,
)


class _StubSettings:
    db_path = "warcindex.db"
    data_dir = "/tmp/metawarc-jobs-tests"
    job_max_concurrent = 2
    request_timeout_seconds = 30


def _indexed_settings(tmp_path: Path) -> _StubSettings:
    settings = _StubSettings()
    settings.db_path = str(tmp_path / "collection.db")
    settings.data_dir = str(tmp_path / "collection.data")
    return settings


def _build_indexed_workspace(tmp_path: Path, warc_factory) -> Path:
    source = warc_factory()
    db_path = str(tmp_path / "collection.db")
    Indexer(batch_size=1).index_records(
        [source], db_path, data_dir=str(tmp_path / "collection.data"), silent=True
    )
    return Path(db_path)


async def _wait_for_terminal(runner: JobRunner, job_id: str, *, attempts: int = 50) -> Job | None:
    for _ in range(attempts):
        current = runner.get(job_id)
        if current is None:
            return None
        if current.status in {
            JobStatus.SUCCEEDED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        }:
            return current
        await asyncio.sleep(0.05)
    return runner.get(job_id)


def test_job_store_round_trip(tmp_path: Path):
    store = JobStore(tmp_path)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 10})
    store.save(job)

    loaded = store.load(job.id)
    assert loaded is not None
    assert loaded.id == job.id
    assert loaded.kind == JobKind.EXPORT_RECORDS.value
    assert loaded.status == JobStatus.PENDING.value
    assert loaded.input == {"format": "json", "limit": 10}
    assert loaded.created_at == job.created_at


def test_job_store_invalid_id_is_rejected(tmp_path: Path):
    store = JobStore(tmp_path)
    with pytest.raises(ValueError):
        store._path("../escape")  # noqa: SLF001


def test_job_store_atomic_write_replaces_partial_file(tmp_path: Path):
    store = JobStore(tmp_path)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json"})
    target = store._path(job.id)  # noqa: SLF001
    target.write_text("{ this is not valid json", encoding="utf-8")
    store.save(job)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["id"] == job.id


def test_job_store_list_filters_and_paginates(tmp_path: Path):
    store = JobStore(tmp_path)
    first = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 5})
    first.created_at = "2026-10-06T00:00:00+00:00"
    store.save(first)
    second = Job.new(JobKind.EXPORT_RECORDS, {"format": "csv", "limit": 5})
    second.created_at = "2026-10-06T00:00:01+00:00"
    second.status = JobStatus.SUCCEEDED.value
    store.save(second)

    rows = store.list(limit=10)
    assert {item.id for item in rows} == {first.id, second.id}

    succeeded = store.list(status=JobStatus.SUCCEEDED.value, limit=10)
    assert {item.id for item in succeeded} == {second.id}

    with pytest.raises(ValueError):
        store.list(limit=0)


def test_run_export_records_writes_json_csv_and_parquet(tmp_path: Path, warc_factory):
    db_path = _build_indexed_workspace(tmp_path, warc_factory)
    store = JobStore(tmp_path / "collection.data")

    async def _exercise() -> None:
        for fmt in EXPORT_FORMATS:
            job = Job.new(JobKind.EXPORT_RECORDS, {"format": fmt, "limit": 10, "filters": {}})
            settings = _indexed_settings(tmp_path)
            settings.db_path = str(db_path)
            result = await run_export_records(job, JobContext(settings=settings, store=store))
            assert result["format"] == fmt
            assert result["rows"] >= 1
            path = Path(result["path"])
            assert path.exists()
            assert path.stat().st_size > 0
            if fmt == "parquet":
                import pyarrow.parquet as pq

                table = pq.read_table(path)
                assert table.num_rows >= 1

    asyncio.run(_exercise())


def test_run_export_records_rejects_bad_format(tmp_path: Path):
    store = JobStore(tmp_path)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "yaml", "limit": 1})
    with pytest.raises(ValueError, match="Unsupported export format"):
        asyncio.run(run_export_records(job, JobContext(settings=_StubSettings(), store=store)))


def test_run_export_records_rejects_oversized_limit(tmp_path: Path):
    store = JobStore(tmp_path)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": EXPORT_HARD_LIMIT + 1})
    with pytest.raises(ValueError, match="limit must be between"):
        asyncio.run(run_export_records(job, JobContext(settings=_StubSettings(), store=store)))


def test_run_export_records_default_limit_is_safe():
    assert EXPORT_DEFAULT_LIMIT >= 1


def test_run_export_records_handles_missing_input_fields(tmp_path: Path, warc_factory):
    _build_indexed_workspace(tmp_path, warc_factory)
    store = JobStore(tmp_path / "collection.data")
    payload: dict = {"format": "json"}
    payload.pop("limit", None)
    job = Job.new(JobKind.EXPORT_RECORDS, payload)
    settings = _indexed_settings(tmp_path)
    result = asyncio.run(run_export_records(job, JobContext(settings=settings, store=store)))
    assert result["format"] == "json"
    assert "rows" in result


def test_job_runner_submit_unknown_kind_raises(tmp_path: Path):
    store = JobStore(tmp_path)
    runner = JobRunner(store, settings=_StubSettings())
    with pytest.raises(ValueError, match="Unsupported job kind"):
        runner.submit("nonexistent-kind", {})


def test_job_runner_round_trip(tmp_path: Path, warc_factory):
    db_path = _build_indexed_workspace(tmp_path, warc_factory)
    store = JobStore(tmp_path / "collection.data")
    settings = _indexed_settings(tmp_path)
    settings.db_path = str(db_path)
    runner = JobRunner(store, settings=settings)

    async def _exercise() -> Job | None:
        job = runner.submit(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 10, "filters": {}})
        return await _wait_for_terminal(runner, job.id)

    finished = asyncio.run(_exercise())
    assert finished is not None
    assert finished.status == JobStatus.SUCCEEDED.value
    assert finished.result["rows"] >= 1
    assert finished.started_at is not None
    assert finished.ended_at is not None


def test_job_runner_cancel_running_job(tmp_path: Path, warc_factory):
    db_path = _build_indexed_workspace(tmp_path, warc_factory)
    store = JobStore(tmp_path / "collection.data")
    settings = _indexed_settings(tmp_path)
    settings.db_path = str(db_path)
    runner = JobRunner(store, settings=settings)

    async def slow_handler(job: Job, ctx: JobContext) -> dict:
        for _ in range(40):
            await asyncio.sleep(0.05)
        return {"rows": 0}

    runner.register(JobKind.EXPORT_RECORDS, slow_handler)

    async def _exercise() -> Job | None:
        job = runner.submit(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1, "filters": {}})
        for _ in range(40):
            current = runner.get(job.id)
            if current is not None and current.status == JobStatus.RUNNING.value:
                break
            await asyncio.sleep(0.025)
        runner.cancel(job.id)
        return await _wait_for_terminal(runner, job.id)

    cancelled = asyncio.run(_exercise())
    assert cancelled is not None
    assert cancelled.status in {
        JobStatus.CANCELLED.value,
        JobStatus.SUCCEEDED.value,
        JobStatus.FAILED.value,
    }


def test_job_runner_cancel_unknown_raises(tmp_path: Path):
    store = JobStore(tmp_path)
    runner = JobRunner(store, settings=_StubSettings())
    with pytest.raises(KeyError):
        runner.cancel("job-does-not-exist")


def test_job_runner_cancel_succeeded_raises(tmp_path: Path):
    store = JobStore(tmp_path)
    runner = JobRunner(store, settings=_StubSettings())
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json"})
    job.status = JobStatus.SUCCEEDED.value
    store.save(job)
    with pytest.raises(ValueError, match="already succeeded"):
        runner.cancel(job.id)


def test_job_runner_resume_pending_on_start(tmp_path: Path, warc_factory):
    db_path = _build_indexed_workspace(tmp_path, warc_factory)
    store = JobStore(tmp_path / "collection.data")
    settings = _indexed_settings(tmp_path)
    settings.db_path = str(db_path)
    pending = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 5, "filters": {}})
    store.save(pending)

    runner = JobRunner(store, settings=settings)

    async def _exercise() -> Job | None:
        await runner.start_background()
        return await _wait_for_terminal(runner, pending.id)

    finished = asyncio.run(_exercise())
    assert finished is not None
    assert finished.status == JobStatus.SUCCEEDED.value


def test_job_runner_handler_failure_marks_failed(tmp_path: Path):
    store = JobStore(tmp_path)
    runner = JobRunner(store, settings=_StubSettings())

    async def broken(job: Job, ctx: JobContext) -> dict:
        raise RuntimeError("boom")

    runner.register(JobKind.EXPORT_RECORDS, broken)

    async def _exercise() -> Job | None:
        job = runner.submit(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1, "filters": {}})
        return await _wait_for_terminal(runner, job.id)

    finished = asyncio.run(_exercise())
    assert finished is not None
    assert finished.status == JobStatus.FAILED.value
    assert finished.error is not None
    assert "boom" in finished.error


def test_job_runner_sync_submit_does_not_raise(tmp_path: Path):
    """Submitting from outside an event loop must not raise — it leaves the
    job in the ``pending`` state for another runner to claim."""
    store = JobStore(tmp_path)
    runner = JobRunner(store, settings=_StubSettings())
    job = runner.submit(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1})
    assert runner.get(job.id) is not None
    assert runner.get(job.id).status == JobStatus.PENDING.value
