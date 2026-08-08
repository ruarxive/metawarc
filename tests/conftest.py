from __future__ import annotations

import gzip
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter


def build_warc(
    path: Path,
    records: list[dict[str, Any]],
    *,
    compressed: bool = False,
) -> Path:
    """Create deterministic small WARC fixtures without checked-in binaries."""
    with path.open("wb") as output:
        writer = WARCWriter(output, gzip=compressed)
        for index, item in enumerate(records):
            payload = item.get("payload", b"")
            record_type = item.get("type", "response")
            headers = None
            if record_type == "response":
                response_headers = list(item.get("headers") or [])
                if not item.get("omit_content_type"):
                    response_headers.insert(0, ("Content-Type", item.get("mime", "text/plain")))
                if not item.get("omit_content_length"):
                    response_headers.append(("Content-Length", str(len(payload))))
                headers = StatusAndHeaders(
                    item.get("status", "200 OK"),
                    response_headers,
                    protocol="HTTP/1.1",
                )
            record = writer.create_warc_record(
                item.get("url", f"https://example.test/{index}"),
                record_type,
                payload=BytesIO(payload),
                http_headers=headers,
                warc_headers_dict={
                    **(item.get("warc_headers") or {}),
                    "WARC-Record-ID": item.get(
                        "id", f"<urn:uuid:00000000-0000-0000-0000-{index:012d}>"
                    ),
                },
            )
            writer.write_record(record)
            record.raw_stream.close()
    return path


@pytest.fixture
def warc_factory(tmp_path: Path):
    def factory(
        name: str = "sample.warc",
        records: list[dict[str, Any]] | None = None,
        *,
        compressed: bool | None = None,
    ) -> Path:
        selected = records or [
            {
                "id": "<urn:uuid:alpha>",
                "url": "https://example.test/index.html",
                "mime": "text/html; charset=UTF-8",
                "payload": b'<html><a href="/about#team">About</a></html>',
            },
            {
                "id": "<urn:uuid:beta>",
                "url": "https://example.test/report.pdf",
                "mime": "application/pdf",
                "payload": b"%PDF-1.4\n% deliberately minimal corrupt fixture\n",
            },
        ]
        return build_warc(
            tmp_path / name,
            selected,
            compressed=name.endswith(".gz") if compressed is None else compressed,
        )

    return factory


@pytest.fixture
def indexed_workspace(tmp_path: Path, warc_factory):
    from metawarc.cmds.indexer import Indexer

    source = warc_factory()
    database = tmp_path / "collection.db"
    summary = Indexer(batch_size=1).index_records(
        [source], str(database), silent=True, digest_fingerprint=True
    )
    assert summary.failed == 0
    return database, source


@pytest.fixture
def unreadable_gzip(tmp_path: Path) -> Path:
    path = tmp_path / "truncated.warc.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"WARC/1.0\r\nContent-Length: 100\r\n\r\nshort")
    raw = path.read_bytes()
    path.write_bytes(raw[:-5])
    return path
