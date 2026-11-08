"""Contract tests for durable job progress and terminal-job retention."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from metawarc.cli_jobs import jobs_group
from metawarc.indexer import Indexer
from metawarc.jobs import (
    EXPORT_FORMATS,
    Job,
    JobContext,
    JobKind,
    JobRunner,
    JobStore,
    run_export_records,
)
from metawarc.settings import ServerSettings

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


class _Settings:
    job_max_concurrent = 1
    job_timeout_seconds = 30
    job_retention_days = 0.0

    def __init__(self, database: Path, data_dir: Path) -> None:
        self.db_path = str(database)
        self.data_dir = str(data_dir)


def _job(store: JobStore, *, status: str = "succeeded", ended_at: str | None = None) -> Job:
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1})
    job.status = status
    job.ended_at = ended_at
    store.save(job)
    return job


def _ids(items: list[dict]) -> set[str]:
    return {item["job_id"] for item in items}


def _invoke(arguments: list[str], database: Path):
    return CliRunner().invoke(
        jobs_group,
        ["--dbfile", str(database), *arguments],
        catch_exceptions=False,
    )


def _indexed_workspace(tmp_path: Path, warc_factory, records: int = 2) -> _Settings:
    source = warc_factory(
        records=[
            {
                "url": f"https://example.test/{index}",
                "payload": f"row {index}".encode("ascii"),
            }
            for index in range(records)
        ]
    )
    database = tmp_path / "collection.db"
    data_dir = tmp_path / "collection.data"
    Indexer(batch_size=50).index_records(
        [source], str(database), data_dir=str(data_dir), silent=True
    )
    return _Settings(database, data_dir)


def test_progress_sidecar_is_atomic_validated_and_separate_from_lifecycle(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job(store, status="running")

    initial = store.write_progress(job.id, 0, 257)
    assert initial is not None
    assert initial["processed_rows"] == 0
    assert initial["total_rows"] == 257
    assert initial["updated_at"]
    assert store.load_progress(job.id) == initial
    assert store.load(job.id) == job

    store.write_progress(job.id, 256, 257)
    assert store.load_progress(job.id)["processed_rows"] == 256
    assert store.load(job.id) == job
    assert list(store.job_directory(job.id).glob(".progress-*.tmp")) == []
    with pytest.raises(ValueError):
        store.write_progress(job.id, 258, 257)
    with pytest.raises(ValueError):
        store.write_progress(job.id, -1, 257)


def test_missing_or_malformed_progress_projects_as_null(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job(store)
    assert store.load_progress(job.id) is None
    store.job_directory(job.id)
    store.progress_path(job.id).write_text("not json", encoding="utf-8")
    assert store.load_progress(job.id) is None


@pytest.mark.parametrize("format_", EXPORT_FORMATS)
def test_export_publishes_final_progress(tmp_path: Path, warc_factory, format_: str):
    settings = _indexed_workspace(tmp_path, warc_factory)
    store = JobStore(settings.data_dir)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": format_, "limit": 10, "filters": {}})

    result = asyncio.run(run_export_records(job, JobContext(settings=settings, store=store)))

    progress = store.load_progress(job.id)
    assert progress is not None
    assert progress["processed_rows"] == result["rows"] == 2
    assert progress["total_rows"] == 2


def test_export_progress_uses_planned_limited_total(tmp_path: Path, warc_factory):
    settings = _indexed_workspace(tmp_path, warc_factory, records=3)
    store = JobStore(settings.data_dir)
    job = Job.new(
        JobKind.EXPORT_RECORDS,
        {"format": "json", "limit": 1, "filters": {"offset": 1}},
    )

    result = asyncio.run(run_export_records(job, JobContext(settings=settings, store=store)))

    assert result["total"] == 3
    assert result["rows"] == 1
    assert store.load_progress(job.id)["total_rows"] == 1


def test_export_progress_updates_at_streaming_boundaries(tmp_path: Path, warc_factory, monkeypatch):
    settings = _indexed_workspace(tmp_path, warc_factory, records=257)
    store = JobStore(settings.data_dir)
    updates: list[tuple[int, int]] = []
    original = store.write_progress

    def record(job_id: str, processed: int, total: int):
        updates.append((processed, total))
        return original(job_id, processed, total)

    monkeypatch.setattr(store, "write_progress", record)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1000, "filters": {}})
    result = asyncio.run(run_export_records(job, JobContext(settings=settings, store=store)))

    assert result["rows"] == 257
    assert updates[0] == (0, 257)
    assert (256, 257) in updates
    assert updates[-1] == (257, 257)
    assert updates == sorted(updates)


def test_progress_write_failure_removes_staged_result(tmp_path: Path, warc_factory, monkeypatch):
    settings = _indexed_workspace(tmp_path, warc_factory)
    store = JobStore(settings.data_dir)
    original = store.write_progress

    def fail_after_start(job_id: str, processed: int, total: int):
        if processed:
            raise OSError("progress storage failed")
        return original(job_id, processed, total)

    monkeypatch.setattr(store, "write_progress", fail_after_start)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 10, "filters": {}})
    with pytest.raises(OSError, match="progress storage failed"):
        asyncio.run(run_export_records(job, JobContext(settings=settings, store=store)))

    assert not store.result_path(job, ".json").exists()
    assert list(store.job_directory(job.id).glob(".result-*.tmp")) == []


def test_cli_job_views_and_wait_expose_progress(tmp_path: Path):
    database = tmp_path / "collection.db"
    store = JobStore(tmp_path / "collection.data")
    job = _job(store, ended_at="2026-11-06T00:00:00+00:00")
    job.result = {"path": str(store.result_path(job, ".json")), "rows": 1}
    store.save(job)
    expected = store.write_progress(job.id, 1, 1)

    listed = _invoke(["list"], database)
    assert listed.exit_code == 0
    assert json.loads(listed.stdout)[0]["progress"] == expected

    waited = _invoke(["wait", job.id, "--progress"], database)
    assert waited.exit_code == 0
    assert json.loads(waited.stdout)["progress"] == expected
    assert "1/1" in waited.stderr
    assert "rows" in waited.stderr


def test_prune_preview_apply_and_cutoff(tmp_path: Path):
    store = JobStore(tmp_path)
    expired = _job(store, ended_at="2026-11-05T23:59:59+00:00")
    recent = _job(store, ended_at="2026-11-06T00:00:00+00:00")
    pending = _job(store, status="pending", ended_at="2026-11-01T00:00:00+00:00")
    malformed = _job(store, ended_at="not-a-date")
    artifact = store.result_path(expired, ".json")
    artifact.write_text("[]\n", encoding="utf-8")
    store.write_progress(expired.id, 0, 0)

    preview = store.prune(retention_days=1, now=NOW)
    assert preview["dry_run"] is True
    assert _ids(preview["candidates"]) == {expired.id}
    assert preview["deleted"] == []
    assert _ids(preview["skipped"]) >= {recent.id, pending.id, malformed.id}
    assert store.load(expired.id) is not None
    assert artifact.exists()

    applied = store.prune(retention_days=1, apply=True, now=NOW)
    assert applied["dry_run"] is False
    assert _ids(applied["deleted"]) == {expired.id}
    assert store.load(expired.id) is None
    assert not artifact.exists()
    assert store.load_progress(expired.id) is None
    assert store.load(recent.id) is not None
    assert store.load(pending.id) is not None
    assert store.load(malformed.id) is not None


def test_prune_skips_locked_job_until_claim_is_released(tmp_path: Path):
    store = JobStore(tmp_path)
    expired = _job(store, ended_at="2026-11-01T00:00:00+00:00")
    claim = store.claim(expired.id)
    claim.acquire(timeout=0)
    try:
        report = store.prune(retention_days=0, apply=True, now=NOW)
        assert report["deleted"] == []
        assert _ids(report["skipped"]) == {expired.id}
        assert store.load(expired.id) is not None
    finally:
        claim.release()

    report = store.prune(retention_days=0, apply=True, now=NOW)
    assert _ids(report["deleted"]) == {expired.id}
    assert store.load(expired.id) is None


def test_prune_never_deletes_external_or_unexpected_content(tmp_path: Path):
    store = JobStore(tmp_path / "jobs-root")
    expired = _job(store, ended_at="2026-11-01T00:00:00+00:00")
    external = tmp_path / "external.json"
    external.write_text("secret", encoding="utf-8")
    expired.result = {"path": str(external), "format": "json"}
    store.save(expired)
    artifact = store.result_path(expired, ".json")
    try:
        artifact.symlink_to(external)
    except OSError:
        pytest.skip("creating symlinks requires additional platform permission")
    unexpected = store.job_directory(expired.id) / "unexpected"
    unexpected.mkdir()
    unexpected_file = unexpected / "keep.txt"
    unexpected_file.write_text("keep", encoding="utf-8")

    report = store.prune(retention_days=0, apply=True, now=NOW)

    assert _ids(report["deleted"]) == {expired.id}
    assert external.read_text(encoding="utf-8") == "secret"
    assert not artifact.exists()
    assert unexpected_file.read_text(encoding="utf-8") == "keep"


def test_prune_cli_preview_requires_apply(tmp_path: Path):
    database = tmp_path / "collection.db"
    store = JobStore(tmp_path / "collection.data")
    expired = _job(store, ended_at="2026-11-01T00:00:00+00:00")

    preview = _invoke(["prune", "--retention-days", "0"], database)
    assert preview.exit_code == 0
    assert json.loads(preview.stdout)["dry_run"] is True
    assert store.load(expired.id) is not None

    applied = _invoke(["prune", "--retention-days", "0", "--apply"], database)
    assert applied.exit_code == 0
    assert _ids(json.loads(applied.stdout)["deleted"]) == {expired.id}
    assert store.load(expired.id) is None


def test_automatic_retention_is_bounded_and_opt_in(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "collection.data"
    store = JobStore(data_dir)
    jobs = [_job(store, ended_at="2026-11-01T00:00:00+00:00") for _ in range(55)]
    settings = _Settings(tmp_path / "collection.db", data_dir)
    settings.job_retention_days = 1.0
    runner = JobRunner(store, settings=settings)
    monkeypatch.setattr("metawarc.jobs.JOB_CLEANUP_INTERVAL_SECONDS", 0.01)

    async def exercise() -> None:
        await runner.start_background()
        try:
            for _ in range(100):
                if all(store.load(job.id) is None for job in jobs):
                    return
                await asyncio.sleep(0.02)
            pytest.fail("automatic retention did not prune every expired job")
        finally:
            await runner.stop_background()

    asyncio.run(exercise())


def test_retention_setting_rejects_negative_values(monkeypatch):
    with pytest.raises(ValueError):
        ServerSettings(job_retention_days=-1)
    monkeypatch.setenv("METAWARC_JOB_RETENTION_DAYS", "2.5")
    assert ServerSettings.from_env().job_retention_days == 2.5


@pytest.mark.parametrize("records", [0, 1, 256])
@pytest.mark.parametrize("format_", EXPORT_FORMATS)
def test_export_progress_empty_and_exact_batches(
    tmp_path: Path, warc_factory, records: int, format_: str
):
    settings = _indexed_workspace(tmp_path, warc_factory, records=records)
    store = JobStore(settings.data_dir)
    filters = {"url_pattern": "^https://does-not-match/"} if records == 0 else {}
    job = Job.new(
        JobKind.EXPORT_RECORDS,
        {"format": format_, "limit": 1000, "filters": filters},
    )

    result = asyncio.run(run_export_records(job, JobContext(settings=settings, store=store)))

    progress = store.load_progress(job.id)
    assert result["rows"] == records
    assert progress is not None
    assert progress["processed_rows"] == records
    assert progress["total_rows"] == records


def test_cancel_and_interrupted_recovery_keep_last_progress(tmp_path: Path):
    data_dir = tmp_path / "collection.data"
    store = JobStore(data_dir)
    settings = _Settings(tmp_path / "collection.db", data_dir)
    runner = JobRunner(store, settings=settings)
    cancelled = _job(store, status="pending")
    cancelled_progress = store.write_progress(cancelled.id, 0, 10)
    runner.cancel(cancelled.id)
    assert store.load_progress(cancelled.id) == cancelled_progress

    interrupted = _job(store, status="running")
    interrupted_progress = store.write_progress(interrupted.id, 256, 257)

    async def exercise() -> Job:
        await runner.start_background()
        try:
            for _ in range(50):
                current = store.load(interrupted.id)
                if current is not None and current.status == "failed":
                    return current
                await asyncio.sleep(0.02)
            pytest.fail("running job was not recovered")
        finally:
            await runner.stop_background()

    recovered = asyncio.run(exercise())
    assert recovered.error == "interrupted"
    assert store.load_progress(interrupted.id) == interrupted_progress


def test_prune_cli_rejects_negative_retention(tmp_path: Path):
    database = tmp_path / "collection.db"
    store = JobStore(tmp_path / "collection.data")
    expired = _job(store, ended_at="2026-11-01T00:00:00+00:00")

    result = _invoke(["prune", "--retention-days", "-1"], database)

    assert result.exit_code == 2
    assert store.load(expired.id) is not None
