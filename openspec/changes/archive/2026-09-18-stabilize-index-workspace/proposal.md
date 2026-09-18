# Change: Stabilize archive indexing and the index workspace

## Why
Current indexing depends on the process working directory, accumulates whole
archive metadata in memory, and has inconsistent behavior for uncompressed,
silent, empty, repeated, and interrupted scans. The candidate branch avoids
basename collisions with random IDs, but creates a new ID on every run and can
orphan old sidecars.

## What Changes
- Define a versioned workspace containing the DuckDB catalog and Parquet data
- Assign stable persisted archive identities and store source fingerprints
- Define explicit add, update, rescan, and force semantics
- Support compressed/uncompressed, silent/interactive, empty, and malformed input
- Write bounded batches to atomic sidecars with catalog transactions
- Add checkpoints, structured run summaries, and a `doctor` validation command
- Resolve sidecars through the catalog instead of hard-coded `data/*` globs
- **BREAKING**: introduce a versioned catalog schema and explicit migration or
  rebuild behavior for legacy indexes

## Impact
- Affected specs: `archive-indexing`, `index-workspace`
- Affected code: indexer, DuckDB schema/helpers, Parquet writers, CLI index and
  stats commands, path configuration, migrations, diagnostics
- Dependencies: `consolidate-release-baseline`

