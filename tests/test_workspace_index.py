from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest

from metawarc.cmds.indexer import Indexer
from metawarc.errors import SchemaCompatibilityError
from metawarc.ingestion import IncrementalIngestor
from metawarc.query import QueryService, RecordQuery
from metawarc.workspace import Workspace, WorkspaceLockedError


@pytest.mark.parametrize("name,silent", [("plain.warc", False), ("compressed.warc.gz", True)])
def test_index_compressed_uncompressed_and_silent(
    warc_factory, tmp_path: Path, name: str, silent: bool
):
    source = warc_factory(name)
    database = tmp_path / f"{name}.db"
    summary = Indexer(batch_size=1).index_records([source], str(database), silent=silent)
    assert summary.processed == 1
    assert summary.records == 2
    with Workspace(database, read_only=True, create=False) as workspace:
        total, records = QueryService(workspace).list_records(RecordQuery(limit=10))
        assert total == 2
        assert {item["warc_id"] for item in records} == {"urn:uuid:alpha", "urn:uuid:beta"}
        for sidecar in workspace.active_sidecars("records"):
            assert pq.ParquetFile(workspace.resolve_path(sidecar["path"])).metadata.num_rows == 2


def test_update_is_idempotent_and_preserves_archive_id(indexed_workspace, warc_factory):
    database, source = indexed_workspace
    with Workspace(database, read_only=True, create=False) as workspace:
        original = workspace.list_archives()[0]
        original_revision = workspace.revision()

    skipped = Indexer().index_records([source], str(database), silent=True, digest_fingerprint=True)
    assert skipped.skipped == 1
    assert skipped.revision == original_revision

    records = [
        {"id": "<urn:uuid:alpha>", "url": "https://example.test/a", "payload": b"a"},
        {"id": "<urn:uuid:gamma>", "url": "https://example.test/g", "payload": b"g"},
    ]
    from conftest import build_warc

    build_warc(source, records)
    os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1_000_000))
    updated = Indexer(batch_size=1).index_records([source], str(database), silent=True)
    assert updated.processed == 1
    with Workspace(database, read_only=True, create=False) as workspace:
        archive = workspace.list_archives()[0]
        assert archive["id"] == original["id"]
        assert workspace.revision() == original_revision + 1
        assert len(workspace.active_sidecars("records")) == 1
        retired = workspace.con.execute(
            "SELECT COUNT(*) FROM sidecars WHERE kind='records' AND status='retired'"
        ).fetchone()[0]
        assert retired == 1


def test_incremental_plan_missing_moved_and_rebind(indexed_workspace, tmp_path: Path):
    database, source = indexed_workspace
    moved = tmp_path / "moved.warc"
    source.rename(moved)
    plan = IncrementalIngestor().plan([moved], dbfile=str(database), digest_fingerprint=True)
    action = plan.actions[0]
    assert action.action == "moved-candidate"
    assert action.archive_id
    with Workspace(database, create=False) as workspace:
        workspace.rebind_archive(action.archive_id, moved)
        assert workspace.get_archive(action.archive_id)["source_path"] == str(moved.resolve())


def test_empty_no_response_and_truncated_inputs(warc_factory, unreadable_gzip, tmp_path: Path):
    empty = tmp_path / "empty.warc"
    empty.touch()
    resource = warc_factory(
        "resource.warc",
        [{"type": "resource", "payload": b"metadata", "url": "urn:test"}],
    )
    summary = Indexer().index_records(
        [empty, resource, unreadable_gzip], str(tmp_path / "odd.db"), silent=True
    )
    assert summary.sources == 3
    assert summary.records == 0
    assert summary.failed in {0, 1}


def test_missing_optional_headers_are_isolated(warc_factory, tmp_path: Path):
    source = warc_factory(
        "headers.warc",
        [
            {
                "id": "<urn:uuid:missing>",
                "payload": b"missing optional headers",
                "omit_content_type": True,
                "omit_content_length": True,
                "status": "malformed",
            },
            {"id": "<urn:uuid:valid>", "payload": b"valid"},
        ],
    )
    database = tmp_path / "headers.db"
    summary = Indexer(batch_size=1).index_records([source], str(database), silent=True)
    assert summary.records == 2
    with Workspace(database, read_only=True, create=False) as workspace:
        total, records = QueryService(workspace).list_records(RecordQuery(limit=10))
    assert total == 2
    missing = next(item for item in records if item["warc_id"] == "urn:uuid:missing")
    assert missing["content_type"] is None
    assert missing["status_code"] == 0


def test_duplicate_basenames_and_record_ids_remain_scoped(tmp_path: Path):
    from conftest import build_warc

    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()
    records = [{"id": "<urn:uuid:shared>", "payload": b"same id"}]
    first = build_warc(first_dir / "same.warc", records)
    second = build_warc(second_dir / "same.warc", records)
    database = tmp_path / "duplicates.db"
    Indexer().index_records([first, second], str(database), silent=True)
    with Workspace(database, read_only=True, create=False) as workspace:
        archives = workspace.list_archives()
        assert len({archive["id"] for archive in archives}) == 2
        selected = QueryService(workspace).get_record(
            "urn:uuid:shared", archive_id=archives[1]["id"]
        )
        assert selected and selected["archive_id"] == archives[1]["id"]


