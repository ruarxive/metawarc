"""Tests for the new collection_stats and metadata_summary MCP tools."""

from __future__ import annotations

import asyncio
import json
from typing import Any

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
    import pytest

    with pytest.raises(ToolError) as caught:
        _call(server, tool, arguments)
    return caught.value


def test_collection_stats_returns_dimensions(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    payload = _call(server, "collection_stats", {"dimensions": "mime,status"})

    assert payload["kind"] == "collection-summary"
    assert payload["catalog_revision"] >= 1
    assert set(payload["data"].keys()) == {"mime", "status"}
    mime_groups = {row["mime"] for row in payload["data"]["mime"]}
    assert "text/html" in mime_groups


def test_collection_stats_rejects_oversized_top(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    error = _call_expecting_error(server, "collection_stats", {"top": 0})
    assert "top" in str(error)

    error = _call_expecting_error(server, "collection_stats", {"top": 200_000})
    assert "top" in str(error)


def test_collection_stats_rejects_unknown_dimension(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    error = _call_expecting_error(
        server,
        "collection_stats",
        {"dimensions": "mime,bogus"},
    )
    assert "bogus" in str(error)


def test_metadata_summary_returns_rollups(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    payload = _call(server, "metadata_summary", {"metadata_types": "pdfs,images"})

    assert payload["kind"] == "stored-metadata"
    assert isinstance(payload["data"], list)
    types = {row["metadata_type"] for row in payload["data"]}
    assert types == {"pdfs", "images"}


def test_metadata_summary_all_includes_every_type(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    payload = _call(server, "metadata_summary", {"metadata_types": "all"})

    types = {row["metadata_type"] for row in payload["data"]}
    assert types >= {"pdfs", "images", "ooxmldocs", "oledocs", "videos", "audio", "fonts"}


def test_metadata_summary_rejects_unknown_type(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    error = _call_expecting_error(
        server,
        "metadata_summary",
        {"metadata_types": "pdfs,bogus"},
    )
    assert "bogus" in str(error)


def test_metadata_summary_rejects_zero_top(indexed_workspace):
    database, _ = indexed_workspace
    server = create_mcp(str(database))

    error = _call_expecting_error(server, "metadata_summary", {"top": 0})
    assert "top" in str(error)
