# remote-batch-job Specification

## Purpose
Defines an authenticated, durable batch-job resource for long-running
read-only operations (exports, analyses) that exceed the synchronous
REST request timeout. Job state persists across server restarts, job
execution is bounded by a server-wide concurrency cap and a per-job
timeout, and the resource inherits the same bearer-token discipline
as the synchronous /records and /replay endpoints.

## Requirements

### Requirement: Job lifecycle states
Every job SHALL move through the documented states in order:
`pending` → `running` → (`succeeded` | `failed` | `cancelled`). An
unclaimed `running` job recovered after owner loss SHALL transition to
`failed` with `error="interrupted"` and SHALL NOT be silently retried. The
runner SHALL refuse to start a job whose file is malformed or whose
current state is not `pending`, and SHALL refuse to cancel a job whose
current state is `succeeded`, `failed`, or `cancelled`.

#### Scenario: Successful job
- **WHEN** a job completes without error
- **THEN** its state is `succeeded`, `ended_at` is populated, and
  `result` carries the result location and row count

#### Scenario: Job fails during execution
- **WHEN** the handler raises an unexpected exception
- **THEN** the job's state is `failed`, `error` carries the message,
  `ended_at` is populated, and the runner continues with the next
  pending job

#### Scenario: Running job is interrupted by owner loss
- **WHEN** a runner acquires the lock of a persisted `running` job after
  the previous owner exited without saving a terminal state
- **THEN** the job becomes `failed` with `error="interrupted"` and
  `ended_at` populated, its handler is not invoked, and no incomplete
  result is published

#### Scenario: User retries an interrupted job
- **WHEN** a user submits a new job with the input of a failed interrupted
  job
- **THEN** the new job receives a distinct id and follows the normal
  pending-to-running lifecycle without mutating the failed job's history

#### Scenario: Cancel a running job
- **WHEN** the runner receives a cancel for a `running` job
- **THEN** the job's state becomes `cancelled`, the running task is
  awaited with a bounded timeout, and subsequent `GET /jobs/{id}`
  reports the new state

### Requirement: Cross-process job claims
The runner SHALL acquire a non-blocking OS-backed per-job lock before
starting a pending job and SHALL retain ownership until the handler has
stopped and its terminal state has been persisted. A runner that cannot
acquire the lock SHALL leave the job state and results untouched. The
locking mechanism SHALL work on supported local filesystems and SHALL NOT
rely on lock-file existence or wall-clock staleness as proof of ownership.
Private lock artifacts SHALL NOT change the public job JSON, CLI, or REST
response schemas.

#### Scenario: Two runners discover one pending job
- **WHEN** two independent runner processes discover the same pending job
- **THEN** exactly one process acquires its claim and invokes the handler,
  and the other process leaves the job to the owner

#### Scenario: Runner polls an actively owned running job
- **WHEN** a runner observes a `running` job whose lock is owned by a live
  process
- **THEN** it does not change the job state, invoke the handler, or remove
  the owner's staged result

#### Scenario: Owner exits without saving a terminal state
- **WHEN** the operating system has released the claim of a job still
  persisted as `running`
- **THEN** another runner can acquire the claim and perform the documented
  interrupted-job recovery without waiting for a lease to expire

### Requirement: Job kinds registry
The runner SHALL dispatch work by `JobKind`. The MVP SHALL register
exactly one kind, `export-records`, which streams the result of
`QueryService.iter_records(...)` into a single file under the
workspace's `jobs/` directory. CLI and REST submission SHALL validate the
format, 1–100 000 row limit, and allowlisted `RecordQuery` filters before
persisting the job. Unknown filters, invalid ranges, and unsupported formats
SHALL be rejected without creating a job file.

#### Scenario: Unknown kind is rejected
- **WHEN** a client submits a job whose `kind` is not in the registry
- **THEN** the runner returns a validation error naming the unknown
  kind and never writes the job file

