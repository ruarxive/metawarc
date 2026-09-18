"""End-to-end tests for the read-only MCP tool surface."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from metawarc.mcp_server import create_mcp


def _call(server: Any, tool: str, arguments: dict[str, Any]) -> Any:
    async def invoke() -> Any:
        async with Client(server) as client:
            result = await client.call_tool(tool, arguments)
            if not result.content:
                return None
            return json.loads(result.content[0].text)

    return asyncio.run(invoke())


def _call_expecting_error(server: Any, tool: str, arguments: dict[str, Any]) -> ToolError:
    with pytest.raises(ToolError) as caught:
        _call(server, tool, arguments)
    return caught.value


def test_mcp_tools_serve_indexed_workspace(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    archives = _call(server, "list_archives", {})
    assert len(archives) == 1
    archive_id = archives[0]["id"]
    assert archives[0]["status"] == "complete"

    page = _call(server, "list_records", {"mimes": "text/html", "limit": 5})
    assert page["total"] == 1
    assert page["items"][0]["warc_id"] == "urn:uuid:alpha"
    assert page["revision"] >= 1

    hostile = _call(server, "list_records", {"url_pattern": "' OR 1=1 --", "limit": 5})
    assert hostile["total"] == 0

    record = _call(
        server,
        "get_record_metadata",
        {"archive_id": archive_id, "record_id": "urn:uuid:alpha"},
    )
    assert record["url"] == "https://example.test/index.html"

    headers = _call(
        server,
        "get_record_headers",
        {"archive_id": archive_id, "record_id": "urn:uuid:alpha"},
    )
    assert any(item["key"].lower() == "content-type" for item in headers)

    missing = _call(
        server,
        "get_record_metadata",
        {"archive_id": archive_id, "record_id": "urn:uuid:unknown"},
    )
    assert missing is None


def test_mcp_list_records_rejects_oversized_pages(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))
    error = _call_expecting_error(server, "list_records", {"limit": 500})
    assert "limit" in str(error)


def test_mcp_rejects_missing_workspace(tmp_path: Path):
    server = create_mcp(str(tmp_path / "missing.db"))
    error = _call_expecting_error(server, "list_archives", {})
    assert "missing.db" in str(error) or "not found" in str(error).lower()


def test_mcp_creation_explains_missing_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "fastmcp", None)
    with pytest.raises(RuntimeError, match=r"metawarc\[mcp\]"):
        create_mcp("unused.db")
