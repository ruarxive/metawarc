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
`pending` → `running` → (`succeeded` | `failed` | `cancelled`). The
runner SHALL refuse to start a job whose file is malformed or whose
current state is not `pending`, and SHALL refuse to cancel a job
whose current state is `succeeded`, `failed`, or `cancelled`.

#### Scenario: Successful job
- **WHEN** a job completes without error
- **THEN** its state is `succeeded`, `ended_at` is populated, and
  `result` carries the result location and row count

#### Scenario: Job fails during execution
- **WHEN** the handler raises an unexpected exception
- **THEN** the job's state is `failed`, `error` carries the message,
  `ended_at` is populated, and the runner continues with the next
  pending job

#### Scenario: Cancel a running job
- **WHEN** the runner receives a cancel for a `running` job
- **THEN** the job's state becomes `cancelled`, the running task is
  awaited with a bounded timeout, and subsequent `GET /jobs/{id}`
  reports the new state

### Requirement: Job kinds registry
The runner SHALL dispatch work by `JobKind`. The MVP SHALL register
exactly one kind, `export-records`, which materialises the result of
`QueryService.list_records(...)` into a single file under the
workspace's `jobs/` directory.

#### Scenario: Unknown kind is rejected
- **WHEN** a client submits a job whose `kind` is not in the registry
- **THEN** the runner returns a validation error naming the unknown
  kind and never writes the job file

#### Scenario: `export-records` writes the chosen format
- **WHEN** a client submits an `export-records` job with
  `format="csv"` and a bounded `RecordQuery`
- **THEN** the job's `result.path` points at the produced CSV file
  and `result.rows` equals the row count written

### Requirement: Persistent JSON storage
Job state SHALL persist under `<data_dir>/jobs/<job_id>.json` with
atomic writes (`tempfile + os.replace`) so a partial write cannot
leave the catalog in a torn state. On read, a job file that cannot be
parsed SHALL be treated as `failed` and SHALL NOT block the runner.

#### Scenario: Server restart resumes pending jobs
- **WHEN** the server is restarted while at least one job is
  `pending`
- **THEN** the new runner picks those jobs up on startup and runs
  them under the same concurrency and timeout bounds

#### Scenario: Server restart preserves completed jobs
- **WHEN** the server is restarted while at least one job is
  `succeeded`
- **THEN** the job is still listed by `GET /jobs` and the result
  file is still reachable through `GET /jobs/{id}/result`

### Requirement: Bearer-token discipline
Every job route SHALL require the same bearer-token discipline as the
existing remote-interfaces routes: no route accepts an unauthenticated
request when the server was started with a token, and a request with
an invalid or missing `Authorization` header returns 401.

#### Scenario: Authenticated server rejects anonymous `POST /jobs`
- **WHEN** the server was started with `--token` and a client calls
  `POST /jobs` without an `Authorization` header
- **THEN** the API returns 401 with the documented error envelope

#### Scenario: Loopback bind without token accepts `GET /jobs/{id}`
- **WHEN** the server was started on a loopback bind without a token
- **THEN** `GET /jobs/{id}` returns the job state without requiring
  an `Authorization` header

### Requirement: Concurrent execution bound
The runner SHALL execute jobs under a semaphore of size
`ServerSettings.max_concurrent` (default 16) and SHALL queue
additional submissions until a worker is free.

#### Scenario: More submissions than workers
- **WHEN** 50 jobs are submitted on a server with
  `max_concurrent=4`
- **THEN** at most 4 jobs are `running` at any moment and the rest
  remain `pending` until a worker frees up

### Requirement: Per-job timeout
Every running job SHALL be awaited under `asyncio.wait_for(...)` with
a timeout of `ServerSettings.request_timeout_seconds`. A timeout
SHALL mark the job `failed` with `error="timeout"` and SHALL release
the worker.

#### Scenario: Job exceeds the timeout
- **WHEN** a job handler runs longer than
  `ServerSettings.request_timeout_seconds`
- **THEN** the job's state becomes `failed`, `error="timeout"`,
  and the runner continues with the next pending job

### Requirement: REST routes
The server SHALL expose:
- `POST /jobs` (auth required) — submit a job; returns 201 with the
  job id
- `GET /jobs` (auth required) — list jobs, paginated, filterable by
  `--status`
- `GET /jobs/{id}` (auth required) — return the job state or 404
- `GET /jobs/{id}/result` (auth required) — stream the result file
  when the job is `succeeded`, return 409 otherwise
- `DELETE /jobs/{id}` (auth required) — cancel a `pending` or
  `running` job, return 409 if the job has already finished

#### Scenario: Submit returns the job id
- **WHEN** a client `POST /jobs` with a valid body
- **THEN** the response is 201 and the body carries the job id and
  the initial `pending` status

#### Scenario: Result route refuses non-succeeded jobs
- **WHEN** a client calls `GET /jobs/{id}/result` while the job is
  `pending`, `running`, `failed`, or `cancelled`
- **THEN** the route returns 409 with the current status

### Requirement: CLI surface
The `metawarc jobs` subcommand group SHALL expose `submit`, `list`,
`get`, `wait`, and `cancel` and SHALL write the same JSON shape the
REST endpoints return. The `wait` subcommand SHALL poll the local
`<data_dir>/jobs/` directory at a configurable interval and SHALL
exit with the documented code on success, failure, cancellation, and
timeout.

#### Scenario: `metawarc jobs submit` returns the id
- **WHEN** a user runs `metawarc jobs submit export-records
  --format=csv --mimes <some>'
- **THEN** the CLI prints the new job id and exits 0

#### Scenario: `metawarc jobs wait` exits with 124
- **WHEN** a user runs `metawarc jobs wait <id> --timeout 1` against
  a job that never finishes
- **THEN** the CLI exits with the documented timeout code (124,
  mirroring `timeout(1)`)