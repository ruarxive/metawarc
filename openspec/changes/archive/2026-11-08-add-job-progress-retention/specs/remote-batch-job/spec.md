## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Persistent JSON storage
Job state SHALL persist under `<data_dir>/jobs/<job_id>.json` with
atomic writes (`tempfile + os.replace`) so a partial write cannot
leave the catalog in a torn state. On read, a job file that cannot be
parsed SHALL be treated as `failed` and SHALL NOT block the runner.
Startup and periodic discovery SHALL eventually consider every eligible
pending and unclaimed running job rather than truncating recovery at the
list endpoint's default page size. Terminal jobs and their completed
result files SHALL survive recovery unchanged unless they are eligible
for the separately configured retention policy.

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

### Requirement: CLI surface
The `metawarc jobs` subcommand group SHALL expose `submit`, `list`,
`get`, `wait`, `cancel`, and `prune` and SHALL preserve the persisted job
JSON lifecycle fields shared with REST. The `wait` subcommand SHALL poll
the local `<data_dir>/jobs/` directory at a configurable interval and
SHALL exit with the documented code on success, failure, cancellation,
and timeout. It SHALL support optional stderr progress without changing
final stdout JSON. While `metawarc serve` is running, it SHALL observe
the shared job store and execute standalone CLI submissions without a
restart. CLI output SHALL retain a local `result.path`, whereas REST
result locations SHALL use `download_url`. The `prune` subcommand SHALL
preview by default and require `--apply` for deletion.

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
