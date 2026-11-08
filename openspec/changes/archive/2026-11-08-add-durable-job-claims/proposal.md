# Change: Add durable cross-process claims and explicit restart semantics

## Why
A running `metawarc serve` now discovers standalone CLI submissions, but
pending jobs are only read, not atomically claimed. Two server processes
using one workspace can therefore execute the same export and race to
replace its JSON state and result. Startup also resumes at most 50 jobs
and leaves a job that was `running` during a process crash in that state
indefinitely. These behaviors block the batch-lifecycle requirements in
the product improvement plan.

This change defines one durable ownership mechanism and an explicit
recovery policy before result download, retention, or additional job
kinds are added.

## What Changes
- Add a non-blocking, OS-backed lock for each job. A runner must hold the
  lock before changing `pending` to `running` and retain it until the
  handler has stopped and the terminal state has been persisted.
- Use a supported, cross-platform `filelock` release as a direct core
  dependency rather than implementing separate Unix and Windows locking
  primitives. Lock files are private runner state; public job JSON and
  response schemas do not change.
- Recover every persisted pending job rather than only the first 50,
  while retaining the configured per-runner concurrency limit.
- Treat an unclaimed persisted `running` job as interrupted: persist
  `failed` with `error="interrupted"` and `ended_at`, and remove any
  incomplete staged result. Do not silently retry an export with unknown
  progress.
- Let the existing store watcher recover an interrupted job when another
  server crashes after startup, not only during the next restart.
- Preserve successful, failed, and cancelled jobs and their existing
  result metadata. Cancellation and timeout behavior remain unchanged.
- Document single-job ownership, per-runner concurrency, explicit retry
  by submitting a new job, and the local-filesystem scope of the locking
  guarantee.

## Non-goals
- No automatic retry, attempt counter, lease expiration, or heartbeat.
- No exactly-once side-effect guarantee for future job kinds; handlers
  must still be read-only with respect to source archives and publish
  their own results atomically.
- No result-download route, retention/deletion policy, progress metrics,
  or additional job kind.
- No guarantee for network filesystems that do not provide reliable
  cross-process file-lock semantics.

## Impact
- Affected specs: `remote-batch-job`.
- Affected code: `metawarc/jobs.py`, job lifecycle documentation, and
  dependency metadata/lockfile.
- Affected tests: job store/runner unit tests, true multi-process claim
  and crash-recovery integration tests, and installed-wheel smoke tests.
- Compatibility: existing CLI commands, REST routes, public job JSON
  fields, and result formats remain unchanged. Interrupted running jobs
  now become observably `failed` instead of remaining `running` forever.

## Risks and Mitigations
- **A stale process could outlive its asynchronous wrapper.** Release a
  claim only after the handler has actually stopped; keep cooperative
  active-state checks and staged-result cleanup in place.
- **A lock failure could be mistaken for a crashed owner.** Only a
  successfully acquired lock authorizes recovery; failed acquisition
  leaves the persisted state untouched.
- **Platform behavior could differ.** Use a maintained cross-platform
  locking library and run claim/recovery tests in the supported OS and
  Python CI matrix.
- **A new dependency expands the runtime closure.** Add it explicitly to
  core metadata, refresh `uv.lock`, and run installation, dependency, and
  audit gates on the resulting wheel.
