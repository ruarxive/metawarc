---
title: "mcp"
description: "metawarc mcp command reference"
---
# `mcp`

Run the explicit read-only MCP tool surface. Requires
`pip install 'metawarc[mcp]'`.

```bash
metawarc mcp --dbfile collection.db                    # stdio
metawarc mcp --dbfile collection.db --transport http  # loopback only by default
metawarc mcp --dbfile collection.db --transport http --host 0.0.0.0 --allow-insecure
```

**`--transport`:** `stdio` (default), `http`, or `sse`.
**`--host`:** default `127.0.0.1`. **`--port`:** default `8191`.

Non-loopback HTTP/SSE binding requires `--allow-insecure`.

## Tools

The server exposes seven allowlisted read-only tools. No raw SQL,
filesystem paths, payloads, or mutations.

| Tool | Purpose |
|------|---------|
| `list_archives` | Registered WARC archives and catalog status |
| `list_records` | Record metadata with typed filters (allowlisted fields, bound values; default limit 50, max page 100) |
| `get_record_metadata` | One indexed record by archive ID and WARC record ID |
| `get_record_headers` | Stored HTTP headers for one record |
| `search_records` | Phrase-search across the indexed `texts` sidecar (requires `metawarc index-content --text`) |
| `collection_stats` | Per-dimension rollups via `AnalysisService.summary` (`mime`, `ext`, `status`, `host`, `date`, `size_bucket`) |
| `metadata_summary` | Per-type extraction rollups via `AnalysisService.stored_metadata` (`pdfs`, `images`, `ooxmldocs`, `oledocs`, `videos`, `audio`, `fonts`, or `all`) |

See [MCP integration](/integrations/mcp) and
[Agents and MCP](/use-cases/agents-and-mcp).