#### Scenario: Invalid export filters are rejected eagerly
- **WHEN** a CLI or REST client submits an unknown filter, contradictory
  status range, or negative size bound
- **THEN** submission returns a validation error and no job is persisted

#### Scenario: `export-records` writes the chosen format
- **WHEN** a client submits an `export-records` job with
  `format="csv"` and a bounded `RecordQuery`
- **THEN** the job's `result.path` points at the produced CSV file
  and `result.rows` equals the row count written

### Requirement: Durable export progress
The `export-records` runner SHALL persist progress at the existing bounded
streaming boundaries in an atomic per-job `progress.json` sidecar. Progress
SHALL contain `processed_rows`, `total_rows`, and `updated_at`. The total SHALL
be the planned export size after offset and limit, not the uncapped number of
matching records. Progress SHALL be monotonic within a job, SHALL NOT mutate
lifecycle state, and SHALL NOT require an additional archive scan or unbounded
buffering. Missing sidecars SHALL project as `progress=null`.

#### Scenario: Running export publishes batch progress
- **WHEN** an owned export with a planned total greater than 256 rows finishes
  its initial and subsequent 256-row batches
- **THEN** each durable snapshot has a non-decreasing processed count, the
  planned total, and an update timestamp, and the final count equals the rows
  published in the result

#### Scenario: Export stops before completion
- **WHEN** an export is cancelled, fails, times out, or is recovered as
  interrupted after publishing progress
- **THEN** the last durable progress remains diagnostic metadata, the lifecycle
  status remains authoritative, and no result is published from incomplete
  staging output

#### Scenario: Old job has no progress sidecar
- **WHEN** a client inspects a job created before progress support or before
  the first progress update
- **THEN** the job view reports `progress=null` without rewriting its lifecycle
  JSON or changing its status

### Requirement: Job progress interfaces
REST job list/get responses and CLI job list/get/wait JSON SHALL expose the
same additive progress snapshot. `metawarc jobs wait` SHALL support
`--progress/--no-progress`, reuse the shared bounded terminal renderer, write
progress only to stderr, and preserve final JSON on stdout and existing exit
codes. Automatic rendering SHALL be disabled for non-interactive stderr.

#### Scenario: User waits with progress enabled
- **WHEN** a user runs `metawarc jobs wait <id> --progress` while the export
  advances
- **THEN** stderr shows processed and planned rows through the shared renderer,
  stdout remains valid final job JSON, and the exit code still reflects the
  terminal lifecycle state

#### Scenario: Remote client polls a running job
- **WHEN** an authenticated client calls `GET /jobs/{id}` during an export
- **THEN** the response includes the latest durable progress snapshot without
  exposing a local progress-file path

### Requirement: Safe result artifact resolution
Result routes SHALL derive the artifact location from the validated job id,
allowlisted export format, and deterministic `result.<ext>` filename under
the owning job directory. They SHALL NOT open the persisted absolute
`result.path`. The resolved artifact SHALL be a regular non-symlink file
confined to that directory. Missing files, unsupported formats, directories,
traversal, absolute external paths, and symlinks SHALL return the documented
404 error without exposing a filesystem location or serving external bytes.
Metadata and content routes SHALL use the same resolver.

#### Scenario: Persisted result points outside the workspace
- **WHEN** a succeeded job JSON contains an absolute external `result.path`
  or a traversal path and its expected internal artifact is absent or a
  symlink to external content
- **THEN** the result routes return 404 and never serve the external bytes

#### Scenario: Result is not a regular file
- **WHEN** the expected result path is missing, names a directory, has an
  unsupported format, or resolves outside the owning job directory
- **THEN** metadata and content routes return 404 without a local path in
  the error response

### Requirement: Remote result location privacy
REST responses SHALL NOT expose absolute server-local result paths. A
succeeded job embedded in job list/get responses and the result metadata
response SHALL carry a root-relative `download_url` of
`/jobs/{id}/result/content` instead of `path`. Persisted job JSON and
standalone CLI output SHALL retain their local `result.path` for local use.

