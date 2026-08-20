---
title: "MCP server"
description: "Read-only allowlisted MCP tools over an indexed workspace"
---
# MCP server

Expose typed catalog metadata to MCP-compatible agents over stdio or loopback
HTTP. Requires `metawarc[mcp]`.

```bash
pip install 'metawarc[mcp]'
metawarc mcp --dbfile collection.db                    # stdio
metawarc mcp --dbfile collection.db --transport http  # loopback only by default
```

The server instructions state that tools do not accept raw SQL or arbitrary
filesystem paths. There is no payload dump or mutation tool.

## Tools

- `list_archives`
- `list_records` (allowlisted filters, default limit 50, max page 100)
- `get_record_metadata`
- `get_record_headers`

Non-loopback MCP transport requires `--allow-insecure`.

See [`mcp`](/commands/mcp) and [agents and MCP](/use-cases/agents-and-mcp).