def test_checkpoint_resume_after_interruption(monkeypatch, warc_factory, tmp_path: Path):
    source = warc_factory()
    database = tmp_path / "resume.db"
    original = Workspace.save_checkpoint
    calls = 0

    def interrupt_once(self, **kwargs):
        nonlocal calls
        original(self, **kwargs)
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt

    monkeypatch.setattr(Workspace, "save_checkpoint", interrupt_once)
    with pytest.raises(KeyboardInterrupt):
        Indexer(batch_size=1).index_records([source], str(database), silent=True, resume=True)
    monkeypatch.setattr(Workspace, "save_checkpoint", original)
    resumed = Indexer(batch_size=1).index_records([source], str(database), silent=True, resume=True)
    assert resumed.records == 2
    with Workspace(database, read_only=True, create=False) as workspace:
        total, _ = QueryService(workspace).list_records(RecordQuery(limit=10))
        assert total == 2


def test_second_writer_is_rejected_and_readers_continue(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(database, create=False) as first, first.writer_lock("first"):
        with (
            Workspace(database, create=False) as second,
            pytest.raises(WorkspaceLockedError),
            second.writer_lock("second"),
        ):
            pass
        with Workspace(database, read_only=True, create=False) as reader:
            assert reader.list_archives()


def test_doctor_reports_and_quarantines_orphan(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(database, create=False) as workspace:
        orphan = workspace.sidecar_root / "orphan.parquet"
        duckdb.connect().execute("COPY (SELECT 1 AS value) TO ? (FORMAT PARQUET)", [str(orphan)])
        dry = workspace.doctor(repair=True, dry_run=True)
        assert any(issue.code == "orphan-sidecar" for issue in dry.issues)
        assert orphan.exists()
        applied = workspace.doctor(repair=True, dry_run=False)
        assert applied.actions
        assert not orphan.exists()


def test_retention_cleanup_preserves_active_sidecar(indexed_workspace):
    database, source = indexed_workspace
    Indexer().index_records([source], str(database), mode="force", silent=True)
    with Workspace(database, create=False) as workspace:
        active = workspace.active_sidecars("records")[0]
        preview = workspace.cleanup_retired(retention_days=0, dry_run=True)
        assert preview["candidates"]
        assert workspace.resolve_path(active["path"]).exists()
        applied = workspace.cleanup_retired(retention_days=0, dry_run=False)
        assert applied["actions"]
        assert workspace.resolve_path(active["path"]).exists()


@pytest.mark.parametrize("layout", ["1.2", "1.3"])
def test_legacy_catalog_migration_creates_backup(tmp_path: Path, warc_factory, layout: str):
    source = warc_factory()
    sidecar = tmp_path / "legacy_records.parquet"
    duckdb.connect().execute("COPY (SELECT 'x' AS warc_id) TO ? (FORMAT PARQUET)", [str(sidecar)])
    database = tmp_path / "legacy.db"
    connection = duckdb.connect(str(database))
    if layout == "1.2":
        connection.execute(
            "CREATE TABLE files(filename VARCHAR, filesize BIGINT, num_records BIGINT)"
        )
        connection.execute(
            "INSERT INTO files VALUES (?, ?, 1)", [str(source), source.stat().st_size]
        )
        connection.execute(
            "CREATE TABLE tables(warcfile VARCHAR, path VARCHAR, type VARCHAR, num_items BIGINT)"
        )
        connection.execute(
            "INSERT INTO tables VALUES (?, ?, 'records', 1)", [str(source), str(sidecar)]
        )
        expected_id = None
    else:
        connection.execute(
            "CREATE TABLE files(id VARCHAR, fullpath VARCHAR, filename VARCHAR, "
            "filesize BIGINT, num_records BIGINT)"
        )
        connection.execute(
            "INSERT INTO files VALUES ('legacy-id', ?, ?, ?, 1)",
            [str(source), source.name, source.stat().st_size],
        )
        connection.execute(
            "CREATE TABLE tables(wf_id VARCHAR, wf_filename VARCHAR, path VARCHAR, "
            "type VARCHAR, num_items BIGINT)"
        )
        connection.execute(
            "INSERT INTO tables VALUES ('legacy-id', ?, ?, 'records', 1)",
            [str(source), str(sidecar)],
        )
        expected_id = "legacy-id"
    connection.close()
    with Workspace(database, migrate=True) as workspace:
        archives = workspace.list_archives()
        assert len(archives) == 1
        if expected_id:
            assert archives[0]["id"] == expected_id
    assert database.with_suffix(database.suffix + ".legacy.bak").exists()


def test_failed_legacy_migration_restores_original(tmp_path: Path):
    database = tmp_path / "broken-legacy.db"
    connection = duckdb.connect(str(database))
    connection.execute("CREATE TABLE files(filename VARCHAR)")
    connection.execute("INSERT INTO files VALUES ('missing.warc')")
    connection.execute("CREATE TABLE tables(unknown VARCHAR)")
    connection.close()
    with pytest.raises(SchemaCompatibilityError):
        Workspace(database, migrate=True)
    connection = duckdb.connect(str(database))
    assert {row[0] for row in connection.execute("SHOW TABLES").fetchall()} == {
        "files",
        "tables",
    }
    connection.close()
