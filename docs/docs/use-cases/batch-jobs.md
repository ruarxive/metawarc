---
title: "Batch jobs"
description: "Submit, observe, and cancel durable batch jobs through the CLI or REST API"
---
# Batch jobs

The REST API is bounded by `ServerSettings.request_timeout_seconds`
(30 seconds by default) and is intentionally read-only. Long-running
exports that exceed a single request budget — for example, materialising
50 000 PDF rows to CSV — can be submitted as durable batch jobs instead.
Job state persists in JSON files under `<data_dir>/jobs/<job_id>.json`,
and the runner is an asyncio Task started from `metawarc serve`'s
lifespan handler, so there is no extra long-running process to manage.

## Job kinds

| Kind | Purpose |
|------|---------|
| `export-records` | Materialise the result of `QueryService.list_records` to JSON, CSV, or Parquet under `<data_dir>/jobs/<job_id>/result.<ext>` |

The MVP ships a single kind. New kinds are added as their own handlers
without changing the runner contract.

## Submit a job

### CLI

```bash
metawarc jobs submit --format csv --limit 50000 \
    --mimes application/pdf \
    --status-min 200 --status-max 299 \
    --url-pattern /reports/ \
    --archive-ids archive-1,archive-2
# Prints: job-7f3a...
```

`metawarc jobs submit` accepts the same allowlisted filters as
[`list-files`](/commands/list-files). Pass them as comma-separated
strings; `limit` is clamped to 1 – `EXPORT_HARD_LIMIT` (100 000).

### REST

```bash
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{
           "kind": "export-records",
           "format": "csv",
           "limit": 50000,
           "filters": {
             "mimes": "application/pdf",
             "status_min": 200,
             "status_max": 299,
             "url_pattern": "/reports/"
           }
         }' \
     http://127.0.0.1:8000/jobs
# 201 Created, Location: /jobs/<job_id>
```

The REST endpoint mirrors the CLI: the request body matches the
`JobRequest` Pydantic model (`kind`, `format`, `limit`, `filters`), and
the response is the same `JobResponse` shape returned by `metawarc jobs get`.

## Lifecycle

| Status | Meaning |
|--------|---------|
| `pending` | Persisted to `<data_dir>/jobs/<job_id>.json`; the runner has not started it yet |
| `running` | The runner is executing the handler; concurrency is bounded by `METAWARC_JOB_MAX_CONCURRENT` (default 4) |
| `succeeded` | `ended_at` is set, `result.path` points at the produced file |
| `failed` | `error` carries the message; `ended_at` is set |
| `cancelled` | The runner received a cancel; the running task was cancelled |

`METAWARC_JOB_TIMEOUT` (default 300 seconds) caps per-job execution. A
handler that exceeds it transitions to `failed` with
`error="timeout"`.

## Observe a job

### CLI

```bash
metawarc jobs list --status running --limit 50
metawarc jobs get <job_id>
metawarc jobs wait <job_id> --poll-seconds 1 --timeout 300
```

`metawarc jobs wait` polls the local `<data_dir>/jobs/<job_id>.json` so it
works whether or not a server is running. Exit codes mirror the job
status:

| Code | Meaning |
|------|---------|
| 0 | Succeeded |
| 1 | Unknown job id |
| 2 | Cancelled |
| 3 | Failed |
| 124 | Timeout |

### REST

```bash
# list
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     'http://127.0.0.1:8000/jobs?status=succeeded&limit=50'

# one job
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/<job_id>

# result metadata (path, format, rows, size)
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/<job_id>/result
```

`GET /jobs/{id}/result` returns 409 unless the job has reached
`succeeded`; the body is a `JobResultResponse` with `path`, `format`,
`rows`, and `size` fields.

## Cancel a job

```bash
metawarc jobs cancel <job_id>
curl -X DELETE -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/<job_id>
```

Cancellation transitions a `pending` or `running` job to `cancelled`. The
runner cooperatively cancels the running asyncio task; in-flight DuckDB
or Parquet writes either finish or roll back inside the next checkpoint,
so partial result files do not appear under `<data_dir>/jobs/<job_id>/`.

## Security

The `/jobs` resource inherits the bearer-token discipline of the existing
`/records` and `/replay` endpoints. Loopback binds accept requests without
a token; non-loopback binds require `--token` / `METAWARC_API_TOKEN` or
`--allow-insecure`. The MCP surface does not expose jobs — the durable
batch API is reachable only through `metawarc serve` and `metawarc jobs`.

See [`jobs`](/commands/jobs), [`serve`](/commands/serve), and the
[REST API](/integrations/rest-api).