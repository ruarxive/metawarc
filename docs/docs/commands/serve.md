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

`METAWARC_JOB_RETENTION_DAYS` controls optional terminal-job cleanup. It
defaults to `0` (disabled); positive values enable cleanup at startup and
every 60 seconds in batches of at most 50 jobs. Negative, NaN, and infinite
values are rejected. Manual preview/apply is available through
[`metawarc jobs prune`](/commands/jobs#prune).

Non-loopback binding requires a bearer token or `--allow-insecure`.

See [REST API](/integrations/rest-api) and [website replay](/integrations/replay).
