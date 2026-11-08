"""Real subprocess coverage for job claims and crash recovery."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from metawarc.jobs import Job, JobKind, JobStatus, JobStore

DRIVER = Path(__file__).with_name("job_process_driver.py")


def _start_driver(
    data_dir: Path,
    job_id: str,
    *,
    hold_seconds: float = 0.5,
    stage_partial: bool = False,
) -> subprocess.Popen[str]:
    command = [
        sys.executable,
        str(DRIVER),
        "--data-dir",
        str(data_dir),
        "--job-id",
        job_id,
        "--invocations",
        str(data_dir / "invocations.log"),
        "--started",
        str(data_dir / "started.txt"),
        "--hold-seconds",
        str(hold_seconds),
    ]
    if stage_partial:
        command.append("--stage-partial")
    return subprocess.Popen(command, text=True)


def _finish(process: subprocess.Popen[str]) -> None:
    try:
        assert process.wait(timeout=20) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def _invocations(data_dir: Path) -> list[str]:
    path = data_dir / "invocations.log"
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def test_independent_processes_invoke_one_pending_job_once(tmp_path: Path):
    data_dir = tmp_path / "collection.data"
    store = JobStore(data_dir)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1})
    store.save(job)
    workers = [_start_driver(data_dir, job.id) for _ in range(2)]
    for worker in workers:
        _finish(worker)

    finished = store.load(job.id)
    assert finished is not None
    assert finished.status == JobStatus.SUCCEEDED.value
    invocations = _invocations(data_dir)
    assert len(invocations) == 1
    assert invocations[0].endswith(job.id)

    observer = _start_driver(data_dir, job.id)
    _finish(observer)
    assert len(_invocations(data_dir)) == 1
    assert store.load(job.id) == finished


def test_surviving_process_recovers_killed_job_owner(tmp_path: Path):
    data_dir = tmp_path / "collection.data"
    store = JobStore(data_dir)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1})
    store.save(job)
    started = data_dir / "started.txt"
    owner = _start_driver(data_dir, job.id, hold_seconds=30, stage_partial=True)
    try:
        deadline = time.monotonic() + 10
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert started.exists(), "job owner did not enter the handler"
        current = store.load(job.id)
        assert current is not None
        assert current.status == JobStatus.RUNNING.value
        owner.kill()
        owner.wait(timeout=5)
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)

    recovery = _start_driver(data_dir, job.id)
    _finish(recovery)
    recovered = store.load(job.id)
    assert recovered is not None
    assert recovered.status == JobStatus.FAILED.value
    assert recovered.error == "interrupted"
    assert recovered.started_at == current.started_at
    assert recovered.ended_at is not None
    assert len(_invocations(data_dir)) == 1
    assert list(store.job_directory(job.id).glob(".result-*.tmp")) == []
    assert not (store.job_directory(job.id) / "result.json").exists()


def test_prune_skips_lock_owned_by_another_process(tmp_path: Path):
    data_dir = tmp_path / "collection.data"
    store = JobStore(data_dir)
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1})
    job.status = JobStatus.SUCCEEDED.value
    job.ended_at = "2000-01-01T00:00:00+00:00"
    store.save(job)
    lock_path = store.job_directory(job.id) / ".runner.lock"
    ready = data_dir / "prune-lock-ready.txt"
    script = (
        "from filelock import FileLock; "
        "from pathlib import Path; "
        "import sys, time; "
        "lock = FileLock(sys.argv[1]); lock.acquire(); "
        "Path(sys.argv[2]).write_text('ready', encoding='utf-8'); "
        "time.sleep(30)"
    )
    owner = subprocess.Popen([sys.executable, "-c", script, str(lock_path), str(ready)])
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and owner.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists(), "another process did not acquire the job claim"
        report = store.prune(retention_days=0, apply=True)
        assert report["deleted"] == []
        assert {item["job_id"] for item in report["skipped"]} == {job.id}
        assert store.load(job.id) is not None
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.wait(timeout=5)

    report = store.prune(retention_days=0, apply=True)
    assert {item["job_id"] for item in report["deleted"]} == {job.id}
    assert store.load(job.id) is None
