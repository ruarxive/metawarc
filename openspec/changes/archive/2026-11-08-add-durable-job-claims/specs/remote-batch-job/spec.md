## ADDED Requirements

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

## MODIFIED Requirements

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
- **THEN** the job is still listed by `GET /jobs` and the result file is
  still reachable through `GET /jobs/{id}/result`

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
