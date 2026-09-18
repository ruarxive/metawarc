## Context

The services that do long-running work currently expose either no progress or
presentation-specific behavior. `Indexer` wraps its WARC iterator in `tqdm`,
while `ContentIndexer` and the bulk analysis/export paths print only after work
finishes. This makes nested operations such as multiple metadata types over
multiple archives especially opaque and couples terminal output to service
implementation.

Progress must coexist with JSON/JSONL output, redirected stdout, `--silent`,
library callers, errors, and archives for which an exact record total would
require an expensive pre-scan.

## Goals / Non-Goals

- Goals:
  - give interactive users immediate, continuously updated feedback;
  - make `index-content` progress clear across types, archives, and candidates;
  - use one event contract for indexing, extraction, export, and payload scans;
  - preserve clean stdout and existing machine-readable result schemas;
  - avoid an extra WARC scan or unbounded buffering just to compute a total.
- Non-Goals:
  - add progress to short catalog, query, single-record, repair-preview, server,
    or MCP commands;
  - expose live progress through REST or MCP in this change;
  - persist high-frequency progress events in the workspace catalog;
  - promise an ETA when the service cannot determine a meaningful total.

## Decisions

### Decision: Services emit structured events; the CLI owns rendering

Long-running service entry points accept an optional progress callback. Events
identify the operation and phase, contain a human label and unit, and include
monotonic `completed` plus optional `total` values and useful counters. A no-op
callback is the default, so programmatic callers do not gain terminal output.

The Click adapter translates events to a shared Rich progress renderer. This
removes the current direct `tqdm`/`print` presentation from service loops and
allows tests to verify event semantics without parsing animated terminal text.

### Decision: Auto mode is interactive and human-oriented

Long-running commands share a tri-state `--progress/--no-progress` option:

- omitted: render only when stderr is a terminal and the command is not silent
  or in a JSON output mode;
- `--progress`: request rendering even when terminal detection would disable it;
- `--no-progress`: disable rendering explicitly.

`--silent` and an explicitly machine-readable output mode take precedence over
`--progress`. Progress is written only to stderr. Result data and summaries
remain on stdout with their existing schemas.

### Decision: Prefer honest nested progress over artificial percentages

The renderer maintains a bounded set of tasks: an outer task for metadata types
or archives and a current task for records or bytes. Services use exact totals
already available from the catalog or query plan. When a total is unavailable,
the current task reports a counter, rate, and elapsed time without a percentage
or ETA. The implementation does not pre-scan a WARC merely to obtain a total.

For `index-content`, the outer task advances for every selected archive/type
pair, including skipped and failed pairs, while the current task advances for
each candidate catalog record inspected. Result-item counts remain separate
because one candidate HTML record may produce many links.

### Decision: Throttle rendering, not event correctness

Services may emit lightweight monotonic events at natural loop boundaries.
The terminal renderer coalesces refreshes to a bounded rate, while completion,
skip, failure, and final events are rendered immediately. This keeps hot loops
simple and makes callback consumers deterministic without excessive terminal
overhead.

### Decision: Always close progress presentation

The renderer is a context manager. Normal completion marks tasks complete;
exceptions and keyboard interrupts stop the live display before Click renders
the error. The underlying run summary and checkpoint behavior remains the
source of truth for completed, skipped, and failed work.

## Command Coverage

| Command | Outer progress | Current progress |
| --- | --- | --- |
| `index` | source archives | WARC records or input bytes |
| applied `ingest` | planned indexing actions | delegated index progress |
| `index-content` | metadata type/archive pairs | candidate records |
| `dump` | selected records | payload bytes when known |
| `dump-metadata` | selected metadata rows | rows written |
| `analyze hashes` | selected archives | payload records/bytes |
| `analyze integrity` | selected archives | checked records/bytes |

## Risks / Trade-offs

- Counting candidates can add a catalog query. Mitigation: reuse catalog
  counts/query filters and fall back to indeterminate progress if counting is
  not cheap.
- Animated output is brittle under redirection and tests. Mitigation: auto mode
  requires a terminal, output goes to stderr, and callback tests cover the core
  behavior independently.
- Multiple nested bars can become noisy. Mitigation: keep one outer task and one
  replaceable current task with concise labels.
- Existing `tqdm` output may differ visually. Mitigation: progress text is
  presentation rather than a stable output contract; summary/result schemas do
  not change.

## Migration Plan

1. Add the progress event contract, no-op callback, and Rich renderer.
2. Replace the indexer-specific `tqdm` wrapper with event emission.
3. Instrument content indexing first, then the remaining covered bulk paths.
4. Add shared CLI options and suppression rules without changing result output.
5. Document the behavior and retain `tqdm` only if another supported path still
   imports it; otherwise remove the unused dependency.

