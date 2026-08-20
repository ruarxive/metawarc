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

Non-loopback HTTP/SSE binding requires `--allow-insecure`. Tools: `list_archives`,
`list_records`, `get_record_metadata`, `get_record_headers`. No raw SQL,
filesystem paths, payloads, or mutations.

See [MCP integration](/integrations/mcp).
