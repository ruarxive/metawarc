## 1. Regression evidence
- [x] 1.1 Add a failing deterministic two-runner regression proving that
      two independent event loops can enter the same pending job.
- [x] 1.2 Add restart cases for an unclaimed `running` job, an actively
      owned `running` job, and more than 50 pending jobs.
- [x] 1.3 Record the pre-fix failures and verify that each fails for the
      intended ownership or recovery reason.

## 2. Durable claims
- [x] 2.1 Add the supported `filelock` dependency to core metadata and
      refresh `uv.lock` without unrelated dependency changes.
- [x] 2.2 Implement a narrowly scoped per-job claim abstraction with
      non-blocking acquisition, re-reading after acquisition, and release
      in `finally`.
- [x] 2.3 Route startup, watcher, and normal submission through the same
      claim path while preserving existing public job JSON and response
      models.
- [x] 2.4 Ensure the claim is retained until the handler has actually
      stopped and terminal state/result publication is complete.

## 3. Recovery
- [x] 3.1 Enumerate all eligible pending jobs without the presentation
      limit of 50 and retain the per-runner semaphore bound.
- [x] 3.2 Mark an acquired but unowned `running` job `failed` with
      `error="interrupted"` and `ended_at`; do not invoke its handler.
- [x] 3.3 Leave a running job untouched when its lock is owned, and
      preserve all terminal jobs and completed result files.
- [x] 3.4 Remove incomplete staged results during recovery without
      deleting another job's artifacts or a completed result.

## 4. Contract and guides
- [x] 4.1 Apply the `remote-batch-job` delta and update the batch-job
      guide with claim, crash-recovery, explicit retry, and local-lock
      semantics.
- [x] 4.2 Update the changelog and only the corresponding improvement
      plan items after their acceptance checks pass.

## 5. Verification
- [x] 5.1 Run focused claim/recovery tests plus all job CLI and REST
      tests; then run the full suite with coverage, Ruff, and mypy.
- [x] 5.2 Build and install the wheel in an isolated environment and run
      the 50 000-row JSON, CSV, and Parquet export scenario.
- [x] 5.3 Run real subprocess crash/recovery and concurrent-server smoke
      tests against the built artifact locally.
- [ ] 5.4 Run the new subprocess tests on the supported OS and Python CI
      matrix after the change is pushed.
- [x] 5.5 Run documentation and strict OpenSpec builds, package builds,
      `pip check`, `uv lock --check`, `git diff --check`, and dependency
      audits for the changed runtime closure.