#### Scenario: Client inspects a succeeded job remotely
- **WHEN** a client calls `GET /jobs`, `GET /jobs/{id}`, or
  `GET /jobs/{id}/result` for a succeeded job
- **THEN** every result location is a relative download URL and no absolute
  server-local path is present

#### Scenario: Local user inspects the same job through CLI
- **WHEN** a local user runs `metawarc jobs get` or `jobs wait`
- **THEN** the CLI continues to report the persisted local `result.path`
  without requiring an HTTP download

### Requirement: Persistent JSON storage
Job state SHALL persist under `<data_dir>/jobs/<job_id>.json` with
atomic writes (`tempfile + os.replace`) so a partial write cannot
leave the catalog in a torn state. A job file that cannot be parsed SHALL be
skipped during discovery and retained unchanged for operator inspection; it
SHALL NOT block valid jobs or be assigned a synthetic lifecycle state.
Startup and periodic discovery SHALL eventually consider every eligible
pending and unclaimed running job rather than truncating recovery at the
list endpoint's default page size. Terminal jobs and their completed
result files SHALL survive recovery unchanged unless they are eligible
for the separately configured retention policy.

#### Scenario: Malformed job file does not block discovery
- **WHEN** a malformed JSON file and a valid pending job share the job store
- **THEN** the malformed file remains unchanged and the valid pending job is
  still discovered and executed normally

#### Scenario: Server restart resumes all eligible pending jobs
- **WHEN** the server is restarted while more than 50 jobs are `pending`
- **THEN** the new runner eventually picks up every pending job and runs
  them under the same per-runner concurrency and timeout bounds

#### Scenario: Running server recovers a crashed owner's job
- **WHEN** another server process exits while owning a `running` job and
  a surviving server is already watching the same workspace
- **THEN** the surviving server applies interrupted-job recovery without
  requiring its own restart

#### Scenario: Server restart preserves completed jobs
- **WHEN** the server is restarted while at least one unexpired job is
  `succeeded` or automatic retention is disabled
- **THEN** the job is still listed by `GET /jobs`, its metadata remains
  available through `GET /jobs/{id}/result`, and its bytes can be
  downloaded through `GET /jobs/{id}/result/content`

### Requirement: Safe terminal-job retention
The system SHALL provide one preview/apply pruning policy for expired terminal
jobs. Only a freshly read `succeeded`, `failed`, or `cancelled` job with a valid
`ended_at` strictly older than the configured cutoff SHALL be eligible. The
pruner SHALL acquire the existing per-job claim without waiting and re-check
eligibility before deletion. Pending, running, malformed, unclaimed-ineligible,
and actively claimed jobs SHALL remain untouched.

`metawarc jobs prune --retention-days N` SHALL preview without writes and
SHALL require `--apply` to delete. Manual zero SHALL select all eligible
terminal jobs. `METAWARC_JOB_RETENTION_DAYS` SHALL default to zero with
automatic cleanup disabled; a positive value SHALL enable startup and periodic
bounded cleanup using the same policy. Negative values SHALL be rejected.

Deletion SHALL use only validated ids and deterministic owned paths, SHALL NOT
follow persisted result paths or symlinks, and SHALL NOT recursively remove
unexpected directories or entries. Once pruned, job and result routes SHALL
return 404.

#### Scenario: Preview expired jobs
- **WHEN** an operator runs `metawarc jobs prune --retention-days 7` without
  `--apply`
- **THEN** the report identifies eligible and skipped jobs by id and reason and
  every lifecycle, progress, and result file remains unchanged

#### Scenario: Apply retention to an expired succeeded job
- **WHEN** an operator applies pruning to a succeeded job whose valid `ended_at`
  is older than the cutoff and whose claim is available
