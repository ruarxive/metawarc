# Change: Add incremental and resumable collection ingestion

## Why
Recurring crawls add new WARC files and occasionally replace or move existing
ones. Rebuilding an entire collection wastes time and risks duplicating catalog
state. Large archive scans also need a safe way to resume after interruption.

## What Changes
- Add new WARC sources without rescanning unchanged registered sources
- Detect changed, moved, missing, and replaced sources through fingerprints
- Persist run manifests and verified per-source checkpoints
- Resume interrupted scans without duplicating committed rows
- Serialize workspace mutations and make concurrent readers revision-aware
- Retire superseded sidecars only after replacements commit
- Provide preview and summary output for incremental operations

## Impact
- Affected specs: `incremental-ingestion`
- Affected code: catalog run/checkpoint state, index orchestration, CLI update and
  resume options, workspace locking, cleanup and diagnostics
- Dependencies: `stabilize-index-workspace`, `establish-quality-gates`

