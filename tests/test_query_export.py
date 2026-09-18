from __future__ import annotations

import json
from pathlib import Path

import pytest

from metawarc.cmds.dump import Dumper, safe_output_path, safe_record_token
from metawarc.errors import QueryValidationError, WorkspaceError
from metawarc.query import QueryService, RecordQuery
from metawarc.workspace import Workspace


def test_typed_filters_are_bound_and_pagination_is_deterministic(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(database, read_only=True, create=False) as workspace:
        service = QueryService(workspace)
        hostile = "' OR 1=1 --"
        total, rows = service.list_records(RecordQuery(url_pattern=hostile, limit=10))
        assert total == 0
        assert rows == []
        first = service.list_records(RecordQuery(limit=1))[1][0]
        again = service.list_records(RecordQuery(limit=1))[1][0]
        second = service.list_records(RecordQuery(offset=1, limit=1))[1][0]
        assert first["warc_id"] == again["warc_id"]
        assert first["warc_id"] != second["warc_id"]
        with pytest.raises(QueryValidationError):
            service.list_records(RecordQuery(unsafe_where="1=1; DROP TABLE archives", limit=10))


def test_all_typed_filter_fields(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(database, read_only=True, create=False) as workspace:
        archive_id = workspace.list_archives()[0]["id"]
        query = RecordQuery(
            archive_ids=(archive_id,),
            mimes=("text/html",),
            exts=("html",),
            host_pattern="EXAMPLE",
            status_min=200,
            status_max=299,
            size_min=1,
            size_max=1000,
            sort_by="url",
            descending=True,
            limit=10,
        )
        total, rows = QueryService(workspace).list_records(query)
        assert total == 1
        assert rows[0]["warc_id"] == "urn:uuid:alpha"


@pytest.mark.parametrize(
    "value",
    ["../../etc/passwd", "..", "/absolute/path", "CON", "bad:name?*", "a/b\\c"],
)
def test_hostile_export_names_stay_below_output(tmp_path: Path, value: str):
    output = tmp_path / "out"
    output.mkdir()
    record = {"warc_id": value, "ext": "txt", "content_type": "text/plain"}
    path = safe_output_path(output, record)
    assert path.parent == output
    assert "/" not in path.name
    assert "\\" not in path.name
    assert safe_record_token(value) not in {"", ".", ".."}


def test_dump_streams_manifest_checksums_and_avoids_overwrite(indexed_workspace, tmp_path: Path):
    database, _ = indexed_workspace
    output = tmp_path / "dump"
    first = Dumper().dump(dbfile=str(database), output=str(output), silent=True, limit=2)
    second = Dumper().dump(dbfile=str(database), output=str(output), silent=True, limit=2)
    assert first["completed"] == second["completed"] == 2
    assert first["manifest"] != second["manifest"]
    paths = []
    for manifest in (first["manifest"], second["manifest"]):
        entries = [json.loads(line) for line in Path(manifest).read_text().splitlines()]
        assert all(len(item["sha256"]) == 64 for item in entries)
        paths.extend(item["output_path"] for item in entries)
    assert len(paths) == len(set(paths))
    assert not list(output.glob("*.part"))


def test_export_byte_limit_cleans_partial_files(indexed_workspace, tmp_path: Path):
    database, _ = indexed_workspace
    output = tmp_path / "bounded"
    result = Dumper().dump(
        dbfile=str(database), output=str(output), silent=True, limit=2, max_bytes=1
    )
    assert result["completed"] == 0
    assert result["failed"] + result["skipped"] >= 1
    assert not list(output.glob("*.part"))


def test_get_refuses_existing_output(indexed_workspace, tmp_path: Path):
    database, _ = indexed_workspace
    target = tmp_path / "already.txt"
    target.write_text("keep")
    with pytest.raises(WorkspaceError):
        Dumper().get_file("urn:uuid:alpha", str(database), output=str(target), silent=True)
    assert target.read_text() == "keep"


def test_dump_records_failed_payloads_in_manifest_without_part_files(
    indexed_workspace, tmp_path: Path
):
    database, source = indexed_workspace
    source.unlink()
    output = tmp_path / "gone-source"
    result = Dumper().dump(dbfile=str(database), output=str(output), silent=True, limit=2)
    assert result["completed"] == 0
    assert result["failed"] == 2
    entries = [json.loads(line) for line in Path(result["manifest"]).read_text().splitlines()]
    assert all(item["status"] == "failed" for item in entries)
    assert all("source not found" in item["error"] for item in entries)
    assert not list(output.glob("*.part"))


def test_dump_declared_byte_limit_skips_before_writing(indexed_workspace, tmp_path: Path):
    database, _ = indexed_workspace
    output = tmp_path / "declared-limit"
    result = Dumper().dump(
        dbfile=str(database), output=str(output), silent=True, limit=2, max_bytes=1
    )
    assert result["completed"] == 0
    assert result["skipped"] == 1
    entries = [json.loads(line) for line in Path(result["manifest"]).read_text().splitlines()]
    assert entries[0]["status"] == "skipped"
    assert "byte limit" in entries[0]["error"]
    assert [item.name for item in output.iterdir()] == ["manifest.jsonl"]


def test_dump_rejects_nonpositive_limit(indexed_workspace, tmp_path: Path):
    database, _ = indexed_workspace
    with pytest.raises(QueryValidationError):
        Dumper().dump(dbfile=str(database), output=str(tmp_path / "x"), silent=True, limit=0)


def test_safe_output_path_deduplicates_reserved_collisions(tmp_path: Path):
    output = tmp_path / "out"
    output.mkdir()
    record = {"warc_id": "<urn:uuid:dup>", "ext": "txt", "content_type": "text/plain"}
    first = safe_output_path(output, record)
    assert first.name == "urn_uuid_dup.txt"
    # An on-disk collision gets a counter suffix.
    first.touch()
    second = safe_output_path(output, record)
    assert second.name == "urn_uuid_dup-1.txt"
    # A collision reserved earlier in the same run also gets a counter suffix.
    third = safe_output_path(output, record, reserved={first})
    assert third.name == "urn_uuid_dup-1.txt"


def test_listfiles_writes_csv_and_jsonl_and_refuses_overwrite(indexed_workspace, tmp_path: Path):
    database, _ = indexed_workspace
    dumper = Dumper()
    csv_path = tmp_path / "rows.csv"
    dumper.listfiles(dbfile=str(database), output=str(csv_path), silent=True, output_format="csv")
    assert csv_path.read_text().splitlines()[0].startswith("archive_id,")
    with pytest.raises(WorkspaceError):
        dumper.listfiles(
            dbfile=str(database), output=str(csv_path), silent=True, output_format="csv"
        )
    jsonl_path = tmp_path / "rows.jsonl"
    rows = dumper.listfiles(
        dbfile=str(database), output=str(jsonl_path), silent=True, output_format="jsonl"
    )
    assert len(jsonl_path.read_text().splitlines()) == len(rows)
    with pytest.raises(QueryValidationError):
        dumper.listfiles(
            dbfile=str(database),
            output=str(tmp_path / "rows.xml"),
            silent=True,
            output_format="xml",
        )


def test_get_unknown_record_returns_none(indexed_workspace):
    database, _ = indexed_workspace
    assert Dumper().get_file("urn:uuid:unknown", str(database), silent=True) is None
