# Change: Add durable job progress and safe retention

## Why
Batch exports expose only lifecycle state until they finish, and terminal job
JSON plus result artifacts currently accumulate forever. Users cannot tell how
far a large export has progressed, while operators have no bounded, safe way to
preview and remove expired job data. These are the remaining operational gaps
before additional job kinds; general metrics and new handlers are out of scope.

## What Changes
- Add an additive `progress` representation to REST and CLI job views:
  `processed_rows`, `total_rows`, and `updated_at`. It is `null` before the
  first durable update. The total is the planned export size, so percentages
  never use the larger unbounded number of matching records.
- Persist export progress in an atomic per-job sidecar rather than rewriting
  the lifecycle JSON from the worker thread. Update at the existing bounded
  export batches for JSON, CSV, and Parquet without another archive scan.
- Add `--progress/--no-progress` to `metawarc jobs wait`, reusing the existing
  stderr renderer and preserving final JSON on stdout. Non-interactive output
  remains free of animated progress by default.
- Add one opt-in server setting, `METAWARC_JOB_RETENTION_DAYS` (default `0`,
  disabled). When positive, expired terminal jobs are cleaned at startup and
  at a fixed periodic interval in bounded batches.
- Add `metawarc jobs prune --retention-days N`, which previews candidates by
  default and removes them only with `--apply`. Manual `0` means every terminal
  job with a valid `ended_at` is eligible; automatic `0` remains disabled.
- Delete only terminal jobs older than the cutoff. Acquire the existing job
  claim and re-read state before deletion, skip active/locked jobs, and never
  follow persisted result paths or delete through symlinks.
- Preserve lifecycle, cancellation, recovery, result-download, and local CLI
  path contracts. Main job JSON remains compatible; the progress sidecar and
  retention setting need no migration.

## Non-goals
- No new job kind, generic progress protocol for future handlers, operational
  metrics, rate/ETA API fields, REST deletion endpoint, or arbitrary recursive
  directory removal.
- No automatic retention by default and no cleanup of source WARCs, catalog
  tables, or unrelated workspace sidecars.
- No resume from the last progress count: an interrupted export still follows
  the documented failed/interrupted policy and requires a new job.

## Impact
- Affected specs: `remote-batch-job`; the existing stderr behavior reuses
  `cli-progress` without changing that capability.
- Affected code: job store/export progress persistence, REST/CLI projections,
  `jobs wait`, retention policy and pruning, server settings and lifecycle.
- Affected tests: progress boundaries and monotonicity, cancellation and
  recovery races, stdout isolation, dry-run/apply, cutoff eligibility,
  cross-process locks, symlink defenses, and installed-wheel workflows.
- Compatibility: REST and CLI job views gain an additive field; persisted
  lifecycle JSON and existing downloads remain unchanged until an operator
  explicitly enables or applies retention.
