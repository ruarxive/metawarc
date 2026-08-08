## Context

Stable archive identities and atomic sidecars make safe incremental operation
possible, but the orchestration still needs run-level planning, checkpoints, and
concurrency rules. A checkpoint must match the exact source fingerprint and
writer state before it can be trusted.

## Goals / Non-Goals

- Goals:
  - ingest new crawl segments without revisiting unchanged archives;
  - resume verified interrupted work;
  - make changes previewable and auditable;
  - keep readers on a complete catalog revision during updates.
- Non-Goals:
  - synchronize remote object stores in the first implementation;
  - merge or rewrite WARC payloads;
  - permit multiple writers to mutate one workspace concurrently.

## Decisions

### Decision: Plan before mutation

An incremental run first compares requested sources with catalog identities and
fingerprints and produces actions: add, unchanged, update, missing, moved
candidate, or conflict. Dry run stops after this plan.

### Decision: Checkpoints are fingerprint-bound

Checkpoints contain run ID, archive ID, source fingerprint, reader position,
completed batch sequence, counts, and temporary sidecars. Resume is allowed only
when source and temporary output validation match the checkpoint.

### Decision: One writer, revisioned readers

A workspace lock prevents simultaneous mutation. Readers use the last committed
catalog revision while new sidecars are prepared. The catalog revision advances
only after all outputs for an archive action commit.

### Decision: Cleanup follows retention policy

Superseded sidecars are marked retired at commit and removed or quarantined by a
separate cleanup action. Interrupted temporary state is retained long enough for
resume according to configuration.

## Risks / Trade-offs

- Metadata-only fingerprints can miss changes. Mitigation: configurable digest
  policies and a force mode.
- Checkpointing compressed streams can be reader-specific. Mitigation: store and
  validate reader/version metadata and fall back to source restart.
- Single-writer locking reduces parallel ingestion. Mitigation: parallelize
  independent scanning only if one coordinator serializes catalog commits.

## Migration Plan

1. Add run manifests, revisions, and workspace locking.
2. Add dry-run planning over stable archive identities.
3. Add source-level checkpoint write and validation.
4. Add resume with duplicate-prevention tests.
5. Add retired-sidecar cleanup and retention policy.
6. Expose human and JSON summaries.

## Open Questions

- Should the first release resume within a compressed WARC or restart that source?
- What is the default retention period for resumable and retired files?
- Should digest computation be eager, sampled, or deferred to conflict cases?

