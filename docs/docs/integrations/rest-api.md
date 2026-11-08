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
| `GET /jobs/metrics` | Read-only operational aggregates over retained jobs |
| `GET /jobs/{job_id}` | One job's state |
| `GET /jobs/{job_id}/result` | Non-sensitive result metadata and `download_url` when the job has `succeeded` |
| `GET /jobs/{job_id}/result/content` | Stream the validated JSON, CSV, or Parquet artifact |
| `DELETE /jobs/{job_id}` | Cancel a `pending` or `running` job |
| `GET /` and `/replay/...` | Website replay (see [replay](/integrations/replay)) |

`/records/list` accepts the same allowlisted query parameters as
[`list-files`](/commands/list-files) (no `--unsafe-where`). Unexpected query
parameters return HTTP 422. Requests are bounded by timeout, concurrency, page
size, and payload bytes. Every response includes `x-trace-id`.

`/records/search` accepts `phrase` (1–512 chars) and `limit`
(1 – `METAWARC_MAX_PAGE`, default 50). Matching is literal and
case-insensitive, with deterministic ordering and match-centered snippets.
`total` reports all matches, `returned` reports the number of items in
`hits`, and `limit` is the requested page bound. Empty queries and excessive
limits return HTTP 422; whitespace-only phrases return HTTP 400. A missing
`texts` sidecar returns HTTP 409 with an `index-content --text` hint.

`/jobs` runs the same `export-records` workflow as
[`metawarc jobs submit`](/commands/jobs): the runner materialises the
result of `QueryService.iter_records` to JSON, CSV, or Parquet under
`<data_dir>/jobs/<job_id>/`. Formats, limits, filter names, and filter ranges
are validated before persistence; invalid submissions return HTTP 422 without
creating a job. Job state persists across server restarts; concurrency is
bounded by `METAWARC_JOB_MAX_CONCURRENT` (default 4) and per-job execution by
`METAWARC_JOB_TIMEOUT` (default 300s).

Job list/get responses include an additive `progress` object with
`processed_rows`, `total_rows`, and `updated_at`. It is `null` before the
first durable update and for older jobs without a sidecar. `total_rows` is the
planned export size after `offset` and `limit`, not the uncapped match count;
an empty export has `0/0`. Progress is read from the job's private
`progress.json` sidecar and never exposes its filesystem path.

### Operational metrics

`GET /jobs/metrics?limit=1000` uses the same bearer-token policy and returns the
same aggregate contract as `metawarc jobs metrics`. The bounded `limit` accepts
1–10,000 and selects the newest valid retained jobs by `created_at`, with job id
as the deterministic tie-breaker. `total` counts all valid jobs observed,
`included` counts jobs contributing to aggregates, and `truncated` is true when
`included < total`; lifecycle `counts` therefore sum to `included`. `invalid`
counts rejected files separately. Responses never include job ids, inputs,
errors, result paths, or progress paths.

`queue_wait_seconds` is `started_at - created_at`; `execution_seconds` is
`ended_at - started_at` for terminal jobs. Each reports `samples`, arithmetic
`mean`, and `max`. Invalid, naive, missing, or negatively ordered optional timing
pairs only exclude that sample; empty summaries contain zero samples and null
statistics. Files are read one at a time with a 1 MiB bound, aggregation memory
is bounded, and REST runs the scan off the event loop.

Pruned jobs disappear from subsequent observations. Metrics are a best-effort,
non-transactional view of retained state, not all-time history, billing data, or
an audit ledger.

### Job results

A succeeded job's embedded `result` and `GET /jobs/{job_id}/result` expose a
root-relative `download_url`, never a server-local `path`:

```json
{
  "job_id": "job-7f3a...",
  "status": "succeeded",
  "format": "csv",
  "rows": 50000,
  "size": 1234567,
  "download_url": "/jobs/job-7f3a.../result/content"
}
```

Follow that URL with the same bearer token to stream the attachment:

```bash
curl --fail -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/job-7f3a.../result/content \
     --output records.csv
```

JSON, CSV, and Parquet use `application/json`, `text/csv; charset=utf-8`, and
`application/vnd.apache.parquet` respectively. Responses carry the actual
content length and `Cache-Control: no-store`. Both result routes return 409
for non-`succeeded` jobs and 404 for an unknown job or a missing/unsafe
artifact. Resolution ignores persisted paths and rejects directories,
symlinks, unsupported formats, and files outside the owning job directory.

**Breaking migration:** REST clients must replace `result.path` with
`result.download_url` and make the additional authenticated content request.
Local CLI output and persisted job JSON continue to use `result.path`. See the
[batch-job guide](/use-cases/batch-jobs) for the complete workflow.

There is intentionally no REST prune endpoint; `DELETE /jobs/{id}` remains
cancellation only. Operators can preview
or apply terminal-job retention with
[`metawarc jobs prune --retention-days N`](/commands/jobs#prune), or set
`METAWARC_JOB_RETENTION_DAYS` to a positive number for automatic cleanup.
After a job is pruned, both its job and result routes return 404.

## Authorization

When `--token` or `METAWARC_API_TOKEN` is set, send:

```
Authorization: Bearer <token>
```

See [`serve`](/commands/serve) and [security](/architecture/security).