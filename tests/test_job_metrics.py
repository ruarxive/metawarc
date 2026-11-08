"""Contract tests for retained-job operational metrics."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from metawarc.api_server import create_app
from metawarc.cli_jobs import jobs_group
from metawarc.jobs import Job, JobKind, JobRunner, JobStatus, JobStore
from metawarc.settings import ServerSettings

BASE = datetime(2026, 11, 7, tzinfo=timezone.utc)


def _at(seconds: int) -> str:
    return (BASE + timedelta(seconds=seconds)).isoformat()


def _job(
    store: JobStore,
    *,
    status: str = "pending",
    created_at: str | None = _at(0),
    started_at: str | None = None,
    ended_at: str | None = None,
    job_id: str | None = None,
) -> Job:
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1})
    if job_id is not None:
        job.id = job_id
    job.status = status
    job.created_at = created_at or ""
    job.started_at = started_at
    job.ended_at = ended_at
    store.save(job)
    return job


def _assert_valid_metrics(payload: dict, limit: int = 1000) -> None:
    assert payload["limit"] == limit
    assert payload["included"] <= payload["total"]
    assert payload["included"] <= limit
    assert payload["truncated"] is (payload["included"] < payload["total"])
    assert sum(payload["counts"].values()) == payload["included"]
    assert set(payload["counts"]) == set(JobStatus.values())
    for name in ("queue_wait_seconds", "execution_seconds"):
        summary = payload[name]
        assert summary["samples"] >= 0
        if summary["samples"] == 0:
            assert summary["mean"] is None
            assert summary["max"] is None
    json.dumps(payload, allow_nan=False)
    generated = datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
    assert generated.tzinfo is not None


def test_metrics_mixed_statuses_and_exact_durations(tmp_path: Path):
    store = JobStore(tmp_path)
    _job(store, status="pending", created_at=_at(0))
    _job(store, status="running", created_at=_at(10), started_at=_at(12))
    _job(
        store,
        status="succeeded",
        created_at=_at(20),
        started_at=_at(24),
        ended_at=_at(30),
    )
    _job(
        store,
        status="failed",
        created_at=_at(40),
        started_at=_at(41),
        ended_at=_at(43),
    )
    _job(
        store,
        status="cancelled",
        created_at=_at(50),
        started_at=_at(55),
        ended_at=_at(59),
    )

    payload = store.metrics()

    _assert_valid_metrics(payload)
    assert payload["total"] == payload["included"] == 5
    assert payload["truncated"] is False
    assert payload["counts"] == {
        "pending": 1,
        "running": 1,
        "succeeded": 1,
        "failed": 1,
        "cancelled": 1,
    }
    assert payload["invalid"] == 0
    assert payload["queue_wait_seconds"] == {"samples": 4, "mean": 3.0, "max": 5.0}
    assert payload["execution_seconds"] == {"samples": 3, "mean": 4.0, "max": 6.0}


def test_metrics_empty_store_has_all_statuses_and_null_statistics(tmp_path: Path):
    payload = JobStore(tmp_path).metrics()

    _assert_valid_metrics(payload)
    assert payload["total"] == payload["included"] == payload["invalid"] == 0
    assert payload["counts"] == dict.fromkeys(JobStatus.values(), 0)
    assert payload["queue_wait_seconds"] == {"samples": 0, "mean": None, "max": None}
    assert payload["execution_seconds"] == {"samples": 0, "mean": None, "max": None}


def test_metrics_timestamp_edges_affect_only_their_samples(tmp_path: Path):
    store = JobStore(tmp_path)
    _job(store, status="pending", created_at=_at(0))
    _job(
        store,
        status="succeeded",
        created_at=_at(10),
        started_at="2026-11-07T00:00:11",
        ended_at=_at(20),
    )
    _job(
        store,
        status="failed",
        created_at=_at(30),
        started_at=_at(29),
        ended_at="not-a-date",
    )
    _job(
        store,
        status="cancelled",
        created_at=_at(40),
        started_at=_at(41),
        ended_at=_at(40),
    )
    _job(store, status="pending", created_at="2026-11-07T00:00:00")

    payload = store.metrics()

    _assert_valid_metrics(payload)
    assert payload["total"] == 4
    assert payload["included"] == 4
    assert payload["invalid"] == 1
    assert payload["counts"]["pending"] == 1
    assert payload["queue_wait_seconds"]["samples"] == 1
    assert payload["execution_seconds"] == {"samples": 0, "mean": None, "max": None}


def test_metrics_limit_selects_newest_with_id_tiebreaker(tmp_path: Path):
    store = JobStore(tmp_path)
    _job(store, status="failed", created_at=_at(0), job_id="job-old")
    for job_id, status in (
        ("job-a", "pending"),
        ("job-b", "running"),
        ("job-c", "succeeded"),
    ):
        _job(store, status=status, created_at=_at(10), job_id=job_id)

    payload = store.metrics(limit=2)

    _assert_valid_metrics(payload, limit=2)
    assert payload["total"] == 4
    assert payload["included"] == 2
    assert payload["truncated"] is True
    assert payload["counts"]["succeeded"] == 1
    assert payload["counts"]["running"] == 1
    assert payload["counts"]["pending"] == 0


@pytest.mark.parametrize("limit", [1, 10_000])
def test_metrics_accepts_limit_bounds(tmp_path: Path, limit: int):
    store = JobStore(tmp_path)
    _job(store)

    payload = store.metrics(limit=limit)

    _assert_valid_metrics(payload, limit=limit)
    assert payload["included"] == 1


@pytest.mark.parametrize("limit", [0, -1, 10_001])
def test_metrics_rejects_out_of_range_limits(tmp_path: Path, limit: int):
    with pytest.raises(ValueError, match="limit must be between 1 and 10000"):
        JobStore(tmp_path).metrics(limit=limit)


def test_metrics_counts_invalid_candidates_without_following_symlinks(tmp_path: Path):
    store = JobStore(tmp_path / "jobs-root")
    _job(store, status="succeeded")
    (store.jobs_dir / "job-malformed.json").write_text("not json", encoding="utf-8")
    (store.jobs_dir / "job-oversized.json").write_bytes(b" " * (1024 * 1024 + 1))
    _job(store, created_at="2026-11-07T00:00:00")
    _job(store, status="unknown")
    mismatch = store.jobs_dir / "job-mismatch.json"
    mismatch.write_text(
        json.dumps(
            {
                "id": "job-other",
                "kind": "export-records",
                "status": "pending",
                "created_at": _at(0),
            }
        ),
        encoding="utf-8",
    )
    (store.jobs_dir / "job-directory.json").mkdir()

    payload = store.metrics()

    _assert_valid_metrics(payload)
    assert payload["total"] == payload["included"] == 1
    assert payload["invalid"] == 6

    external = _job(JobStore(tmp_path / "external"), job_id="job-external")
    symlink = store.jobs_dir / "job-symlink.json"
    try:
        symlink.symlink_to(store._path(external.id))
    except OSError:
        pytest.skip("creating symlinks requires additional platform permission")
    with_symlink = store.metrics()
    assert with_symlink["total"] == 1
    assert with_symlink["invalid"] == 7


def test_metrics_skips_file_disappearing_during_scan(tmp_path: Path, monkeypatch):
    store = JobStore(tmp_path)
    _job(store, job_id="job-kept")
    ghost = _job(store, job_id="job-ghost")
    ghost_path = store._path(ghost.id)
    original_open = Path.open

    def disappearing_open(self, *args, **kwargs):
        if self == ghost_path:
            raise FileNotFoundError(self)
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", disappearing_open)
    payload = store.metrics()

    _assert_valid_metrics(payload)
    assert payload["total"] == payload["included"] == 1
    assert payload["invalid"] == 0


def test_metrics_does_not_mutate_lifecycle_progress_results_or_claims(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job(
        store,
        status="succeeded",
        created_at=_at(0),
        started_at=_at(1),
        ended_at=_at(2),
    )
    store.write_progress(job.id, 1, 1)
    result = store.result_path(job, ".json")
    result.write_text("[]\n", encoding="utf-8")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    payload = store.metrics()

    _assert_valid_metrics(payload)
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (store.job_directory(job.id) / ".runner.lock").exists()


def test_metrics_observes_completion_cancellation_and_pruning(tmp_path: Path):
    store = JobStore(tmp_path)
    jobs = [
        _job(
            store,
            status="succeeded",
            created_at=_at(index),
            started_at=_at(index + 1),
            ended_at="2000-01-01T00:00:00+00:00",
        )
        for index in range(12)
    ]
    pending = _job(store, status="pending", created_at=_at(20))

    async def exercise() -> None:
        for job in jobs:
            job.status = "running"
            store.save(job)
            payload = await asyncio.to_thread(store.metrics, limit=3)
            _assert_valid_metrics(payload, limit=3)
            job.status = "succeeded"
            store.save(job)
        pending.status = "cancelled"
        pending.ended_at = _at(21)
        store.save(pending)

        async def observe_pruning() -> None:
            for _ in range(10):
                payload = await asyncio.to_thread(store.metrics)
                _assert_valid_metrics(payload)

        await asyncio.gather(asyncio.to_thread(store.prune, 0, True), observe_pruning())
        assert store.metrics()["total"] == 0

    asyncio.run(exercise())


def test_metrics_observes_interrupted_recovery(tmp_path: Path):
    store = JobStore(tmp_path / "collection.data")
    interrupted = _job(
        store,
        status="running",
        created_at=_at(0),
        started_at=_at(1),
    )
    runner = JobRunner(
        store,
        settings=ServerSettings(
            db_path=str(tmp_path / "collection.db"),
            data_dir=str(tmp_path / "collection.data"),
        ),
    )

    async def exercise() -> None:
        await runner.start_background()
        try:
            for _ in range(50):
                payload = await asyncio.to_thread(store.metrics)
                _assert_valid_metrics(payload)
                current = store.load(interrupted.id)
                if current is not None and current.status == "failed":
                    assert current.error == "interrupted"
                    if payload["counts"]["failed"] == 1:
                        return
                await asyncio.sleep(0.01)
            pytest.fail("running job was not recovered")
        finally:
            await runner.stop_background()

    asyncio.run(exercise())


def test_cli_metrics_matches_store_without_scheduling(tmp_path: Path, monkeypatch):
    database = tmp_path / "collection.db"
    store = JobStore(tmp_path / "collection.data")
    pending = _job(store, status="pending")

    def fail_start(self):
        raise AssertionError("metrics must not start a runner")

    monkeypatch.setattr("metawarc.jobs.JobRunner.start_background", fail_start)
    result = CliRunner().invoke(
        jobs_group,
        ["--dbfile", str(database), "metrics", "--limit", "1000"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    _assert_valid_metrics(payload)
    assert payload["counts"]["pending"] == 1
    assert store.load(pending.id).status == "pending"
    assert not (store.job_directory(pending.id) / ".runner.lock").exists()


@pytest.mark.parametrize("limit", [0, 10_001])
def test_cli_metrics_rejects_invalid_limit(tmp_path: Path, limit: int):
    result = CliRunner().invoke(
        jobs_group,
        ["--dbfile", str(tmp_path / "collection.db"), "metrics", "--limit", str(limit)],
    )
    assert result.exit_code == 2


def test_rest_metrics_auth_route_precedence_privacy_and_thread_offload(tmp_path: Path, monkeypatch):
    settings = ServerSettings(
        db_path=str(tmp_path / "collection.db"),
        data_dir=str(tmp_path / "collection.data"),
        token="secret",
    )
    original_to_thread = asyncio.to_thread
    calls = []

    async def recording_to_thread(function, /, *args, **kwargs):
        calls.append(function)
        return await original_to_thread(function, *args, **kwargs)

    monkeypatch.setattr("metawarc.api_server.asyncio.to_thread", recording_to_thread)
    with TestClient(create_app(settings)) as client:
        store = client.app.state.job_runner.store
        job = _job(store, status="succeeded", started_at=_at(1), ended_at=_at(2))
        job.error = "sensitive-error"
        job.input["secret"] = "sensitive-input"
        job.result["path"] = "/private/result.json"
        store.save(job)

        assert client.get("/jobs/metrics").status_code == 401
        assert (
            client.get("/jobs/metrics", headers={"Authorization": "Bearer wrong"}).status_code
            == 401
        )
        response = client.get(
            "/jobs/metrics?limit=1000", headers={"Authorization": "Bearer secret"}
        )

        assert response.status_code == 200
        payload = response.json()
        _assert_valid_metrics(payload)
        assert store.metrics in calls
        assert payload["counts"]["succeeded"] == 1
        assert job.id not in response.text
        assert "sensitive" not in response.text
        assert "/private" not in response.text
        assert set(payload) == {
            "generated_at",
            "limit",
            "total",
            "included",
            "truncated",
            "counts",
            "invalid",
            "queue_wait_seconds",
            "execution_seconds",
        }
        for limit in (0, 10_001):
            invalid = client.get(
                f"/jobs/metrics?limit={limit}",
                headers={"Authorization": "Bearer secret"},
            )
            assert invalid.status_code == 422
