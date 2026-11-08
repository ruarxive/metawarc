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
| `export-records` | Stream the result of `QueryService.iter_records` to JSON, CSV, or Parquet under `<data_dir>/jobs/<job_id>/result.<ext>` |

The MVP ships a single kind. New kinds are added as their own handlers
without changing the runner contract.

## Submit a job

### CLI

```bash
# keep the API/job runner running in one terminal
metawarc serve --dbfile collection.db

# submit from another terminal using the same workspace
metawarc jobs --dbfile collection.db submit --format csv --limit 50000 \
    --mimes application/pdf \
    --status-min 200 --status-max 299 \
    --url-pattern /reports/ \
    --archive-ids archive-1,archive-2
# Prints: job-7f3a...
```

`metawarc jobs --dbfile collection.db submit` accepts the same allowlisted filters as
[`list-files`](/commands/list-files). Pass them as comma-separated
strings; `limit` must be between 1 and `EXPORT_HARD_LIMIT` (100 000).
The format, limit, filter names, and filter ranges are validated before a job
is persisted; invalid submissions fail immediately instead of becoming
background failures. A running `metawarc serve` process watches the shared job
store and executes standalone CLI submissions without requiring a restart.

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
both interfaces share the same persisted lifecycle fields. Result locations
are intentionally different: local CLI output retains `result.path`, while
REST responses use `result.download_url`.

## Lifecycle

| Status | Meaning |
|--------|---------|
| `pending` | Persisted to `<data_dir>/jobs/<job_id>.json`; the runner has not started it yet |
| `running` | The runner is executing the handler; concurrency is bounded by `METAWARC_JOB_MAX_CONCURRENT` (default 4) |
| `succeeded` | `ended_at` is set; CLI/persisted JSON carries `result.path`, REST carries `result.download_url` |
| `failed` | `error` carries the message; `ended_at` is set |
| `cancelled` | The runner received a cancel; the running task was cancelled |

`METAWARC_JOB_TIMEOUT` (default 300 seconds) caps per-job execution. A
handler that exceeds it transitions to `failed` with
`error="timeout"`.

### Ownership and recovery

Each runner acquires an OS-backed lock before starting a job and keeps it
until the handler has stopped and its terminal state is saved. Multiple
servers may share one workspace and execute different jobs, but only one
can execute a given job. Concurrency limits remain per server. This
guarantee requires a local filesystem with reliable cross-process file
locking; lock-file existence alone does not indicate an active owner.

Startup and periodic discovery consider every pending job, not just the
first 50 shown by the default list page. If a process exits while owning
a `running` job, another runner that can acquire its lock marks it
`failed` with `error="interrupted"` and removes incomplete staged output.
The interrupted export is not silently retried; submit a new job with the
same input to retry it. Terminal jobs and completed result files remain
unchanged unless they are removed by the configured retention policy.

## Observe a job

### CLI

```bash
metawarc jobs --dbfile collection.db list --status running --limit 50
metawarc jobs --dbfile collection.db get <job_id>
metawarc jobs --dbfile collection.db wait <job_id> --poll-seconds 1 --timeout 300
metawarc jobs --dbfile collection.db wait <job_id> --progress
```

CLI list/get/wait JSON includes `progress` with `processed_rows`, `total_rows`,
and `updated_at`. It is `null` before the first update and for jobs created
before progress support. `total_rows` is the planned export size after offset
and limit, not the larger uncapped match count; an empty export is `0/0`.
Progress is persisted in a separate atomic `progress.json` sidecar and is not
used to resume an interrupted job.

`--progress` forces the shared Rich renderer on stderr; `--no-progress`
suppresses it. Without either flag, animation is enabled only for interactive
stderr. The final job JSON remains the only stdout payload, and existing exit
codes are unchanged. `metawarc jobs --dbfile collection.db wait` polls the local
`<data_dir>/jobs/<job_id>.json` so it works whether or not a server is running.
Exit codes mirror the job status:

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

# one job; a succeeded result contains download_url, not path
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/<job_id>

# result metadata: job_id, status, format, rows, size, download_url
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/<job_id>/result

# authenticated download using the returned root-relative URL
curl --fail -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/<job_id>/result/content \
     --output metawarc-<job_id>.csv
