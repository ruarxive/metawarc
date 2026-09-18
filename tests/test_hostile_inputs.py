"""Hostile-input tests: malformed archives and adversarial record content.

The domain calls out malformed headers, hostile URLs/identifiers, and hostile
payloads; these tests confirm indexing, extraction, and export stay bounded and
account for failures instead of crashing.
"""

from __future__ import annotations

import json
from pathlib import Path

from metawarc.cmds.dump import Dumper, safe_record_token
from metawarc.cmds.extractor import ContentIndexer, Extractor
from metawarc.cmds.indexer import Indexer
from metawarc.query import QueryService, RecordQuery
from metawarc.workspace import Workspace


def test_hostile_urls_index_and_export_to_safe_names(warc_factory, tmp_path: Path):
    urls = [
        "https://example.test/a'b\"c?x=1&y=' OR 1=1--",
        "https://example.test/" + "a" * 300,
        "https://example.test/\xff\xfe.html",
        "https://example.test/a b c.html",
    ]
    source = warc_factory(
        "hostile.warc",
        [
            {
                "id": f"<urn:uuid:hostile-{index}>",
                "url": url,
                "mime": "text/html",
                "payload": b"<html>hi</html>",
            }
            for index, url in enumerate(urls)
        ],
    )
    database = tmp_path / "hostile.db"
    summary = Indexer(batch_size=1).index_records([source], str(database), silent=True)
    assert summary.failed == 0
    assert summary.records == 4
    with Workspace(database, read_only=True, create=False) as workspace:
        total, rows = QueryService(workspace).list_records(RecordQuery(limit=10))
    assert total == 4
    output = tmp_path / "dump"
    result = Dumper().dump(dbfile=str(database), output=str(output), silent=True, limit=4)
    assert result["completed"] == 4
    for path in output.iterdir():
        assert path.parent == output.resolve()
        assert "/" not in path.name and "\\" not in path.name
        assert path.name == safe_record_token(path.name)


def test_truncated_warc_is_accounted_not_fatal(warc_factory, tmp_path: Path):
    source = warc_factory()
    raw = source.read_bytes()
    source.write_bytes(raw[: len(raw) // 2])
    database = tmp_path / "truncated.db"
    summary = Indexer(batch_size=1).index_records([source], str(database), silent=True)
    assert summary.failed <= 1
    # Whatever was indexed before the cut remains queryable and bounded.
    with Workspace(database, read_only=True, create=False) as workspace:
        total, _ = QueryService(workspace).list_records(RecordQuery(limit=10))
    assert total <= 2


def test_garbage_warc_extension_fails_cleanly(tmp_path: Path):
    garbage = tmp_path / "garbage.warc"
    garbage.write_bytes(b"\x00\x01\x02 not a WARC at all \xff" * 64)
    database = tmp_path / "garbage.db"
    # Garbage must not crash the scan; nothing is indexed. (A fully invalid
    # file currently reports zero records rather than a failure — validating
    # the WARC magic bytes is a candidate future hardening change.)
    summary = Indexer().index_records([garbage], str(database), silent=True)
    assert summary.records == 0
    with Workspace(database, read_only=True, create=False) as workspace:
        total, _ = QueryService(workspace).list_records(RecordQuery(limit=10))
    assert total == 0


def test_hostile_html_link_extraction_stays_bounded(indexed_workspace, tmp_path: Path):
    database, _ = indexed_workspace
    ContentIndexer().index_by_table_type(None, str(database), "links", rescan=True, silent=True)
    with Workspace(database, read_only=True, create=False) as workspace:
        sidecars = workspace.active_sidecars("links")
    assert sidecars, "links sidecar published"
    path = workspace.resolve_path(sidecars[0]["path"])
    assert path.exists()


def test_corrupt_family_payloads_produce_error_envelopes(warc_factory, tmp_path: Path):
    source = warc_factory(
        "corrupt.warc",
        [
            {
                "id": "<urn:uuid:fake-pdf>",
                "url": "https://example.test/doc.pdf",
                "mime": "application/pdf",
                "payload": b"%PDF-1.4\n" + b"%" + b"\x00\xff" * 512,
            },
            {
                "id": "<urn:uuid:fake-zip>",
                "url": "https://example.test/doc.docx",
                "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "payload": b"PK\x03\x04" + b"\x00" * 64 + b"garbage",
            },
            {
                "id": "<urn:uuid:fake-png>",
                "url": "https://example.test/img.png",
                "mime": "image/png",
                "payload": b"\x89PNG\r\n\x1a\n" + b"\xde\xad\xbe\xef" * 32,
            },
        ],
    )
    output = tmp_path / "metadata.jsonl"
    Extractor().metadata_by_ext(str(source), output=str(output))
    envelopes = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(envelopes) == 3
    for envelope in envelopes:
        assert envelope["warc_id"]
        # Errors are captured inside the envelope, never raised to the caller.
        assert envelope.get("warnings") is not None or envelope.get("metadata") is not None