- **THEN** its lifecycle JSON, progress, and owned result artifacts are removed
  and subsequent job/result requests return 404

#### Scenario: Active job cannot be pruned
- **WHEN** another process owns a job claim or the freshly read job is pending
  or running
- **THEN** pruning skips that job without deleting or modifying its lifecycle,
  progress, staging, or result files

#### Scenario: Persisted path targets external content
- **WHEN** an expired job contains an absolute/traversal `result.path` or an
  owned artifact is a symlink to external content
- **THEN** pruning never follows that path or symlink and external content
  remains unchanged

#### Scenario: Automatic retention is not configured
- **WHEN** the server starts or its watcher runs with the default zero
  retention setting
- **THEN** no job or artifact is pruned and existing recovery behavior remains
  unchanged

#### Scenario: Cleanup backlog exceeds one batch
- **WHEN** positive automatic retention is configured and more than 50 expired
  terminal jobs exist
- **THEN** cleanup runs off the event loop in bounded batches of at most 50 and
  later periodic passes eventually consider the remaining jobs

### Requirement: Bearer-token discipline
Every job route SHALL require the same bearer-token discipline as the
existing remote-interfaces routes: no route accepts an unauthenticated
request when the server was started with a token, and a request with
an invalid or missing `Authorization` header returns 401. This applies
to both result metadata and result content.

#### Scenario: Authenticated server rejects anonymous `POST /jobs`
- **WHEN** the server was started with `--token` and a client calls
  `POST /jobs` without an `Authorization` header
- **THEN** the API returns 401 with the documented error envelope

#### Scenario: Result content requires valid authentication
- **WHEN** the server was started with `--token` and a client calls
  `GET /jobs/{id}/result/content` without a token or with an invalid token
- **THEN** the API returns 401 and no result bytes are sent

#### Scenario: Loopback bind without token accepts `GET /jobs/{id}`
- **WHEN** the server was started on a loopback bind without a token
- **THEN** `GET /jobs/{id}` returns the job state without requiring
  an `Authorization` header

### Requirement: Concurrent execution bound
The runner SHALL execute jobs under a semaphore of size
`ServerSettings.job_max_concurrent` (default 4) and SHALL queue
additional submissions until a worker is free. The bound applies per
runner process; independent runners MAY execute distinct jobs
concurrently but SHALL NOT execute the same job concurrently.

#### Scenario: More submissions than workers
- **WHEN** 50 jobs are submitted on a server with
  `job_max_concurrent=4`
- **THEN** at most 4 jobs are `running` in that runner at any moment and
  the rest remain `pending` until a worker frees up

#### Scenario: Two runners share a workspace
- **WHEN** two runners with independent semaphores poll one workspace
- **THEN** each job has at most one executing owner while each runner's
  own configured concurrency bound remains enforced

### Requirement: Per-job timeout
Every running job SHALL be awaited under `asyncio.wait_for(...)` with
a timeout of `ServerSettings.job_timeout_seconds` (default 300). A
timeout SHALL mark the job `failed` with `error="timeout"` and SHALL
release the worker.

#### Scenario: Job exceeds the timeout
- **WHEN** a job handler runs longer than
  `ServerSettings.job_timeout_seconds`
- **THEN** the job's state becomes `failed`, `error="timeout"`,
  and the runner continues with the next pending job

### Requirement: REST routes
The server SHALL expose:
- `POST /jobs` (auth required) — submit a job; returns 201 with the
  job id
- `GET /jobs` (auth required) — list jobs, paginated, filterable by
  `--status`
- `GET /jobs/metrics` (auth required) — return retained-job operational
  aggregates without exposing per-job payloads or local paths
- `GET /jobs/{id}` (auth required) — return the job state or 404
- `GET /jobs/{id}/result` (auth required) — return non-sensitive result
  metadata and `download_url` when the job is `succeeded`, 409 otherwise
