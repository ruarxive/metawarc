## ADDED Requirements

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
