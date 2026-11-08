# Design: Retained-job operational metrics

## Context and assumptions
Every readable job already carries `created_at`, optional `started_at`, optional
`ended_at`, and one of five lifecycle statuses. Those fields are sufficient for
a useful operational summary without introducing another writer into the
cross-process lifecycle protocol.

Retention can delete terminal jobs and their progress/result artifacts. A
metrics response is therefore a view of jobs retained when the calculation
reads them, not an all-time report. The calculation is read-only and does not
acquire job claims or block execution, cancellation, recovery, or pruning.

## Response contract
REST and CLI expose the same JSON shape:

```json
{
  "generated_at": "2026-11-07T10:00:00+00:00",
  "limit": 1000,
  "total": 4,
  "included": 4,
  "truncated": false,
  "counts": {
    "pending": 1,
    "running": 1,
    "succeeded": 1,
    "failed": 1,
    "cancelled": 0
  },
  "invalid": 0,
  "queue_wait_seconds": {
    "samples": 3,
    "mean": 1.25,
    "max": 2.5
  },
  "execution_seconds": {
    "samples": 2,
    "mean": 4.0,
    "max": 6.0
  }
}
```

`total` is the number of valid retained jobs observed during the scan.
`included` is the number selected for `counts` and timing summaries, and
`truncated` is true exactly when `included < total`. Consequently, `counts`
sums to `included`, not to `total` when truncation occurs. `invalid` counts all
job candidates rejected during the scan and is not a lifecycle status.

The default limit is 1,000 and values outside 1–10,000 are usage/validation
errors. Selection uses the existing newest-first `created_at` convention, with
job id as a deterministic tie-breaker. A response never includes job inputs,
errors, ids, result paths, or progress paths.

## Timing semantics
All input timestamps used for selection or durations must be valid ISO 8601
values with explicit timezone information. Calculations use seconds and finite
JSON numbers. A valid timezone-aware `created_at` is required for deterministic
selection; a candidate without one is structurally invalid and increments
`invalid` rather than contributing a status count.

- Queue wait is `started_at - created_at` for an included job with both values
  available and `started_at >= created_at`. Pending jobs without a start and
  jobs cancelled before starting contribute no sample.
- Execution time is `ended_at - started_at` for an included terminal job with
  both values available and `ended_at >= started_at`. Running jobs contribute
  no execution sample.
- Missing, naive, or malformed `started_at`/`ended_at` values and negatively
  ordered duration pairs are excluded from the affected timing summary. They do
  not change status counts or invalidate an otherwise selectable job.
- `samples` counts only accepted durations. With no accepted durations, `mean`
  and `max` are null. No NaN or infinity is emitted and no percentile is
  inferred from these aggregates.

`generated_at` is a timezone-aware UTC timestamp for the observation. It does
not imply a transactional instant across every job file.

## Store calculation and bounds
The store owns one presentation-neutral calculation shared by REST and CLI. It
enumerates only direct lifecycle JSON candidates, rejects symlinks and
non-regular files without following them, and reads at most 1 MiB per candidate.
Unreadable, oversized, malformed, or structurally invalid candidates increment
`invalid`; a file disappearing during a concurrent prune is skipped rather than
reported as corruption.

Valid jobs are selected newest-first up to `limit`. The implementation may scan
the retained directory to determine `total`, deterministic ordering, and
`truncated`, but it processes one file at a time and retains only bounded
lightweight status/timestamp selections plus fixed-size counters/accumulators,
not full job inputs/results or an unbounded per-job event list. The limit bounds
response and aggregation memory; it is not a claim that directory enumeration
has constant cost.

REST runs the blocking calculation through `asyncio.to_thread`. Existing server
request/concurrency controls remain applicable. No background sampler,
additional timer, persistent aggregate file, or cross-process metrics lock is
introduced.

## Interfaces
`GET /jobs/metrics` is registered before `GET /jobs/{job_id}` so `metrics` is not
interpreted as a job id. It accepts only the bounded `limit` query parameter and
uses the existing bearer-token policy and error envelope. Invalid limits return
422; authenticated requests do not gain filesystem access.

`metawarc jobs metrics --limit N` calls the same store calculation and prints
one JSON document to stdout. Diagnostics, if any, go to stderr. The command does
not start a runner or schedule pending jobs.

Concurrent lifecycle updates can produce a best-effort operational observation:
a file may be read before one job changes and after another changes. This is
acceptable for backlog/duration monitoring and is explicitly not an atomic
cross-file snapshot. The calculation itself must never save, claim, cancel,
recover, or prune a job.

## Compatibility and migration
The change adds one REST route, typed response models, and one CLI command.
Existing routes and commands are unchanged. Old jobs with missing or invalid
optional timing fields still contribute to status counts but not to invalid
timing samples. Pruned jobs disappear from later `total` and aggregates; no
backfill or migration is attempted.

## Verification
- Use fixed timestamps to prove every status count, exact queue/execution
  samples, mean/max, newest-first ties, and empty/null summaries.
- Cover pending cancellation, running jobs, naive/malformed/future-ordered
  timestamps, malformed JSON, missing fields, oversized files, symlinks, and
  files disappearing during scanning.
- Verify limits 1 and 10,000, rejected 0/10,001, deterministic `total`,
  `included`, `truncated`, and no unbounded per-job collection.
- Prove REST authentication, validation, static-route precedence, off-event-loop
  execution, response privacy, and identical CLI/store output.
- Race metrics with cancellation, completion, and prune; assert valid bounded
  output and no lifecycle/progress/result mutations.
- Repeat `jobs metrics` and authenticated `GET /jobs/metrics` from an installed
  wheel after mixed exports and pruning. Run full quality gates and the
  supported CI matrix without claiming unexecuted coverage.