- `GET /jobs/{id}/result/content` (auth required) — stream the validated
  result artifact with bounded memory when the job is `succeeded`,
  return 409 otherwise and 404 when the artifact is missing or unsafe
- `DELETE /jobs/{id}` (auth required) — cancel a `pending` or
  `running` job, return 409 if the job has already finished

#### Scenario: Submit returns the job id
- **WHEN** a client `POST /jobs` with a valid body
- **THEN** the response is 201 and the body carries the job id and
  the initial `pending` status

#### Scenario: Result routes refuse non-succeeded jobs
- **WHEN** a client calls either result route while the job is `pending`,
  `running`, `failed`, or `cancelled`
- **THEN** the route returns 409 with the current status and sends no
  artifact bytes

#### Scenario: Download a completed JSON, CSV, or Parquet export
- **WHEN** an authenticated client follows `download_url` for a succeeded
  export
- **THEN** the response streams the exact artifact bytes with the mapped
  media type, actual content length, a safe attachment filename, and
  `Cache-Control: no-store` without exposing the local path

### Requirement: CLI surface
The `metawarc jobs` subcommand group SHALL expose `submit`, `list`,
`get`, `wait`, `cancel`, `metrics`, and `prune` and SHALL preserve the persisted
job JSON lifecycle fields shared with REST. The `wait` subcommand SHALL poll
the local `<data_dir>/jobs/` directory at a configurable interval and
SHALL exit with the documented code on success, failure, cancellation,
and timeout. It SHALL support optional stderr progress without changing
final stdout JSON. While `metawarc serve` is running, it SHALL observe
the shared job store and execute standalone CLI submissions without a
restart. CLI output SHALL retain a local `result.path`, whereas REST
result locations SHALL use `download_url`. The `prune` subcommand SHALL
preview by default and require `--apply` for deletion. The `metrics`
subcommand SHALL NOT start a runner or schedule work.

#### Scenario: Running server discovers a standalone CLI submission
- **WHEN** a user submits a job through `metawarc jobs submit` while
  `metawarc serve` is running against the same workspace
- **THEN** the running server schedules the persisted pending job
  without requiring a restart

