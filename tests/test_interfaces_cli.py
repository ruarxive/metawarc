from __future__ import annotations

import asyncio
import json
from pathlib import Path

from click.testing import CliRunner
from fastapi.testclient import TestClient

from metawarc.cmds.server import create_app
from metawarc.core import cli
from metawarc.mcp_server import create_mcp
from metawarc.settings import ServerSettings


def test_cli_end_to_end(warc_factory, tmp_path: Path):
    source = warc_factory()
    database = tmp_path / "cli.db"
    runner = CliRunner()
    indexed = runner.invoke(
        cli,
        ["index", str(source), "--dbfile", str(database), "--silent", "--output-format", "json"],
    )
    assert indexed.exit_code == 0, indexed.output
    assert json.loads(indexed.output)["records"] == 2
    for arguments in (
        ["catalog", "--dbfile", str(database), "--output-format", "json"],
        ["stats", "--dbfile", str(database), "--output-format", "json"],
        ["list-files", "--dbfile", str(database), "--mimes", "text/html", "--limit", "1"],
        ["doctor", "--dbfile", str(database)],
        ["ingest", str(source), "--dbfile", str(database), "--dry-run"],
        ["analyze", "summary", "--dbfile", str(database), "--top", "1"],
        ["analyze", "metadata", "--dbfile", str(database), "--top", "1"],
        ["index-content", "--dbfile", str(database), "--type", "links", "--silent"],
        ["analyze", "hashes", "--dbfile", str(database), "--batch-size", "1"],
        ["analyze", "duplicates", "--dbfile", str(database)],
        ["analyze", "links", "--dbfile", str(database)],
        ["analyze", "integrity", "--dbfile", str(database)],
        ["cleanup", "--dbfile", str(database), "--retention-days", "0"],
    ):
        result = runner.invoke(cli, arguments)
        assert result.exit_code == 0, f"{arguments}: {result.output}\n{result.exception}"
    unsafe = runner.invoke(cli, ["serve", "--host", "0.0.0.0", "--dbfile", str(database)])
    assert unsafe.exit_code != 0
    metadata = tmp_path / "links.jsonl"
    dumped_metadata = runner.invoke(
        cli,
        [
            "dump-metadata",
            "--dbfile",
            str(database),
            "--type",
            "links",
            "--output",
            str(metadata),
            "--silent",
        ],
    )
    assert dumped_metadata.exit_code == 0, dumped_metadata.output
    assert metadata.exists()
    selected_metadata = runner.invoke(
        cli,
        [
            "analyze",
            "metadata",
            "--dbfile",
            str(database),
            "--type",
            "pdfs",
            "--type",
            "images",
        ],
    )
    assert selected_metadata.exit_code == 0, selected_metadata.output
    assert json.loads(selected_metadata.output)["filters"]["metadata_types"] == [
        "pdfs",
        "images",
    ]
    ambiguous_metadata = runner.invoke(
        cli,
        [
            "analyze",
            "metadata",
            "--dbfile",
            str(database),
            "--type",
            "all",
            "--type",
            "pdfs",
        ],
    )
    assert ambiguous_metadata.exit_code != 0
    assert "cannot be combined" in ambiguous_metadata.output
    export_dir = tmp_path / "cli-export"
    dumped = runner.invoke(
        cli,
        [
            "dump",
            "--dbfile",
            str(database),
            "--limit",
            "1",
            "--output",
            str(export_dir),
            "--silent",
        ],
    )
    assert dumped.exit_code == 0, dumped.output
    selected = tmp_path / "selected.html"
    fetched = runner.invoke(
        cli,
        [
            "get",
            "urn:uuid:alpha",
            "--dbfile",
            str(database),
            "--output",
            str(selected),
            "--silent",
        ],
    )
    assert fetched.exit_code == 0, fetched.output
    assert selected.exists()


def test_cli_failure_has_nonzero_exit(tmp_path: Path):
    result = CliRunner().invoke(
        cli,
        [
            "index",
            str(tmp_path / "missing.warc"),
            "--dbfile",
            str(tmp_path / "missing.db"),
            "--silent",
        ],
    )
    assert result.exit_code != 0
    assert "failed" in result.output.lower()


def test_rest_auth_filters_limits_and_openapi(indexed_workspace):
    database, _ = indexed_workspace
    settings = ServerSettings(
        db_path=str(database), token="secret", max_page=1, max_payload_bytes=1024
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 401
        headers = {"Authorization": "Bearer secret"}
        assert client.get("/health", headers=headers).status_code == 200
        page = client.get("/records/list?limit=1&mimes=text/html", headers=headers)
        assert page.status_code == 200
        assert page.json()["items"][0]["warc_id"] == "urn:uuid:alpha"
        rejected = client.get("/records/list?limit=2", headers=headers)
        assert rejected.status_code == 422
        raw_query = client.get("/records/list?query=read_parquet('secret')", headers=headers)
        assert raw_query.status_code == 422
        schema = client.get("/openapi.json").json()
        params = json.dumps(schema["paths"]["/records/list"]["get"]["parameters"])
        assert "raw" not in params.lower()
        archive_id = page.json()["items"][0]["archive_id"]
        archives = client.get("/warcs/list", headers=headers)
        assert archives.status_code == 200
        metadata = client.get(f"/records/get/{archive_id}/record/urn:uuid:alpha", headers=headers)
        assert metadata.status_code == 200
        record_headers = client.get(
            f"/records/get/{archive_id}/headers/urn:uuid:alpha", headers=headers
        )
        assert record_headers.status_code == 200
        payload = client.get(f"/records/get/{archive_id}/data/urn:uuid:alpha", headers=headers)
        assert payload.status_code == 200
        assert b"About" in payload.content
        missing = client.get(f"/records/get/{archive_id}/record/does-not-exist", headers=headers)
        assert missing.status_code == 404


def test_mcp_inventory_is_minimal_and_read_only(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "list_archives",
        "list_records",
        "get_record_metadata",
        "get_record_headers",
    }
    schema = json.dumps([tool.model_dump() for tool in tools], default=str).lower()
    assert "raw sql" not in schema
    assert "delete" not in names


def test_documented_commands_match_click_tree():
    documentation = (
        Path(__file__).parents[1] / "docs" / "docs" / "commands" / "index.md"
    ).read_text()
    for command in cli.commands:
        assert f"`{command}`" in documentation


def test_every_cli_command_exposes_help():
    runner = CliRunner()
    for command in cli.commands:
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0, f"{command}: {result.output}"
    for command in ("summary", "metadata", "hashes", "duplicates", "links", "integrity"):
        result = runner.invoke(cli, ["analyze", command, "--help"])
        assert result.exit_code == 0, f"analyze {command}: {result.output}"


def test_nonloopback_mcp_requires_explicit_acknowledgement():
    result = CliRunner().invoke(
        cli,
        ["mcp", "--transport", "http", "--host", "0.0.0.0"],
    )
    assert result.exit_code != 0
    assert "allow-insecure" in result.output
