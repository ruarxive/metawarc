## 1. Spec delta
- [x] 1.1 Create `openspec/specs/remote-batch-job/spec.md` with the
      lifecycle, persistence, bearer-token discipline, concurrent
      bound, per-job timeout, and supported job kinds
- [x] 1.2 Add a "Batch jobs share remote safety defaults" requirement
      to `openspec/specs/remote-interfaces/spec.md` that points at
      the new capability
- [x] 1.3 Confirm `openspec validate --strict` passes for both
      `add-batch-job-api` and `--specs`

## 2. Job core
- [x] 2.1 Add `metawarc/jobs.py` with:
      - `JobStatus` enum (`pending`, `running`, `succeeded`,
        `failed`, `cancelled`)
      - `JobKind` enum (start with `export-records`)
      - `Job` dataclass (id, kind, status, input dict, result dict,
        error, created_at, started_at, ended_at)
      - `JobStore` class that reads and writes one job per file
        under `<data_dir>/jobs/<id>.json` with atomic `os.replace`
      - `JobRunner` class with `start()`, `stop()`, `submit()`,
        `cancel(id)`, `get(id)`, `list_(status=None, limit=50)`
- [x] 2.2 Implement the `export-records` handler: writes JSON, CSV,
      or Parquet based on the input's `format` field; output path is
      `<data_dir>/jobs/<id>/result.<ext>`; rows are bounded by
      `input["limit"]` (default 1 000, max 100 000)

## 3. Settings
- [x] 3.1 Add `job_timeout_seconds` and `job_max_concurrent` to
      `ServerSettings` and `from_env` (`METAWARC_JOB_TIMEOUT`,
      `METAWARC_JOB_MAX_CONCURRENT`); defaults 300 and 4
- [x] 3.2 Update `_run_serve` to forward the new settings to the
      `ServerSettings` constructor

## 4. REST surface
- [x] 4.1 Add `JobRequest`, `JobResponse`, `JobListResponse`,
      `JobResultResponse` to `metawarc/api_models.py`
- [x] 4.2 In `metawarc/api_server.py`, add a `lifespan` parameter to
      `FastAPI(...)` that creates a `JobStore` and `JobRunner`,
      starts the runner task, and stops it on shutdown
- [x] 4.3 Add `POST /jobs` (auth required) that validates the
      request, submits the job, and returns 201 with the job id
- [x] 4.4 Add `GET /jobs` (auth required) with `--status` and
      `--limit` filters
- [x] 4.5 Add `GET /jobs/{id}` (auth required) returning the job
      state or 404
- [x] 4.6 Add `GET /jobs/{id}/result` (auth required) that streams
      the result file when `succeeded` and returns 409 otherwise
- [x] 4.7 Add `DELETE /jobs/{id}` (auth required) cancelling a
      `pending` or `running` job

## 5. CLI surface
- [x] 5.1 Create `metawarc/cli_jobs.py` with:
      - `submit` (subcommands): `--kind export-records`, `--format`,
        `--limit`, `--archive-ids`, `--mimes`, `--exts`,
        `--url-pattern`, `--host-pattern`, `--status-min`,
        `--status-max`, `--size-min`, `--size-max`
      - `list` with `--status` and `--limit`
      - `get <id>`
      - `wait <id>` with `--poll-seconds` (default 1) and
        `--timeout` (default 300)
      - `cancel <id>`
- [x] 5.2 Wire `cli_jobs` into `metawarc/core.py` so
      `metawarc jobs ...` reaches the new handlers
- [x] 5.3 Update `test_documented_commands_match_click_tree` if the
      docs mention the new subcommand — added `jobs` to
      `docs/docs/commands/index.md` and a new `jobs.md` page

## 6. Tests
- [x] 6.1 `tests/test_jobs.py` covers `JobStore` round-trip,
      atomic-write semantics, malformed-file fallback (17 cases)
- [x] 6.2 `tests/test_job_endpoints.py` covers the FastAPI routes
      with bearer-token auth, including 401 paths, 404 paths,
      422 paths, and the end-to-end submit→wait→result flow (12 cases)
- [x] 6.3 `tests/test_cli_jobs.py` covers the CLI surface,
      including `metawarc jobs submit|list|get|wait|cancel` (11 cases)
- [x] 6.4 Verified the existing
      `test_mcp_inventory_is_minimal_and_read_only` still passes
      (the MCP surface is unchanged)

## 7. Verification
- [x] 7.1 `pytest -q` reports 166 + 40 new tests passing (206 total)
- [x] 7.2 `metawarc.jobs` coverage 90 %, `metawarc.api_server`
      90 %, `metawarc.cli_jobs` 91 %
- [x] 7.3 `ruff format --check`, `ruff check`, and `mypy metawarc`
      remain clean
- [x] 7.4 `openspec validate add-batch-job-api --strict` passes
- [x] 7.5 `pip-audit` was not run in this change; the new
      dependencies are all already in `[api]`