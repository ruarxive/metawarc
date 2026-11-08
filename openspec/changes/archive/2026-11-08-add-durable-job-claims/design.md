# Design: Durable job claims and restart recovery

## Context
`JobStore.save()` makes an individual JSON replacement atomic, but a
read/check/save sequence is not a cross-process transaction. The current
store watcher repeats that sequence in every running server. A claim
must therefore coordinate processes independently of the job JSON file.

The workspace is local-first. The proposed guarantee applies to local
filesystems with functioning OS-backed locks; it does not pretend that a
JSON directory on an arbitrary network filesystem is a distributed job
queue.

## Decision: per-job OS-backed locks
Each job has a private lock file under its existing job directory, next
to its staged/final result. The runner opens it through `filelock` and
uses non-blocking acquisition. The filename is derived only from the
already validated job id.

The claim protocol is:

1. Try to acquire the job lock without waiting.
2. If acquisition fails, leave the job untouched; another runner may own
   it.
3. Re-read the job JSON only after acquiring the lock.
4. If it is `pending`, persist `running`, `started_at`, and the existing
   fields before invoking the handler.
5. If it is terminal, perform no execution and release the lock.
6. If it is `running`, the lock proves there is no active owner. Persist
   `failed`, `error="interrupted"`, and `ended_at`; clean incomplete
   staged output and do not invoke the handler.
7. Hold the lock through terminal-state persistence and actual handler
   shutdown, then release it in `finally`.

There is no timeout-based stale-lock detection. OS lock release on
process exit distinguishes a dead owner without guessing from wall-clock
time. A long-running or suspended live process retains ownership.

A lock file may remain after process exit; its existence alone is not a
claim. Only successful lock acquisition grants ownership.

## Watcher and startup
Startup and the existing periodic watcher share the same claim path, so
there is no startup-only implementation to drift. Enumeration must not
truncate recovery at the store's presentation default of 50. It may scan
job files incrementally, but must eventually consider every pending and
unclaimed running job.

The semaphore remains per runner. Two servers may execute different jobs
concurrently, each up to its own configured limit, but may not execute
the same job concurrently.

## Interrupted means failed, not automatic retry
A process crash does not reveal how much external work a handler did.
For exports, silently running the whole query again would also make
duplicate work and result replacement difficult to reason about. This
change therefore makes recovery deterministic:

- `pending`: eligible for execution;
- unclaimed `running`: `failed` with `error="interrupted"`;
- `succeeded`, `failed`, `cancelled`: unchanged.

A user retries an interrupted job by submitting a new job with the same
input. This adds no schema field or implicit retry budget. The initial
`started_at` remains as diagnostic evidence of the interrupted attempt;
`ended_at` records recovery.

## Handler and shutdown discipline
Cancelling an asyncio wrapper does not by itself stop a synchronous
`asyncio.to_thread` export. The runner must not release the claim while
its handler can still write or publish. The existing cooperative checks
and per-job temporary files remain mandatory. Final publication occurs
only while the owning handler is active; a recovered interrupted job is
terminal, so a stale handler cannot legitimately publish a final result.

Normal cancellation and timeout continue to persist their existing
terminal states. Crash recovery must not overwrite a terminal state
saved concurrently by the owner: re-reading after lock acquisition is
the authority.

## Dependency and compatibility
`filelock` becomes a direct core dependency because both CLI-only job
workflows and the optional API rely on the runner. No public JSON, REST,
or CLI fields are added. Lock artifacts are operational state and are
excluded from job list/get responses and exported record files.

## Verification strategy
Tests must prove the mechanism rather than only inspect fields:

- fail a pre-change two-runner race regression before implementing the
  claim;
- run two independent processes against one job and instrument the
  handler to prove exactly one invocation;
- kill a process while it owns a running job, then start another runner
  and assert `failed/interrupted`, `ended_at`, no handler retry, and no
  published partial result;
- keep an actively owned `running` job unchanged when another runner
  polls it;
- resume more than 50 pending jobs without exceeding each runner's
  concurrency limit;
- preserve successful and cancelled state/result files across restart;
- exercise CLI submission, cancellation, timeout, and all three export
  formats from the built wheel.
