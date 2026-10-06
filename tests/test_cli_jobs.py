"""CLI tests for the ``metawarc jobs`` subcommand group."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from metawarc.cli_jobs import jobs_group
from metawarc.indexer import Indexer
from metawarc.jobs import JobStatus


def _setup_workspace(tmp_path: Path, warc_factory) -> Path:
    source = warc_factory()
    db_path = tmp_path / "collection.db"
    data_dir = tmp_path / "collection.data"
    Indexer(batch_size=1).index_records(
        [str(source)], str(db_path), data_dir=str(data_dir), silent=True
    )
    return db_path


def _invoke(args: list[str], db_path: Path) -> tuple[int, str]:
    runner = CliRunner()
    result = runner.invoke(
        jobs_group,
        ["--dbfile", str(db_path)] + args,
        catch_exceptions=False,
    )
    return result.exit_code, result.output


def test_cli_jobs_list_empty(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, output = _invoke(["list"], db_path)
    assert exit_code == 0
    assert json.loads(output) == []


def test_cli_jobs_submit_creates_pending(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, output = _invoke(
        ["submit", "--format", "json", "--limit", "5", "--mimes", "text/html"],
        db_path,
    )
    assert exit_code == 0
    job_id = output.strip()
    assert job_id.startswith("job-")

    exit_code, output = _invoke(["get", job_id], db_path)
    assert exit_code == 0
    body = json.loads(output)
    assert body["id"] == job_id
    assert body["kind"] == "export-records"
    assert body["input"]["format"] == "json"


def test_cli_jobs_get_unknown(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, _ = _invoke(["get", "job-does-not-exist"], db_path)
    assert exit_code == 1


def test_cli_jobs_submit_rejects_oversized_limit(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, _ = _invoke(["submit", "--limit", "10000000"], db_path)
    assert exit_code == 2


def test_cli_jobs_cancel_unknown(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, _ = _invoke(["cancel", "job-does-not-exist"], db_path)
    assert exit_code == 1


def test_cli_jobs_cancel_succeeded(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, output = _invoke(["submit", "--format", "json", "--limit", "1"], db_path)
    job_id = output.strip()

    # Manually mark succeeded to simulate terminal state.
    from metawarc.jobs import JobStore

    store = JobStore(str(db_path.with_suffix(".data")))
    job = store.load(job_id)
    job.status = JobStatus.SUCCEEDED.value
    store.save(job)

    exit_code, output = _invoke(["cancel", job_id], db_path)
    assert exit_code != 0
    assert "already succeeded" in output


def test_cli_jobs_wait_timeout(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, output = _invoke(["submit", "--format", "json", "--limit", "1"], db_path)
    job_id = output.strip()

    # Submit a wait with a 1s timeout.
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        jobs_group,
        ["--dbfile", str(db_path), "wait", job_id, "--timeout", "1", "--poll-seconds", "0.5"],
        catch_exceptions=False,
    )
    # Exit 124 == timed out
    assert result.exit_code in {0, 124}


def test_cli_jobs_list_filters_by_status(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, output = _invoke(["submit"], db_path)
    job_id = output.strip()

    from metawarc.jobs import JobStore

    store = JobStore(str(db_path.with_suffix(".data")))
    job = store.load(job_id)
    job.status = JobStatus.SUCCEEDED.value
    store.save(job)

    exit_code, output = _invoke(["list", "--status", "succeeded"], db_path)
    assert exit_code == 0
    rows = json.loads(output)
    assert any(item["id"] == job_id for item in rows)

    exit_code, output = _invoke(["list", "--status", "cancelled"], db_path)
    assert exit_code == 0
    assert json.loads(output) == []


def test_cli_jobs_list_rejects_unknown_status(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, _ = _invoke(["list", "--status", "bogus"], db_path)
    assert exit_code == 2


def test_cli_jobs_submit_unknown_kind(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, _ = _invoke(["submit", "--kind", "nonexistent-kind"], db_path)
    assert exit_code == 2


def test_cli_jobs_submit_bad_format(tmp_path: Path, warc_factory):
    db_path = _setup_workspace(tmp_path, warc_factory)
    exit_code, _ = _invoke(["submit", "--format", "yaml"], db_path)
    assert exit_code == 2
