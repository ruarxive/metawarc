## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Persistent JSON storage
Job state SHALL persist under `<data_dir>/jobs/<job_id>.json` with
atomic writes (`tempfile + os.replace`) so a partial write cannot
leave the catalog in a torn state. On read, a job file that cannot be
parsed SHALL be treated as `failed` and SHALL NOT block the runner.
Startup and periodic discovery SHALL eventually consider every eligible
pending and unclaimed running job rather than truncating recovery at the
list endpoint's default page size. Terminal jobs and their completed
result files SHALL survive recovery unchanged.

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
- **WHEN** the server is restarted while at least one job is `succeeded`
- **THEN** the job is still listed by `GET /jobs`, its metadata remains
  available through `GET /jobs/{id}/result`, and its bytes can be
  downloaded through `GET /jobs/{id}/result/content`

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

### Requirement: REST routes
The server SHALL expose:
- `POST /jobs` (auth required) — submit a job; returns 201 with the
  job id
- `GET /jobs` (auth required) — list jobs, paginated, filterable by
  `--status`
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
`get`, `wait`, and `cancel` and SHALL preserve the persisted job JSON
lifecycle fields shared with REST. The `wait` subcommand SHALL poll the
local `<data_dir>/jobs/` directory at a configurable interval and SHALL
exit with the documented code on success, failure, cancellation, and
timeout. While `metawarc serve` is running, it SHALL observe the shared
job store and execute standalone CLI submissions without a restart. CLI
output SHALL retain a local `result.path`, whereas REST result locations
SHALL use `download_url`.

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
