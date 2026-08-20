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
| `list_records` | Record metadata with typed filters |
| `get_record_metadata` | One indexed record by archive ID and WARC record ID |
| `get_record_headers` | Stored HTTP headers for one record |

Non-loopback MCP transport requires `--allow-insecure`.

See [MCP integration](/integrations/mcp) and [`mcp`](/commands/mcp). For HTTP
access with replay, use the [REST API](/integrations/rest-api) instead.
