"""End-to-end smoke test intended to run against an installed wheel."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter


def main() -> None:
    executable = Path(sys.executable).with_name("metawarc")
    if not executable.is_file():
        raise RuntimeError("installed metawarc executable was not found")
    with tempfile.TemporaryDirectory(prefix="metawarc-installed-smoke-") as raw_directory:
        directory = Path(raw_directory)
        source = directory / "smoke.warc"
        database = directory / "smoke.db"
        payload = b"installed artifact smoke"
        with source.open("wb") as output:
            writer = WARCWriter(output, gzip=False)
            headers = StatusAndHeaders(
                "200 OK",
                [("Content-Type", "text/plain"), ("Content-Length", str(len(payload)))],
                protocol="HTTP/1.1",
            )
            record = writer.create_warc_record(
                "https://example.test/smoke.txt",
                "response",
                payload=BytesIO(payload),
                http_headers=headers,
                warc_headers_dict={"WARC-Record-ID": "<urn:uuid:installed-smoke>"},
            )
            writer.write_record(record)
            record.raw_stream.close()
        subprocess.run(
            [
                str(executable),
                "index",
                str(source),
                "--dbfile",
                str(database),
                "--silent",
                "--output-format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        listed = subprocess.run(
            [
                str(executable),
                "catalog",
                "--dbfile",
                str(database),
                "--output-format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        catalog = json.loads(listed.stdout)
        if catalog["archives"][0]["num_records"] != 1:
            raise RuntimeError("installed artifact did not index and query the fixture")


if __name__ == "__main__":
    main()
