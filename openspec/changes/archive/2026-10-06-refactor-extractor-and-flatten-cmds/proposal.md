# Change: Refactor the extractor registry and flatten the command namespace

## Why
The 2026-09-17 review (`PRODUCT_REVIEW_AND_IMPROVEMENT_PLAN.md`) flagged
`metawarc/cmds/extractor.py` as the largest single source of complexity in
the package and explicitly recommended an extractor-registry split **before**
the next format family lands. Since then, two archive changes have shipped:
`expand-media-format-extraction` (video, audio, fonts) and
`harden-metadata-extraction` (extractor hardening). The module has grown
from 1 389 LOC, 53 functions, and 13 classes (per the 2026-10-06 review's
function-count run) into the same shape, but with one more format family in
production. The next format change would push the module past 1 700 LOC.

The second half of the same maintainability concern is the partial
`cmds/` namespace. Four commands sit under `metawarc/cmds/` (`dump.py`,
`extractor.py`, `indexer.py`, `server.py`); four more sit at the package
top level (`analysis.py`, `replay.py`, `mcp_server.py`,
`ingestion.py`). Top-level modules reach back into `cmds/` for utilities:
`metawarc/analysis.py:20` imports `iter_payload` from
`metawarc.cmds.dump`, and `metawarc/replay.py:18` does the same.
A new contributor reading `core.py` cannot predict whether to look in
`cmds/` or at the top level for a given command.

The third concern is `metawarc/core.py:227`, which calls
`logging.basicConfig(...)` during the import of `core`. Library callers
that import `metawarc` without using the CLI cannot configure the logger
without `basicConfig` running first and possibly clobbering their own
handler chain. `core.py` is also 1 091 LOC and mixes Click command-group
wiring with report rendering (Rich tables, JSON emitters), which makes
the next command harder to add.

This change splits the extractor, flattens the namespace, and separates
logging/reporting from command wiring. None of these are user-visible
behavior changes; the public API surface (`metawarc.cli`,
`metawarc.mcp_server.create_mcp`, `metawarc.cmds.server.create_app`)
remains the same.

## What Changes
- Replace `metawarc/cmds/extractor.py` with a small registry package
  (`metawarc/extractor/`) plus per-format modules
  (`pdf.py`, `office.py`, `media.py`, `links.py`, `common.py`).
  The registry package owns the dispatch, normalization, envelope, and
  per-format selection logic; the per-format modules own only the
  format-specific helpers
- Move every command module out of `metawarc/cmds/` to the package
  top level (`metawarc/cmds/dump.py` → `metawarc/dump.py`,
  `metawarc/cmds/extractor/` becomes `metawarc/extractor/`,
  `metawarc/cmds/indexer.py` → `metawarc/indexer.py`,
  `metawarc/cmds/server.py` → `metawarc/api_server.py`). Public-API
  re-exports in `metawarc/__init__.py` keep `metawarc.cmds.server.create_app`
  and `metawarc.mcp_server.create_mcp` working without code changes for
  callers
- Remove the `logging.basicConfig` call from `metawarc/core.py:227`;
  move it into `metawarc/__main__.py` so library consumers retain full
  control of their logger configuration
- Move the Rich-table and JSON-emit rendering helpers from `core.py`
  into a new `metawarc/reporting.py` module so command wiring and
  report rendering are no longer in the same file
- Update imports in `metawarc/analysis.py`, `metawarc/replay.py`,
  `metawarc/ingestion.py`, `metawarc/core.py`, and the test suite to
  match the new layout
- No user-visible CLI, REST, or MCP behavior changes; coverage stays at
  the documented 87 % floor

## Impact
- Affected specs: `metadata-extraction`, `cli-progress`
- Affected code: `metawarc/cmds/extractor.py` (removed),
  `metawarc/cmds/{dump,indexer,server}.py` (moved), `metawarc/core.py`
  (reduced), `metawarc/__init__.py` (re-exports), new
  `metawarc/extractor/` package, new `metawarc/reporting.py`,
  `metawarc/__main__.py` (logging init), test imports
- Dependencies: `ship-2.0.2-and-cleanup` (so the rename ships in a
  published wheel) and `harden-network-binding-and-extend-test-coverage`
  (so the per-module coverage gate stays clean during the rename)