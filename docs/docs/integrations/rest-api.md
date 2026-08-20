---
title: "REST API"
description: "Bounded read-only FastAPI access to a WARC index workspace"
---
# REST API

The REST server is optional. Install `metawarc[api]` or `metawarc[all]`. Website
replay routes are included on the same process; see [replay](/integrations/replay).

```bash
pip install 'metawarc[api]'
METAWARC_API_TOKEN='replace-me' metawarc serve --dbfile collection.db
```

Both network services bind to loopback by default. Non-loopback REST binding
requires a bearer token or an explicit `--allow-insecure` acknowledgement.

## Endpoints

| Path | Purpose |
|------|---------|
| `GET /health` | Schema version and catalog revision |
| `GET /warcs/list` | Registered archives |
| `GET /records/list` | Typed, paginated record metadata |
| `GET /records/get/{archive_id}/record/{record_id}` | One record |
| `GET /records/get/{archive_id}/headers/{record_id}` | Stored HTTP headers |
| `GET /records/get/{archive_id}/data/{record_id}` | Streamed payload (byte-capped) |
| `GET /` and `/replay/...` | Website replay (see [replay](/integrations/replay)) |

`/records/list` accepts the same allowlisted query parameters as
[`list-files`](/commands/list-files) (no `--unsafe-where`). Unexpected query
parameters return HTTP 422. Requests are bounded by timeout, concurrency, page
size, and payload bytes. Every response includes `x-trace-id`.

## Authorization

When `--token` or `METAWARC_API_TOKEN` is set, send:

```
Authorization: Bearer <token>
```

See [`serve`](/commands/serve) and [security](/architecture/security).
