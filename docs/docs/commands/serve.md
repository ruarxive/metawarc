---
title: "serve"
description: "metawarc serve command reference"
---
# `serve`

Start the bounded, authenticated, read-only REST API, including `/replay/...`
website replay. Requires `pip install 'metawarc[api]'` or `'metawarc[replay]'`.

```bash
pip install 'metawarc[api]'
metawarc serve --dbfile collection.db
METAWARC_API_TOKEN='replace-me' metawarc serve --dbfile collection.db --host 0.0.0.0
```

**Options:** `--host` (default environment or `127.0.0.1`), `--port`,
`--token` / `METAWARC_API_TOKEN`, `--allow-insecure`.

Non-loopback binding requires a bearer token or `--allow-insecure`.

See [REST API](/integrations/rest-api) and [website replay](/integrations/replay).
