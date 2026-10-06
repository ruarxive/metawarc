"""Explicit read-only MCP tool surface."""

from __future__ import annotations

import json
from typing import Any

from .query import QueryService, RecordQuery
from .workspace import Workspace


def _serializable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def create_mcp(dbfile: str = "warcindex.db", data_dir: str | None = None) -> Any:
    """Create an MCP server with allowlisted typed metadata tools only."""
    try:
        from fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("MCP support requires `pip install metawarc[mcp]`") from exc

    server = FastMCP(
        "Metawarc",
        instructions=(
            "Read-only typed access to indexed WARC metadata. Tools do not accept "
            "raw SQL or arbitrary filesystem paths."
        ),
    )

    @server.tool
    def list_archives() -> list[dict[str, Any]]:
        """List registered WARC archives and catalog status."""
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as ws:
            return _serializable(QueryService(ws).list_archives())

    @server.tool
    def list_records(
        archive_ids: str | None = None,
        mimes: str | None = None,
        exts: str | None = None,
        url_pattern: str | None = None,
        host_pattern: str | None = None,
        status_min: int | None = None,
        status_max: int | None = None,
        size_min: int | None = None,
        size_max: int | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List record metadata using allowlisted typed filters."""
        selected = RecordQuery.from_values(
            archive_ids=archive_ids,
            mimes=mimes,
            exts=exts,
            url_pattern=url_pattern,
            host_pattern=host_pattern,
            status_min=status_min,
            status_max=status_max,
            size_min=size_min,
            size_max=size_max,
            offset=offset,
            limit=limit,
        )
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as ws:
            total, items = QueryService(ws, max_page=100).list_records(selected)
            return _serializable(
                {
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "revision": ws.revision(),
                    "items": items,
                }
            )

    @server.tool
    def get_record_metadata(archive_id: str, record_id: str) -> dict[str, Any] | None:
        """Return one indexed record by catalog archive and WARC record ID."""
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as ws:
            return _serializable(QueryService(ws).get_record(record_id, archive_id=archive_id))

    @server.tool
    def get_record_headers(archive_id: str, record_id: str) -> list[dict[str, Any]]:
        """Return stored HTTP headers for one indexed record."""
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as ws:
            return _serializable(QueryService(ws).get_headers(archive_id, record_id))

    @server.tool
    def search_records(phrase: str, limit: int = 50) -> dict[str, Any]:
        """Phrase-search across the indexed ``texts`` sidecar.

        Empty phrases and ``limit`` higher than ``METAWARC_MAX_PAGE``
        are rejected with a tool error. Returns a dict shaped
        ``{phrase, limit, total, hits}`` where each ``hit`` carries
        ``archive_id``, ``warc_id``, ``source``, ``url``, and a
        ``snippet`` of the matched text.
        """
        with Workspace(dbfile, data_dir=data_dir, read_only=False, create=False) as ws:
            rows = ws.search_text(phrase, limit=limit)
        return _serializable({"phrase": phrase, "limit": limit, "total": len(rows), "hits": rows})

    return server


__all__ = ["create_mcp"]
