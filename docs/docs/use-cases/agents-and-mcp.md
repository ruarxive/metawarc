---
title: "Agents and MCP"
description: "Give LLM agents read-only typed access to indexed WARC metadata"
---
# Agents and MCP

Give agents controlled metadata tools instead of unconstrained shell or SQL
access. The MCP surface is read-only and contains no raw SQL, filesystem-path,
payload, or mutation tool.

## Start the MCP server

```bash
pip install 'metawarc[mcp]'
metawarc mcp --dbfile collection.db                    # stdio
metawarc mcp --dbfile collection.db --transport http  # loopback only by default
```

Wire the stdio command into your MCP client (Claude Desktop, Cursor, and similar).

## Allowlisted tools

| Tool | Purpose |
|------|---------|
| `list_archives` | Registered WARC archives and catalog status |
| `list_records` | Record metadata with typed filters (allowlisted fields, bound values) |
| `get_record_metadata` | One indexed record by archive ID and WARC record ID |
| `get_record_headers` | Stored HTTP headers for one record |
| `search_records` | Phrase-search across the indexed `texts` sidecar (run [`index-content --text`](/commands/index-content) first) |
| `collection_stats` | Per-dimension rollups via `AnalysisService.summary` |
| `metadata_summary` | Per-type extraction rollups via `AnalysisService.stored_metadata` |

`collection_stats` and `metadata_summary` mirror the local `analyze summary`
and `analyze metadata` reports and are bounded by the same
`ServerSettings.max_page` and `request_timeout_seconds` limits inherited
from the FastAPI app. `top` is clamped to 1–100,000 and rejected otherwise.

## Search workflow

Phrase search needs the `texts` Parquet sidecar. Populate it once after
indexing:

```bash
metawarc index-content --dbfile collection.db --text
metawarc search "Welcome to the museum of modern art"
```

The same workflow is reachable through MCP and the REST API:

- MCP: `search_records(phrase="...", limit=50)`
- REST: `GET /records/search?phrase=<text>&limit=<n>`

Non-loopback MCP transport requires `--allow-insecure`.

See [MCP integration](/integrations/mcp) and [`mcp`](/commands/mcp). For HTTP
access with replay, use the [REST API](/integrations/rest-api) instead.