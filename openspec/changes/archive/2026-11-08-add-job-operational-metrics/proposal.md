# Change: Add retained-job operational metrics

## Why
Durable progress shows the state of one export, but operators still cannot see
queue backlog, terminal outcomes, or observed queue/execution durations across
jobs. Adding a small derived operational view is the remaining batch-operations
slice before considering additional job kinds.

The job store is retention-based rather than a permanent event history. Metrics
must therefore describe exactly which retained jobs were included and must not
invent historical totals after pruning.

## What Changes
- Add one read-only store-level metrics calculation over retained job JSON.
  Report `generated_at`, `limit`, `total`, `included`, `truncated`, counts for
  all five lifecycle states, an `invalid` count, and timing summaries for
  `queue_wait_seconds` and `execution_seconds`.
- Derive queue wait from `started_at - created_at` and execution time from
  `ended_at - started_at`. Each timing summary reports `samples`, `mean`, and
  `max`; empty summaries use zero samples and null statistics.
- Select the newest valid retained jobs by `created_at`, up to a caller limit
  (default 1,000, allowed range 1–10,000). `total` counts all valid retained
  jobs observed, `included` counts jobs contributing to status/timing
  aggregates, and `truncated` reports whether valid jobs were excluded by the
  limit. Invalid files are counted separately and never become lifecycle
  statuses.
- Add authenticated `GET /jobs/metrics?limit=N` and `metawarc jobs metrics
  --limit N`, both returning the same response contract. CLI output
  remains machine-readable JSON on stdout.
- Compute filesystem-backed metrics off the REST event loop, one job file at a
  time with bounded per-file reads and bounded aggregate memory. Do not add a
  metrics database or rewrite lifecycle/progress state.
- Document that pruning removes jobs from subsequent observations, concurrent
  lifecycle changes do not form a cross-file transaction, and these metrics are
  operational observations rather than billing or audit records.

## Non-goals
- No persistent time-series, Prometheus/OpenTelemetry exporter, histograms,
  percentiles, throughput rates, ETA, alerting, or external metrics service.
- No per-kind breakdown, new job kind, automatic retry, retention change, or
  modification of per-job progress.
- No global cross-file snapshot lock and no guarantee that pruned historical
  data can be reconstructed.
- No MCP surface in this slice.

## Impact
- Affected spec: `remote-batch-job`.
- Affected code: job-store metrics aggregation, typed REST response/routing,
  CLI jobs commands, and documentation.
- Affected tests: mixed/empty stores, timing boundaries, malformed and oversized
  files, deterministic limits, pruning, concurrent reads, authentication, CLI
  stdout, route precedence, and installed-wheel workflows.
- Compatibility: additive REST route and CLI command; existing job JSON,
  lifecycle, progress, result download, cancellation, and retention contracts
  remain unchanged. No migration is required.
