# Design: Durable progress and safe job retention

## Context and assumptions
The exporter already computes a matching-row count and checks cancellation at
256-row natural streaming boundaries. The runner owns an OS-backed per-job
claim until terminal state is saved. Cancellation can rewrite the main job JSON
while the exporter is active, so progress must not be saved by rewriting a
stale `Job` object.

Automatic retention is opt-in. A manual prune is a preview unless `--apply` is
present. This proposal covers only `export-records` progress and terminal job
cleanup; it does not introduce a general metrics system.

## Durable progress contract
A job view gains one additive field:

```json
"progress": {
  "processed_rows": 256,
  "total_rows": 50000,
  "updated_at": "2026-11-07T04:00:00+00:00"
}
```

Before the first update, `progress` is `null`. `total_rows` is the number the
current export plans to write: the matching count adjusted for the selected
offset and capped by the requested limit. It is not the larger `result.total`
match count. A planned empty export uses `0/0`; clients must not invent a
percentage or ETA when no meaningful denominator exists.

Progress lives at `<data_dir>/jobs/<id>/progress.json` and is written with the
same tempfile-plus-`os.replace` discipline as lifecycle state. It is internal
operational state, not a second lifecycle authority. The initial `0` update is
written before rows are consumed, followed by updates at the existing 256-row
batch boundaries and a final update before result publication. Only the runner
that owns the job claim writes it.

The writer preserves these invariants:

- `processed_rows` is monotonic within one job and never exceeds the planned
  total;
- cancellation and terminal-state checks remain authoritative and progress
  never changes job status or resurrects a terminal job;
- failed/cancelled/interrupted jobs retain their last durable count for
  diagnostics, but a new retry starts a separate progress history;
- a progress-write failure fails the export and removes its staged result
  rather than silently promising durable progress that was not saved;
- no extra WARC scan or unbounded event buffer is introduced.

REST list/get and CLI list/get/wait JSON merge the sidecar into their response
projection; they do not mutate the main job JSON. Reads are bounded by the
existing job-list page size. `GET /jobs/{id}/result` is unchanged because its
`rows` field is already final result metadata.

`jobs wait` converts the current snapshot to the existing presentation-neutral
`ProgressEvent` and `RichProgressRenderer`. Progress goes only to stderr and is
coalesced by the existing renderer. Auto mode displays it only for interactive
stderr; `--progress` forces it and `--no-progress` suppresses it. The terminal
job JSON on stdout and existing exit codes remain unchanged.

## Retention policy
`ServerSettings.job_retention_days` defaults to `0.0` and is populated from
`METAWARC_JOB_RETENTION_DAYS`. Negative values are rejected. Automatic cleanup
is disabled at zero. When positive, a job is eligible only when all conditions
hold:

1. its freshly read status is `succeeded`, `failed`, or `cancelled`;
2. its `ended_at` is valid and strictly older than `now - retention_days`;
3. its existing per-job claim can be acquired without waiting.

Pending, running, malformed, terminal-without-valid-`ended_at`, and actively
claimed jobs are skipped. Eligibility is checked again after claim acquisition
so a preview or stale directory listing cannot authorize deletion.

The same store-level policy supports the CLI:

```bash
metawarc jobs prune --retention-days 7
metawarc jobs prune --retention-days 7 --apply
```

Preview reports candidate, skipped, and would-delete/delete counts by job id
and reason, without performing writes. Manual zero selects all eligible
terminal jobs. Apply returns the actual deleted/skipped outcome. No REST prune
route is added.

## Safe deletion and scheduling
Deletion uses the validated job id and deterministic paths below the owning
job directory. It never opens or deletes `result.path`. The public job JSON is
removed first so the job immediately leaves list/get/discovery. The pruner then
removes only owned progress, known result artifacts, and incomplete staging
files. Symlinks are unlinked, never followed; directories and unexpected
entries are not recursively removed. The lock is released before its file and
an empty job directory are removed. A later pass may clean known orphaned
artifacts after a crash, under the same claim and containment checks.

Consequently, after retention a job and its result routes return 404. An
in-flight download has normal concurrent-file-deletion semantics and must not
be used as proof that the job still exists; no download lease or resumable
transfer is added in this slice.

The server invokes the shared pruner at startup and at most once per 60 seconds
from its existing watcher. Filesystem work runs off the event loop and each
pass considers at most 50 candidates; later passes eventually handle a larger
backlog. No new interval setting or cleanup service is introduced. Multiple
servers are serialized by the existing per-job claims.

## Compatibility and migration
Existing jobs need no schema rewrite. Missing progress sidecars project as
`null`; old terminal jobs become eligible only when an operator configures a
positive automatic TTL or applies a manual prune. Automatic retention defaults
to disabled, so upgrade behavior is unchanged. REST and CLI additions are
additive, and local `result.path` remains until that job is pruned.

## Verification
- Prove progress for 0, 1, 256, 257, and 50 000 rows in all formats, including
  exact totals, monotonic updates, final counts, and no extra source scan.
- Race progress with CLI cancellation and owner-loss recovery; verify terminal
  state, result publication, staged cleanup, and final stdout/exit codes.
- Verify REST/CLI `null` and populated projections plus interactive, forced,
  disabled, and redirected `jobs wait` output.
- Prove preview makes no changes, manual zero, cutoff boundaries, disabled
  automatic retention, malformed timestamps, and batches beyond 50.
- Use two real processes to show that an active or locked job is not pruned;
  test absolute/traversal persisted paths, symlinks, unexpected entries, and
  crash leftovers without deleting external bytes.
- Repeat submit → progress → wait → download and prune → 404 workflows from an
  installed wheel. Run the complete quality gates and supported CI matrix;
  leave any unexecuted matrix item explicitly open.
