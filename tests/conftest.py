"""Shared test fixtures."""

from io import BytesIO
from pathlib import Path

import pytest
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter

from metawarc.cmds.indexer import Indexer


def write_sample_warc(path: Path) -> None:
    gzip = str(path).endswith(".gz")
    with open(path, "wb") as out:
        writer = WARCWriter(out, gzip=gzip)
        headers = StatusAndHeaders(
            "200 OK",
            [("Content-Type", "text/html"), ("Content-Length", "26")],
            protocol="HTTP/1.0",
        )
        record = writer.create_warc_record(
            "http://example.com/page.html",
            "response",
            payload=BytesIO(b"<html><body>hi</body></html>"),
            http_headers=headers,
        )
        writer.write_record(record)

        pdf_headers = StatusAndHeaders(
            "200 OK",
            [("Content-Type", "application/pdf"), ("Content-Length", "4")],
            protocol="HTTP/1.0",
        )
        pdf_record = writer.create_warc_record(
            "http://example.com/doc.pdf",
            "response",
            payload=BytesIO(b"%PDF"),
            http_headers=pdf_headers,
        )
        writer.write_record(pdf_record)


@pytest.fixture
def indexed_workspace(tmp_path, monkeypatch):
    """Create a WARC file, index it, and run tests inside tmp_path."""
    monkeypatch.chdir(tmp_path)
    warc_path = tmp_path / "sample.warc.gz"
    db_path = tmp_path / "warcindex.db"
    write_sample_warc(warc_path)
    indexer = Indexer()
    indexer.index_records([str(warc_path)], str(db_path), ["records", "headers"], silent=True)
    return {
        "tmpdir": tmp_path,
        "warc": warc_path,
        "db": db_path,
        "data_dir": tmp_path / "data",
    }
