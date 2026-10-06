"""Tests for the REST ``/records/search`` endpoint and MCP ``search_records`` tool."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from metawarc.api_server import create_app
from metawarc.core import cli
from metawarc.extractor import TEXT_SCHEMA
from metawarc.mcp_server import create_mcp
from metawarc.settings import ServerSettings
from metawarc.workspace import Workspace


def _publish_texts(workspace: Workspace, archive_id: str) -> None:
    rows = [
        {
            "archive_id": archive_id,
            "warc_id": "WARC-1",
            "source": "sample.warc",
            "url": "https://example.test/welcome",
            "language": "en",
            "text": "Welcome to the museum of modern art",
        },
        {
            "archive_id": archive_id,
            "warc_id": "WARC-2",
            "source": "sample.warc",
            "url": "https://example.test/about",
            "language": "en",
            "text": "About opening hours and tickets",
        },
    ]
    table = pa.Table.from_pylist(rows, schema=TEXT_SCHEMA)
    destination = workspace.new_sidecar_path(archive_id, "synthetic", "texts")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, destination, compression="zstd")
    workspace.publish_sidecar(
        archive_id=archive_id,
        kind="texts",
        path=destination,
        num_items=table.num_rows,
        run_id="synthetic",
    )


@pytest.fixture
def workspace_with_texts(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(str(database), read_only=False, create=False) as ws:
        archive_id = ws.list_archives()[0]["id"]
        _publish_texts(ws, archive_id)
    return database


def test_search_endpoint_requires_token(workspace_with_texts: Path) -> None:
    settings = ServerSettings(db_path=str(workspace_with_texts), token="secret")
    with TestClient(create_app(settings)) as client:
        response = client.get("/records/search?phrase=museum")
    assert response.status_code == 401


def test_search_endpoint_returns_hits(workspace_with_texts: Path) -> None:
    settings = ServerSettings(db_path=str(workspace_with_texts), token="secret")
    headers = {"Authorization": "Bearer secret"}
    with TestClient(create_app(settings)) as client:
        response = client.get("/records/search?phrase=museum", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["phrase"] == "museum"
    assert body["total"] == 1
    assert body["hits"][0]["url"] == "https://example.test/welcome"


def test_search_endpoint_rejects_empty_phrase(workspace_with_texts: Path) -> None:
    """An empty query phrase is rejected by FastAPI's query validation.

    FastAPI's ``min_length=1`` triggers a 422 (Unprocessable Entity)
    before the handler runs; the service-layer guard against empty
    phrases is exercised by the CLI test.
    """
    settings = ServerSettings(db_path=str(workspace_with_texts), token="secret")
    headers = {"Authorization": "Bearer secret"}
    with TestClient(create_app(settings)) as client:
        response = client.get("/records/search?phrase=", headers=headers)
    assert response.status_code == 422


def test_search_endpoint_no_token_no_auth_required(workspace_with_texts: Path) -> None:
    settings = ServerSettings(db_path=str(workspace_with_texts), token=None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/records/search?phrase=museum")
    assert response.status_code == 200


def test_search_cli_command_runs_end_to_end(workspace_with_texts: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "search",
            "--dbfile",
            str(workspace_with_texts),
            "museum",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "https://example.test/welcome" in result.output


def test_mcp_search_records_tool_is_registered(workspace_with_texts: Path) -> None:
    server = create_mcp(str(workspace_with_texts))
    tools = asyncio.run(server.list_tools())
    names = {tool.name for tool in tools}
    assert "search_records" in names


def test_mcp_search_records_returns_hits(workspace_with_texts: Path) -> None:
    server = create_mcp(str(workspace_with_texts))
    result = asyncio.run(server.call_tool("search_records", {"phrase": "museum"}))
    # fastmcp surfaces the structured result; the helper returns a
    # serialisable dict shaped {phrase, limit, total, hits}.
    data = result.structured_content if hasattr(result, "structured_content") else None
    assert data is not None
    assert data["total"] == 1
    assert data["hits"][0]["url"] == "https://example.test/welcome"
