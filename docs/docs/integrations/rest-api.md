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
| `GET /records/search` | Phrase-search across the indexed `texts` sidecar (requires [`index-content --text`](/commands/index-content)) |
| `POST /jobs` | Submit a durable batch job (MVP kind: `export-records`) |
| `GET /jobs` | List jobs (filterable by status) |
| `GET /jobs/{job_id}` | One job's state |
| `GET /jobs/{job_id}/result` | Result metadata (path, format, rows, size) when the job has `succeeded` |
| `DELETE /jobs/{job_id}` | Cancel a `pending` or `running` job |
| `GET /` and `/replay/...` | Website replay (see [replay](/integrations/replay)) |

`/records/list` accepts the same allowlisted query parameters as
[`list-files`](/commands/list-files) (no `--unsafe-where`). Unexpected query
parameters return HTTP 422. Requests are bounded by timeout, concurrency, page
size, and payload bytes. Every response includes `x-trace-id`.

`/records/search` accepts `phrase` (1–512 chars) and `limit`
(1 – `METAWARC_MAX_PAGE`, default 50). Empty phrases return HTTP 400.

`/jobs` runs the same `export-records` workflow as
[`metawarc jobs submit`](/commands/jobs): the runner materialises the
result of `QueryService.list_records` to JSON, CSV, or Parquet under
`<data_dir>/jobs/<job_id>/`. Job state persists across server restarts;
concurrency is bounded by `METAWARC_JOB_MAX_CONCURRENT` (default 4) and
per-job execution by `METAWARC_JOB_TIMEOUT` (default 300s).

## Authorization

When `--token` or `METAWARC_API_TOKEN` is set, send:

```
Authorization: Bearer <token>
```

See [`serve`](/commands/serve) and [security](/architecture/security).