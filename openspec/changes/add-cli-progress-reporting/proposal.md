# Change: Add progress reporting to long-running CLI commands

## Why
Long-running Metawarc commands provide little or no feedback while they scan
archives, extract typed content, hash payloads, or export many records.
`index` has a command-specific record counter, but `index-content` and other
bulk operations can appear stalled for long periods and there is no consistent
behavior across interactive, silent, and machine-readable invocations.

## What Changes
- Add a shared, service-neutral progress event interface and a Rich CLI renderer
- Show progress automatically for interactive long-running commands, with an
  explicit `--progress/--no-progress` override
- Report outer work (archives, metadata types, or selected records) and current
  work (records or bytes) when a useful total is available
- Cover `index`, applied `ingest`, `index-content`, `dump`, `dump-metadata`,
  `analyze hashes`, and `analyze integrity`
- Keep progress on stderr and suppress it in silent, JSON, and non-interactive
  auto modes so stdout remains stable and machine-readable
- Document progress behavior and test terminal, suppression, failure, and
  callback semantics

## Impact
- Affected specs: `cli-progress`
- Affected code: CLI option helpers and command adapters, indexer, incremental
  ingestion, typed metadata extraction/export, payload export, hashing, and
  integrity analysis
- Dependencies: existing `rich` dependency; no new runtime dependency
- Compatibility: existing `--silent` behavior and JSON result schemas remain
  unchanged

