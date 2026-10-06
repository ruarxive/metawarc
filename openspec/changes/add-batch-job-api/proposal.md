# Change: Add an authenticated durable batch-job API

## Why
Large collections need exports and analyses that do not fit inside a
single HTTP request budget. The current REST surface is strictly
read-only and bounded by `ServerSettings.request_timeout_seconds` (30s
by default); a researcher who wants to materialise a 50 000-row CSV
or re-run the duplicate-analysis on a 100 GiB WARC must drop back to
the local CLI. The same is true for the MCP surface, which is
explicitly no-SQL/no-path/no-mutation.

The 2026-09-17 improvement plan calls for "an authenticated durable
batch-job API — async export/analysis jobs for large collections" as
a deferred item. The infrastructure is already half-built:

- `ServerSettings.request_timeout_seconds` and `max_concurrency` already
  bound the request plane (we keep them).
- `QueryService.list_records` and `AnalysisService.{summary,
  stored_metadata, hash_payloads, duplicates}` are stable, typed,
  and side-effect-free.
- `metawarc.api_server.create_app` already accepts `ServerSettings`
  and wires FastAPI's middleware + bearer-token discipline.

The missing pieces are (1) a persistent job table, (2) a background
runner, (3) a `/jobs` resource, and (4) a CLI surface so the same
flow is reachable without an HTTP client.

This change ships all four. Persistence uses JSON files under
`<data_dir>/jobs/` to avoid a workspace schema migration and to keep
the job surface readable (`cat jobs/<id>.json`). The runner is an
asyncio Task started from FastAPI's lifespan handler, so there is no
extra long-running process to manage.

## What Changes
- New module `metawarc/jobs.py` defining `Job`, `JobStatus`, `JobKind`,
  `JobStore` (JSON file persistence with `os.replace` for atomic
  writes), and `JobRunner` (asyncio background task with a semaphore
  bound by `ServerSettings.max_concurrency`, a per-job
  `asyncio.wait_for` timeout, and a poll interval)
- New module `metawarc/cli_jobs.py` exposing
  `metawarc jobs submit|list|get|wait|cancel`; lives next to
  `metawarc/core.py` so the existing `cli` group can be split if needed
- `metawarc/api_models.py` adds `JobRequest`, `JobListResponse`,
  `JobResponse`, `JobResultResponse`
- `metawarc/api_server.py` gains a `lifespan` handler that starts and
  stops the `JobRunner`; new routes:
  - `POST /jobs` (auth required, creates a job)
  - `GET /jobs` (auth required, list with `--status` filter)
  - `GET /jobs/{id}` (auth required, returns the job state)
  - `GET /jobs/{id}/result` (auth required, streams the result file
    when the job is `succeeded`)
  - `DELETE /jobs/{id}` (auth required, cancels a `pending` or
    `running` job)
- The first registered `JobKind` is `export-records`, which writes
  the result of `QueryService.list_records(...)` to
  `<data_dir>/jobs/<id>/result.{json|csv|parquet}`; the input shape
  reuses the existing `RecordQuery` allowlist, the output format is
  chosen from `{json, csv, parquet}`
- New capability spec `remote-batch-job` describing the lifecycle,
  persistence, bearer-token discipline, concurrent-execution bound,
  per-job timeout, and supported job kinds
- `remote-interfaces/spec.md` gains a "Batch jobs share remote safety
  defaults" requirement that points at `remote-batch-job/spec.md`
- No new dependencies; same `fastapi`, `pydantic`, `click`, and
  `httpx2` already required by the `[api]` extra
- No SQL injection vector: job input is JSON-serialised into a file
  and validated by Pydantic on read
- No new filesystem path vector: the result path is computed by
  `JobStore` from the job id and the workspace's data directory

## Impact
- Affected specs: `remote-interfaces` (MODIFIED), new `remote-batch-job`
- Affected code:
  - New `metawarc/jobs.py`, `metawarc/cli_jobs.py`
  - `metawarc/api_models.py`, `metawarc/api_server.py`, `metawarc/core.py`
  - `tests/test_jobs.py` (new), `tests/test_job_endpoints.py` (new),
    `tests/test_cli_jobs.py` (new)
- Dependencies: none
- Backward compatibility: existing REST/MCP/CLI surfaces are
  unchanged; the new `/jobs/*` routes are additive

## Risk
- A background runner started from FastAPI lifespan shares the event
  loop with request handlers. Mitigation: every job runs under a
  separate `asyncio.Task`; cancellation flows through `JobRunner.cancel`
  which sets the job to `cancelled` and awaits the task with a
  bounded timeout.
- Long-running jobs can hold DuckDB connections open. Mitigation:
  each job opens its own short-lived `Workspace` context, mirroring
  the existing `query` path.
- JSON-file persistence is eventually consistent; a crash mid-write
  could leave a half-written file. Mitigation: writes are atomic via
  `tempfile + os.replace`; on read, malformed files are reported
  as `failed` jobs and the runner skips them.
- The export path is bounded by `ServerSettings.request_timeout
  _seconds` for parity with the synchronous export endpoint; jobs
  have their own per-job timeout (default 5 minutes,
  `METAWARC_JOB_TIMEOUT`) to keep them from running indefinitely.