#### Scenario: `metawarc jobs submit` returns the id
- **WHEN** a user runs `metawarc jobs submit export-records
  --format=csv --mimes <some>'
- **THEN** the CLI prints the new job id and exits 0

#### Scenario: `metawarc jobs wait` exits with 124
- **WHEN** a user runs `metawarc jobs wait <id> --timeout 1` against
  a job that never finishes
- **THEN** the CLI exits with the documented timeout code (124,
  mirroring `timeout(1)`)

#### Scenario: Prune preview is non-destructive
- **WHEN** a user runs `metawarc jobs prune --retention-days 0` without
  `--apply`
- **THEN** all eligible terminal jobs are reported but none is deleted

### Requirement: Retained-job operational metrics
The system SHALL provide a read-only aggregate view of retained jobs containing
`generated_at`, `limit`, `total`, `included`, `truncated`, counts for every
lifecycle status (`pending`, `running`, `succeeded`, `failed`, `cancelled`), an
`invalid` count, and `queue_wait_seconds` and `execution_seconds` summaries.
Each timing summary SHALL contain `samples`, `mean`, and `max`.

The default limit SHALL be 1,000 with an allowed range of 1–10,000. The newest
valid retained jobs by `created_at`, using job id as a deterministic tie-breaker,
up to the limit SHALL contribute to status and timing aggregates. `total` SHALL
count all valid retained jobs observed, `included` SHALL count the selected
jobs, and `truncated` SHALL be true exactly when `included < total`. Status
counts SHALL sum to `included`. Invalid candidates SHALL increment `invalid`
and SHALL NOT be treated as a lifecycle status.

A valid timezone-aware `created_at` SHALL be required for deterministic
selection; a candidate without one SHALL be structurally invalid. Queue wait
SHALL be `started_at - created_at` when both timestamps are valid and the
duration is non-negative. Execution time SHALL be `ended_at - started_at` for
terminal jobs when both timestamps are valid and the duration is non-negative.
Missing, naive, or malformed `started_at`/`ended_at` values and negatively
ordered duration pairs SHALL be excluded only from the affected timing summary.
A summary with no samples SHALL have `samples=0`, `mean=null`, and `max=null`;
metrics responses SHALL NOT contain NaN or infinity.

Metrics SHALL be derived from retained state without a persistent event history.
Pruned jobs SHALL be excluded from later observations, and responses SHALL NOT
claim all-time history or a transactional cross-file snapshot.

#### Scenario: Mixed retained jobs
- **WHEN** retained jobs include all lifecycle states and valid timestamps
- **THEN** the response counts each selected status, sums counts to `included`,
  and reports the exact accepted queue/execution samples with their arithmetic
  mean and maximum

#### Scenario: No timing samples
- **WHEN** the store is empty or no included job has a valid duration pair
- **THEN** the affected summary has zero samples and null mean/max, all declared
  status keys remain present, and no non-finite number is emitted

#### Scenario: Retained history exceeds the limit
- **WHEN** more valid retained jobs exist than the requested limit
- **THEN** only the deterministic newest subset contributes to counts/timings,
  `total` reports every valid job observed, `included` equals the limit, and
  `truncated` is true

#### Scenario: Pruned and invalid jobs
- **WHEN** a terminal job has been pruned and another direct job candidate is
  malformed, oversized, unreadable, a symlink, or structurally invalid
- **THEN** the pruned job contributes nothing, the invalid candidate increments
  `invalid` without following a symlink or blocking other observations, and no
  historical value is reconstructed

### Requirement: Job metrics interfaces
The server SHALL expose authenticated `GET /jobs/metrics` with a bounded `limit`
query parameter, and the CLI SHALL expose `metawarc jobs metrics --limit N`.
Both interfaces SHALL use the same store-level calculation and response
contract. The REST route SHALL be registered before `GET /jobs/{job_id}`, SHALL
return 422 for invalid limits, and SHALL run blocking filesystem work off the
event loop. CLI metrics SHALL emit one JSON document on stdout and SHALL NOT
start a runner or schedule jobs.

The calculation SHALL inspect only direct lifecycle JSON candidates, read at
most 1 MiB per candidate, reject symlinks and non-regular files without following
them, and retain only the bounded selection plus fixed-size accumulators. It
SHALL NOT claim, save, cancel, recover, schedule, or prune jobs and SHALL NOT
expose job ids, inputs, errors, local paths, or progress paths.

#### Scenario: Authenticated client reads metrics
- **WHEN** an authenticated client calls `GET /jobs/metrics?limit=1000`
- **THEN** it receives the typed aggregate response without filesystem paths or
  per-job sensitive payloads, and the blocking calculation runs off the event
  loop

#### Scenario: Metrics require the existing authorization policy
- **WHEN** the server has a token and a client requests `/jobs/metrics` without
  a token or with an invalid token
- **THEN** the API returns 401 with the documented error envelope and no metrics

#### Scenario: Metrics route is not a job id
- **WHEN** a client requests `GET /jobs/metrics`
- **THEN** the metrics handler responds rather than the dynamic job-get handler
  looking up a job whose id is `metrics`

#### Scenario: CLI reads metrics without executing work
- **WHEN** a user runs `metawarc jobs metrics --limit 1000`
- **THEN** stdout is one valid metrics JSON document, pending jobs remain
  unscheduled, and lifecycle/progress/result files are not modified

#### Scenario: Metrics race with lifecycle changes and pruning
- **WHEN** jobs complete, are cancelled, recovered, or pruned during calculation
- **THEN** the result remains a valid bounded observation or omits a disappeared
  file, no non-finite statistic is emitted, and the calculation performs no
  lifecycle or artifact mutation