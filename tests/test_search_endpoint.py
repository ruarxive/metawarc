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


def test_search_endpoint_reports_total_and_returned(workspace_with_texts: Path) -> None:
    settings = ServerSettings(db_path=str(workspace_with_texts))
    with TestClient(create_app(settings)) as client:
        response = client.get("/records/search?phrase=e&limit=1")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["returned"] == 1
    assert body["limit"] == 1
    assert len(body["hits"]) == 1


def test_mcp_search_reports_total_and_returned(workspace_with_texts: Path) -> None:
    server = create_mcp(str(workspace_with_texts))
    result = asyncio.run(server.call_tool("search_records", {"phrase": "e", "limit": 1}))
    data = result.structured_content
    assert data["total"] == 2
    assert data["returned"] == 1
    assert data["limit"] == 1
    assert len(data["hits"]) == 1


def test_search_endpoint_uses_active_max_page_configuration(
    workspace_with_texts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("METAWARC_MAX_PAGE", "1000")
    limited = ServerSettings(db_path=str(workspace_with_texts), max_page=1)
    with TestClient(create_app(limited)) as client:
        response = client.get("/records/search?phrase=e&limit=2")
    assert response.status_code == 422

    configured = ServerSettings(db_path=str(workspace_with_texts), max_page=1000)
    app = create_app(configured)
    monkeypatch.setenv("METAWARC_MAX_PAGE", "1")
    with TestClient(app) as client:
        response = client.get("/records/search?phrase=e&limit=2")
    assert response.status_code == 200


def test_search_endpoint_opens_workspace_read_only(
    workspace_with_texts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read_only_values = []
    original_init = Workspace.__init__

    def recording_init(self, *args, **kwargs):
        read_only_values.append(kwargs.get("read_only"))
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(Workspace, "__init__", recording_init)
    settings = ServerSettings(db_path=str(workspace_with_texts))
    with TestClient(create_app(settings)) as client:
        response = client.get("/records/search?phrase=museum")
    assert response.status_code == 200
    assert read_only_values == [True]


def test_mcp_search_opens_workspace_read_only(
    workspace_with_texts: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read_only_values = []
    original_init = Workspace.__init__

    def recording_init(self, *args, **kwargs):
        read_only_values.append(kwargs.get("read_only"))
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(Workspace, "__init__", recording_init)
    server = create_mcp(str(workspace_with_texts))
    asyncio.run(server.call_tool("search_records", {"phrase": "museum"}))
    assert read_only_values == [True]


def test_search_cli_distinguishes_missing_sidecar(indexed_workspace) -> None:
    database, _ = indexed_workspace
    result = CliRunner().invoke(cli, ["search", "--dbfile", str(database), "anything"])
    assert result.exit_code == 1
    assert "index-content --text" in result.output
    assert "(no matches)" not in result.output


def test_search_endpoint_distinguishes_missing_sidecar(indexed_workspace) -> None:
    database, _ = indexed_workspace
    settings = ServerSettings(db_path=str(database))
    with TestClient(create_app(settings)) as client:
        response = client.get("/records/search?phrase=anything")
    assert response.status_code == 409
    assert "index-content --text" in response.json()["detail"]


def test_mcp_search_distinguishes_missing_sidecar(indexed_workspace) -> None:
    from fastmcp.exceptions import ToolError

    database, _ = indexed_workspace
    server = create_mcp(str(database))
    with pytest.raises(ToolError, match="index-content --text"):
        asyncio.run(server.call_tool("search_records", {"phrase": "anything"}))
