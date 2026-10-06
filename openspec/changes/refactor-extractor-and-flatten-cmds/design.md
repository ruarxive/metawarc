## Context
The 2026-09-17 review flagged three maintainability watchlist items that
have aged into the actionable range on `master` at `b272283`:

1. `metawarc/cmds/extractor.py` is 1 389 LOC, 53 functions, 13 classes.
   The module owns extraction for PDF, OOXML, OLE, image, video, audio,
   font, and link families. The 2026-09-17 review said: "if the next
   format family lands, introduce an extractor registry before adding a
   fourth dispatch table." Two archive changes have shipped since then
   (`expand-media-format-extraction`, `harden-metadata-extraction`),
   and a third format family is queued for the next release cycle.
2. The command namespace is split: four command modules live under
   `metawarc/cmds/` (`dump.py`, `extractor.py`, `indexer.py`,
   `server.py`); four more live at the package top level
   (`analysis.py`, `replay.py`, `mcp_server.py`, `ingestion.py`).
   `analysis.py:20` and `replay.py:18` import `iter_payload` from
   `metawarc.cmds.dump`; `ingestion.py:10` imports `Indexer` and
   `IndexSummary` from `metawarc.cmds.indexer`. New contributors
   cannot predict the layout from any single rule.
3. `metawarc/core.py` is 1 091 LOC and mixes Click command-group
   wiring with `Console().print(...)` table renders, JSON emits, and
   the `logging.basicConfig(...)` call at line 227. Library consumers
   who import `metawarc` without going through the CLI cannot
   configure the logger without `basicConfig` running first.

This change reshapes the three concerns into a layout that mirrors the
service boundaries (`workspace.py`, `query.py`, `progress.py`,
`settings.py`, `api_models.py`, `errors.py` already live at the top
level; commands should follow the same pattern). The behavior of every
public CLI, REST, and MCP surface is preserved exactly.

## Goals / Non-Goals

- Goals:
  - split `metawarc/cmds/extractor.py` into a small registry package
    plus per-format modules so each module has a single
    responsibility;
  - flatten the `metawarc/cmds/` namespace so every command lives at
    the package top level, matching the existing service-layer
    convention;
  - remove the `logging.basicConfig` call from `metawarc/core.py`
    and move it to `metawarc/__main__.py`;
  - move the Rich-table and JSON-emit rendering helpers into a
    dedicated `metawarc/reporting.py` module;
  - preserve the public API of every existing symbol by re-exporting
    it from a small backward-compatibility shim, so third-party
    callers do not break in this release.
- Non-Goals:
  - changing user-visible CLI, REST, or MCP behavior;
  - introducing a new extractor signature or a new envelope shape
    (the versioned envelope requirement remains
    `metawarc.extractor.ExtractionResult` with the same fields);
  - changing the supported Python range or the package metadata;
  - rewriting the test suite (test files keep their current names and
    imports are updated mechanically).

## Decisions

### Decision: Registry package, not a single module

A registry that handles dispatch, normalization, envelope, and
format-specific logic in a single file is the shape that caused the
current 1 389-LOC module. Splitting into:

- `metawarc/extractor/__init__.py` (re-exports),
- `metawarc/extractor/common.py` (envelope, limits, signal helpers),
- `metawarc/extractor/registry.py` (dispatch),
- `metawarc/extractor/pdf.py`,
- `metawarc/extractor/office.py`,
- `metawarc/extractor/media.py`,
- `metawarc/extractor/links.py`

keeps each module under 500 LOC and groups related formats together.
The `media.py` module owns video, audio, and font extractors because
they share the binary-header detection helper; the `pdf.py` and
`office.py` modules own their document families because their parsing
paths differ materially.

### Decision: Flatten to top level, not move everything to `cmds/`

The existing service layer (`workspace.py`, `query.py`, `progress.py`,
`settings.py`, `api_models.py`, `errors.py`) lives at the package top
level. The convention is therefore "commands at the top level,
services at the top level." The alternative — moving every command
under `metawarc/cmds/` — would create a second service-layer group
and keep the partial-namespace problem.

### Decision: Backward-compatibility shim, not breaking change

`metawarc.cmds.server.create_app`,
`metawarc.cmds.dump.iter_payload`,
`metawarc.cmds.indexer.Indexer`, and
`metawarc.cmds.extractor.ContentIndexer` are public symbols that
might be imported by third-party tooling or downstream forks. The
change keeps them working through a small re-export shim and
removes the shim only in the next major release (after a
deprecation cycle).

### Decision: Logging init in `__main__.py`

`metawarc/__main__.py` is the documented CLI entry point. It is the
only place where `logging.basicConfig` is needed for the documented
`--verbose` behavior. Library consumers retain full control of
their own logger configuration.

### Decision: Dedicated `reporting.py` for renderers

The Rich-table renderers and JSON emitters are presentation logic,
not command wiring. Moving them to `metawarc/reporting.py` (under
250 LOC) leaves `core.py` to own the command group, options, and
exit-code translation. The split also makes future command additions
trivial: a new command imports its renderers from `reporting.py`
without growing `core.py`.

## Risks / Trade-offs

- The rename touches every test file's imports. Mitigation: the
  rename is mechanical (`sed -i 's/metawarc.cmds./metawarc./g'`), and
  the backward-compatibility shim catches anything missed.
- Per-module coverage floors from `harden-network-binding-and-extend-test-coverage`
  will move from `metawarc.cmds.server` to `metawarc.api_server` (and
  similarly for the other three). Mitigation: the floors are matched
  by module name; the rename updates the CI command list in the
  same PR.
- The registry split changes the file layout for any developer who has
  the old module open in their editor. Mitigation: the rename is
  one PR; the new file layout is stable thereafter.

## Migration Plan

1. Land `ship-2.0.2-and-cleanup` first.
2. Land `harden-network-binding-and-extend-test-coverage` next.
3. Land this change as a single PR on `master`.
5. Run the verification harness in §4 of `tasks.md` before merging.
6. Cut a minor release (e.g. 2.1.0) that ships the rename, and
   document the deprecation of the shim in `CHANGELOG.md`.

## Open Questions

- Should `metawarc/api_server.py` be the final name, or
  `metawarc/rest_server.py`? Recommendation: `api_server.py`
  because the existing comments and smoke-test script reference
  `metawarc.cmds.server`.
- Should the backward-compatibility shim live in
  `metawarc/__init__.py` or in a dedicated `metawarc/cmds.py`?
  Recommendation: a dedicated shim, because the symbols are
  CLI-server-specific and `__init__.py` should stay minimal.
- Should `metawarc/reporting.py` move to `metawarc/cli/reporting.py`
  in a future change? Recommendation: defer the question; the
  current placement keeps the reporting concerns next to the CLI
  consumers and is consistent with the existing `progress.py`
  placement.