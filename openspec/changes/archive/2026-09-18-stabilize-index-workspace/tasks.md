## 1. Catalog and Workspace
- [x] 1.1 Define schema-version, archives, sidecars, runs, and checkpoints tables
- [x] 1.2 Implement workspace-root and sidecar-path resolution
- [x] 1.3 Implement stable persisted archive IDs and source fingerprints
- [x] 1.4 Add catalog transactions and archive processing states
- [x] 1.5 Implement legacy 1.2/1.3 detection and migration/rebuild guidance

## 2. Streaming Indexer
- [x] 2.1 Define stable Arrow schemas for records and headers
- [x] 2.2 Replace whole-archive lists with configurable bounded batches
- [x] 2.3 Write sidecars to temporary paths and atomically publish validated files
- [x] 2.4 Implement correct offsets for `.warc` and `.warc.gz`
- [x] 2.5 Handle missing/malformed headers per record without aborting the archive
- [x] 2.6 Handle empty/no-response archives without schema-less inserts
- [x] 2.7 Close every archive, writer, and database resource on all paths

## 3. Update Semantics and Recovery
- [x] 3.1 Implement explicit add, update, rescan, and force modes
- [x] 3.2 Preserve archive ID when refreshing or rescanning a source
- [x] 3.3 Write and resume from verified checkpoints
- [x] 3.4 Detect changed, missing, moved, and stale sources
- [x] 3.5 Remove or quarantine superseded sidecars only after commit

## 4. CLI and Diagnostics
- [x] 4.1 Normalize database/workspace options across index and stats commands
- [x] 4.2 Make silent mode suppress presentation only, not change indexing behavior
- [x] 4.3 Add human and JSON run summaries with counts, bytes, errors, and duration
- [x] 4.4 Add `doctor` checks for schema, sources, paths, Parquet readability, and orphans
- [x] 4.5 Add explicit repair/rebind actions with dry-run output

## 5. Verification
- [x] 5.1 Test compressed/uncompressed and silent/interactive combinations
- [x] 5.2 Test empty, no-response, malformed-header, and truncated inputs
- [x] 5.3 Test duplicate basenames and repeated add/update/rescan/force runs
- [x] 5.4 Test interruption, checkpoint resume, and atomic rollback
- [x] 5.5 Measure peak memory across increasing record counts
- [x] 5.6 Test commands from a directory other than the workspace

