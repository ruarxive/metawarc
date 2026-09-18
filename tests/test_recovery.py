"""Recovery-path tests: doctor, rebind, retention, and no-op ingestion runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from metawarc.errors import WorkspaceError
from metawarc.ingestion import IncrementalIngestor
from metawarc.workspace import Workspace


def test_doctor_reports_missing_source_and_rebind_restores_it(indexed_workspace, tmp_path: Path):
    database, source = indexed_workspace
    moved = tmp_path / "relocated.warc"
    source.rename(moved)
    with Workspace(database, read_only=True, create=False) as workspace:
        report = workspace.doctor()
    issue = next(item for item in report.issues if item.code == "source-missing")
    assert issue.severity == "error"
    archive_id = issue.archive_id
    with Workspace(database, create=False) as workspace:
        workspace.rebind_archive(archive_id, moved)
    with Workspace(database, read_only=True, create=False) as workspace:
        assert not [item for item in workspace.doctor().issues if item.code == "source-missing"]


def test_rebind_rejects_unrelated_source_without_force(indexed_workspace, warc_factory):
    database, _ = indexed_workspace
    with Workspace(database, read_only=True, create=False) as workspace:
        archive_id = workspace.list_archives()[0]["id"]
    impostor = warc_factory("impostor.warc", [{"id": "<urn:uuid:other>", "payload": b"different"}])
    with Workspace(database, create=False) as workspace, pytest.raises(WorkspaceError):
        workspace.rebind_archive(archive_id, impostor)
    with Workspace(database, create=False) as workspace:
        workspace.rebind_archive(archive_id, impostor, force=True)
        assert workspace.get_archive(archive_id)["source_path"] == str(impostor.resolve())


def test_doctor_reports_corrupt_active_sidecar(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(database, create=False) as workspace:
        sidecar = workspace.active_sidecars("records")[0]
        path = workspace.resolve_path(sidecar["path"])
        path.write_bytes(b"not a parquet file at all")
        report = workspace.doctor()
    issue = next(item for item in report.issues if item.code == "sidecar-corrupt")
    assert issue.severity == "error"
    assert issue.archive_id == sidecar["archive_id"]


def test_doctor_reports_missing_sidecar(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(database, create=False) as workspace:
        sidecar = workspace.active_sidecars("records")[0]
        workspace.resolve_path(sidecar["path"]).unlink()
        report = workspace.doctor()
    issue = next(item for item in report.issues if item.code == "sidecar-missing")
    assert issue.severity == "error"


def test_retention_cleanup_rejects_negative_days(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(database, create=False) as workspace, pytest.raises(WorkspaceError):
        workspace.cleanup_retired(retention_days=-1)


def test_ingest_with_no_work_records_completed_run(indexed_workspace):
    database, source = indexed_workspace
    plan, summary = IncrementalIngestor().ingest(
        [source], dbfile=str(database), silent=True, digest_fingerprint=True
    )
    assert summary is None
    assert all(item.action == "unchanged" for item in plan.actions)
    with Workspace(database, read_only=True, create=False) as workspace:
        runs = workspace.con.execute(
            "SELECT operation, status FROM runs ORDER BY ended_at"
        ).fetchall()
    assert runs[-1] == ("ingest", "complete")


def test_ingest_missing_source_is_planned_as_conflict(warc_factory, tmp_path: Path):
    missing = tmp_path / "missing.warc"
    plan, summary = IncrementalIngestor().ingest(
        [missing], dbfile=str(tmp_path / "new.db"), silent=True
    )
    assert summary is None
    assert plan.actions[0].action == "conflict"
    assert "not found" in plan.actions[0].reason
