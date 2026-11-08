"""Operational and documentation smoke tests against an installed wheel."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter


def _write_warc(path: Path) -> None:
    records = [
        (
            "https://example.com/",
            "text/html; charset=UTF-8",
            b"<html><a href='/about'>About</a>Welcome to the museum of modern art. API press release data breach.</html>",
            "<urn:uuid:html>",
        ),
        (
            "https://example.com/reports/report.pdf",
            "application/pdf",
            b"%PDF-1.4\n% smoke fixture\n",
            "<urn:uuid:pdf>",
        ),
        (
            "https://example.com/about",
            "text/plain",
            b"Welcome to the museum API",
            "<urn:uuid:text>",
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output:
        writer = WARCWriter(output, gzip=path.suffix == ".gz")
        for url, mime, payload, record_id in records:
            headers = StatusAndHeaders(
                "200 OK",
                [("Content-Type", mime), ("Content-Length", str(len(payload)))],
                protocol="HTTP/1.1",
            )
            record = writer.create_warc_record(
                url,
                "response",
                payload=BytesIO(payload),
                http_headers=headers,
                warc_headers_dict={"WARC-Record-ID": record_id},
            )
            writer.write_record(record)
            record.raw_stream.close()


class InstalledSmoke:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.executable = Path(sys.executable).with_name("metawarc")
        self.database = directory / "collection.db"
        self.data_dir = directory / "collection.data"
        self.executed: set[tuple[str, ...]] = set()
        self.env = dict(os.environ)
        self.env["METAWARC_API_TOKEN"] = "installed-smoke-token"
        if not self.executable.is_file():
            raise RuntimeError("installed metawarc executable was not found")

    @staticmethod
    def _key(arguments: list[str]) -> tuple[str, ...]:
        if arguments[0] == "jobs" and len(arguments) > 3 and arguments[1] == "--dbfile":
            return "jobs", arguments[3]
        if arguments[0] in {"jobs", "analyze"}:
            return tuple(arguments[:2])
        return (arguments[0],)

    def run_jobs(self, *arguments: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        return self.run("jobs", "--dbfile", "collection.db", *arguments, timeout=timeout)

    def run(self, *arguments: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
        self.executed.add(self._key(list(arguments)))
        try:
            return subprocess.run(
                [str(self.executable), *arguments],
                cwd=self.directory,
                env=self.env,
                check=True,
                capture_output=True,
                text=True,
                input="",
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"command failed: {' '.join(arguments)}\nstdout:\n{exc.stdout}\nstderr:\n{exc.stderr}"
            ) from exc

    def core_workflow(self) -> None:
        _write_warc(self.directory / "collection.warc.gz")
        _write_warc(self.directory / "archives" / "collection.warc.gz")
        _write_warc(self.directory / "archives" / "new-batch" / "collection.warc.gz")
        self.run("index", "collection.warc.gz", "--dbfile", "collection.db", "--resume")
        self.run("index", "archives/**/*.warc*", "--dbfile", "collection.db", "--resume")
        self.run(
            "index",
            "archives",
            "--dbfile",
            "collection.db",
            "--resume",
            "--hash-payloads",
        )
        catalog = self.run("catalog", "--dbfile", "collection.db", "--output-format", "json")
        archives = json.loads(catalog.stdout)["archives"]
        if not archives or sum(item["num_records"] for item in archives) < 3:
            raise RuntimeError("installed artifact did not index the documentation fixtures")
        self.archive_id = archives[0]["id"]
        self.run("stats", "--dbfile", "collection.db", "--mode", "mimes")
        self.run("stats", "--dbfile", "collection.db", "--mode", "exts", "--output-format", "json")
        self.run(
            "list-files", "--dbfile", "collection.db", "--mimes", "application/pdf", "--limit", "50"
        )
        self.run(
            "list-files",
            "--dbfile",
            "collection.db",
            "--host-pattern",
            "example.com",
            "--date-from",
            "2020-01-01",
        )
        self.run(
            "dump",
            "--dbfile",
            "collection.db",
            "--exts",
            "pdf",
            "--limit",
            "100",
            "--output",
            "exported",
        )
        self.run(
            "dump",
            "--dbfile",
            "collection.db",
            "--url-pattern",
            "/reports/",
            "--output",
            "filtered-export",
        )
        self.run("get", "urn:uuid:pdf", "--dbfile", "collection.db", "--output", "one.pdf")
        self.run("index-content", "--dbfile", "collection.db", "--type", "links", "--type", "pdfs")
        self.run(
            "index-content",
            "--dbfile",
            "collection.db",
            "--type",
            "images",
            "--type",
            "videos",
            "--type",
            "audio",
            "--type",
            "fonts",
        )
        self.run(
            "index-content",
            "--dbfile",
            "collection.db",
            "--type",
            "ooxmldocs",
            "--rescan",
        )
        self.run("index-content", "--dbfile", "collection.db", "--text")
        self.run("index-content", "--dbfile", "collection.db", "--text", "--rescan")
        for phrase, limit in (
            ("Welcome to the museum of modern art", "50"),
            ("Welcome to the museum", "25"),
            ("API", "10"),
            ("data breach", "25"),
            ("press release", "50"),
        ):
            result = self.run("search", phrase, "--dbfile", "collection.db", "--limit", limit)
            if phrase != "data breach" and "urn:uuid:" not in result.stdout:
                raise RuntimeError(f"documentation search returned no match for {phrase!r}")
        self.run("analyze", "summary", "--dbfile", "collection.db", "--output", "summary.json")
        self.run("analyze", "metadata", "--dbfile", "collection.db", "--type", "all", "--top", "20")
        self.run("analyze", "hashes", "--dbfile", "collection.db", "--resume")
        self.run(
            "analyze",
            "duplicates",
            "--dbfile",
            "collection.db",
            "--output",
            "duplicates.csv",
            "--output-format",
            "csv",
        )
        self.run(
            "analyze",
            "links",
            "--dbfile",
            "collection.db",
            "--output",
            "links.parquet",
            "--output-format",
            "parquet",
        )
        self.run(
            "analyze",
            "integrity",
            "--dbfile",
            "collection.db",
            "--deep",
            "--max-records",
            "1000",
        )
        self.run("ingest", "archives/**/*.warc*", "--dbfile", "collection.db", "--dry-run")
        self.run("ingest", "archives/**/*.warc*", "--dbfile", "collection.db", "--resume")
        self.run("doctor", "--dbfile", "collection.db")
        self.run(
            "export-cdxj",
            "--dbfile",
            "collection.db",
            "-o",
            "collection.cdxj",
            "--path-index",
            "paths.tsv",
        )

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    def _request(
        self, port: int, path: str, *, method: str = "GET", payload: dict | None = None
    ) -> tuple[int, bytes, dict[str, str]]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Authorization": "Bearer installed-smoke-token"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", data=body, headers=headers, method=method
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read(), dict(response.headers)

    @contextmanager
    def server(self, command: str, port: int) -> Iterator[None]:
        self.executed.add((command,))
        log_path = self.directory / f"{command}-{port}.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    str(self.executable),
                    command,
                    "--dbfile",
                    "collection.db",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=self.directory,
                env=self.env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                deadline = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"{command} exited early: {log_path.read_text()}")
                    try:
                        status, _, _ = self._request(port, "/health")
                        if status == 200:
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError(f"{command} did not start: {log_path.read_text()}")
                        time.sleep(0.1)
                yield
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def api_workflow(self) -> None:
        port = self._free_port()
        with self.server("serve", port):
            status, payload, _ = self._request(port, "/records/search?phrase=Welcome&limit=10")
            assert status == 200
            assert json.loads(payload)["total"] >= 1
            status, payload, _ = self._request(port, "/replay/sites")
            assert status == 200 and json.loads(payload)
            submitted = self.run_jobs(
                "submit",
                "--format",
                "csv",
                "--limit",
                "50000",
                "--mimes",
                "application/pdf",
                "--status-min",
                "200",
                "--status-max",
                "299",
                "--url-pattern",
                "/reports/",
                "--archive-ids",
                self.archive_id,
            )
            job_id = submitted.stdout.strip()
            finished = json.loads(
                self.run_jobs(
                    "wait",
                    job_id,
                    "--poll-seconds",
                    "0.1",
                    "--timeout",
                    "120",
                    "--progress",
                ).stdout
            )
            assert finished["status"] == "succeeded"
            self.run_jobs("list", "--status", "running", "--limit", "50")
            self.run_jobs("get", job_id)
            status, payload, _ = self._request(port, f"/jobs/{job_id}/result")
            metadata = json.loads(payload)
            assert status == 200 and "path" not in metadata
            status, content, _ = self._request(port, metadata["download_url"])
            assert status == 200 and content.startswith(b"archive_id")
            status, payload, _ = self._request(port, "/jobs/metrics?limit=1000")
            assert status == 200 and json.loads(payload)["included"] >= 1
            metrics = self.run_jobs("metrics", "--limit", "1000")
            assert json.loads(metrics.stdout)["included"] >= 1
            preview = self.run_jobs("prune", "--retention-days", "7")
            assert json.loads(preview.stdout)["dry_run"] is True
            applied = self.run_jobs("prune", "--retention-days", "0", "--apply")
            assert json.loads(applied.stdout)["dry_run"] is False
            remaining = self.run_jobs("metrics", "--limit", "1000")
            assert json.loads(remaining.stdout)["total"] == 0
            status, payload, _ = self._request(port, "/jobs/metrics?limit=1000")
            assert status == 200 and json.loads(payload)["total"] == 0
            from metawarc.jobs import Job, JobKind, JobStore

            pending = Job.new(JobKind.EXPORT_RECORDS, {"format": "json", "limit": 1})
            store = JobStore(self.data_dir)
            claim = store.claim(pending.id)
            claim.acquire(timeout=0)
            try:
                store.save(pending)
                cancelled = self.run_jobs("cancel", pending.id)
                assert json.loads(cancelled.stdout)["status"] == "cancelled"
            finally:
                claim.release()
        replay_port = self._free_port()
        with self.server("replay", replay_port):
            status, payload, _ = self._request(replay_port, "/")
            assert status == 200 and b"metawarc" in payload

    @contextmanager
    def mcp_http(self, port: int) -> Iterator[None]:
        self.executed.add(("mcp",))
        log_path = self.directory / f"mcp-{port}.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    str(self.executable),
                    "mcp",
                    "--dbfile",
                    "collection.db",
                    "--transport",
                    "http",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=self.directory,
                env=self.env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            try:
                deadline = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"mcp exited early: {log_path.read_text()}")
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=1):
                            break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError(f"mcp did not start: {log_path.read_text()}")
                        time.sleep(0.1)
                yield
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def mcp_workflow(self) -> None:
        self.run("mcp", "--dbfile", "collection.db", timeout=20)
        from fastmcp import Client

        from metawarc.mcp_server import create_mcp

        server = create_mcp(str(self.database), data_dir=str(self.data_dir))

        async def call_tools() -> None:
            archives = await server.call_tool("list_archives", {})
            assert archives.structured_content
            search = await server.call_tool("search_records", {"phrase": "Welcome", "limit": 5})
            assert search.structured_content["total"] >= 1
            stats = await server.call_tool("collection_stats", {"top": 5})
            assert stats.structured_content
            metadata = await server.call_tool(
                "metadata_summary", {"metadata_types": "all", "top": 5}
            )
            assert metadata.structured_content is not None

        asyncio.run(call_tools())
        port = self._free_port()
        with self.mcp_http(port):

            async def call_remote_tool() -> None:
                async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                    result = await client.call_tool(
                        "search_records", {"phrase": "Welcome", "limit": 5}
                    )
                    assert result.structured_content["total"] >= 1

            asyncio.run(call_remote_tool())

    def verify_documentation(self, docs_root: Path) -> None:
        documented: set[tuple[str, ...]] = set()
        paths = [docs_root / "getting-started" / "quick-start.md"]
        paths.extend((docs_root / "use-cases").glob("*.md"))
        for path in paths:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.startswith("metawarc "):
                    continue
                command = line.rstrip().removesuffix("\\").rstrip()
                parts = shlex.split(command, comments=True)
                if len(parts) > 1:
                    documented.add(self._key(parts[1:]))
        missing = documented - self.executed
        if missing:
            formatted = ", ".join(" ".join(item) for item in sorted(missing))
            raise RuntimeError(
                f"documented commands without installed-wheel execution: {formatted}"
            )
        print(f"Executed {len(documented)} documented command forms against the installed wheel")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("core", "api", "mcp", "all"), default="core")
    parser.add_argument("--docs-root", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="metawarc-installed-smoke-") as raw_directory:
        smoke = InstalledSmoke(Path(raw_directory))
        smoke.core_workflow()
        if args.mode in {"api", "all"}:
            smoke.api_workflow()
        if args.mode in {"mcp", "all"}:
            smoke.mcp_workflow()
        if args.docs_root is not None:
            if args.mode != "all":
                parser.error("--docs-root requires --mode all")
            smoke.verify_documentation(args.docs_root)


if __name__ == "__main__":
    main()