```

`GET /jobs` and `GET /jobs/{id}` expose the same `progress` snapshot as the
CLI: `processed_rows`, `total_rows`, and `updated_at`, or `null` when no durable
snapshot exists. The result metadata route is unchanged; its `rows` field is
final result metadata rather than live progress.

`GET /jobs/{id}/result` and `/result/content` return 409 for every
non-`succeeded` state. An unknown job, missing artifact, unsupported format,
or unsafe artifact returns 404 without revealing a server-local path. The
content route streams the exact file with its actual content length, a safe
attachment filename, and `Cache-Control: no-store`.

| Format | Media type |
|--------|------------|
| JSON | `application/json` |
| CSV | `text/csv; charset=utf-8` |
| Parquet | `application/vnd.apache.parquet` |

**REST migration:** replace uses of the removed `result.path` field with
`result.download_url`, then make a second authenticated request to that URL.
The on-disk job JSON and local `metawarc jobs --dbfile collection.db get` / `jobs wait` output retain
`result.path`; only the REST representation changed.

## Operational metrics

```bash
metawarc jobs --dbfile collection.db metrics --limit 1000
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     'http://127.0.0.1:8000/jobs/metrics?limit=1000'
```

Both interfaces use the same read-only calculation over retained job JSON. The
response contains `generated_at`, `limit`, `total`, `included`, `truncated`, all
five lifecycle `counts`, an `invalid` candidate count, and
`queue_wait_seconds`/`execution_seconds` summaries with `samples`, `mean`, and
`max`. The newest valid jobs by `created_at` (job id as tie-breaker) contribute
up to `limit` entries (default 1,000, range 1–10,000). `total` counts all valid
jobs observed, `included` counts the selected subset, and counts sum to
`included`; `truncated` is true exactly when `included < total`.

Queue wait is `started_at - created_at`; execution time is
`ended_at - started_at` for terminal jobs. Invalid, naive, missing, or negatively
ordered optional timing pairs only exclude that timing sample. Empty summaries
have zero samples and null mean/max. Malformed, oversized, unreadable,
non-regular, symlink, and structurally invalid files increment `invalid` rather
than becoming lifecycle statuses. Candidate reads are limited to 1 MiB and the
selection/aggregation memory is bounded. REST runs the filesystem scan off the
event loop; CLI metrics does not start a runner.

Pruning removes jobs from subsequent observations. Lifecycle changes during the
scan do not form a cross-file transaction. Metrics therefore describe a
best-effort retained-state observation, not all-time history, billing, or an
audit ledger.

## Prune terminal jobs

Preview expired terminal jobs before deleting anything:

```bash
metawarc jobs --dbfile collection.db prune --retention-days 7
metawarc jobs --dbfile collection.db prune --retention-days 7 --apply
# Manual zero selects every eligible terminal job:
metawarc jobs --dbfile collection.db prune --retention-days 0 --apply
```

Without `--apply`, the command only writes a JSON report and performs no
writes. The report contains `dry_run`, `retention_days`, `cutoff`, `candidates`,
`deleted`, `skipped`, and `remaining`; candidates and skipped entries include
`job_id`, with skip reasons such as `not_expired`, `not_terminal`,
`invalid_ended_at`, or `locked`.

Only freshly read `succeeded`, `failed`, and `cancelled` jobs with a valid
timezone-aware `ended_at` strictly older than the cutoff are eligible. Apply
acquires the existing per-job claim without waiting and checks eligibility
again. Active, pending, running, malformed, and locked jobs are skipped.
Deletion removes the lifecycle JSON, progress sidecar, known result artifacts,
and staging files, but never follows persisted `result.path` values or symlinks
and never recursively removes unexpected content. After pruning, job and result
routes return 404.

Automatic cleanup is opt-in through `METAWARC_JOB_RETENTION_DAYS` (default `0`,
disabled). A positive value runs the same policy at startup and every 60
seconds, off the event loop, with at most 50 candidates per pass. Negative,
NaN, and infinite values are rejected. There is no REST prune endpoint and no
retention of source WARCs or unrelated workspace files.

## Cancel a job

```bash
metawarc jobs --dbfile collection.db cancel <job_id>
curl -X DELETE -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     http://127.0.0.1:8000/jobs/<job_id>
```

Cancellation immediately persists a `pending` or `running` job as
`cancelled`, including when the request comes from the standalone CLI. The
server cancels its local asyncio task when present, and the export handler
checks the persisted state between batches and before publication. Results
are written to a temporary file and atomically moved to `result.<ext>` only
while the job is active; failed or cancelled exports remove the temporary
file instead of exposing a partial result.

## Security

The `/jobs` resource inherits the bearer-token discipline of the existing
`/records` and `/replay` endpoints. Loopback binds accept requests without
a token; non-loopback binds require `--token` / `METAWARC_API_TOKEN` or
`--allow-insecure`. Result downloads derive `result.<ext>` from the validated
job id and allowlisted format; they never open the persisted `result.path`.
Missing files, directories, symlinks, and paths outside the owning job
directory are rejected. The MCP surface does not expose jobs — the durable
batch API is reachable only through `metawarc serve` and `metawarc jobs`.

See [`jobs`](/commands/jobs), [`serve`](/commands/serve), and the
[REST API](/integrations/rest-api).