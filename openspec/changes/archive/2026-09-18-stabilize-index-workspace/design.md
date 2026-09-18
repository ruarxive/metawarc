## Context

The current catalog records source paths and sidecar paths but does not own an
explicit workspace root or schema version. Sidecars use basenames on `master`
and fresh UUIDs on `testing`. Both implementations build unbounded Python lists
and register output only after processing an entire source.

## Goals / Non-Goals

- Goals:
  - make repeated indexing deterministic and idempotent;
  - make database/sidecar lookup independent of the current directory;
  - bound memory use and make interruption recoverable;
  - distinguish successful, partial, failed, stale, and skipped archive states;
  - provide diagnostics and migration behavior before schema changes ship.
- Non-Goals:
  - implement content search or collection analytics;
  - expose arbitrary SQL;
  - copy WARC payloads into the workspace.

## Decisions

### Decision: The database and sidecars form one workspace

By default, the workspace root is derived from the database path. A user can
override the sidecar directory explicitly. Paths inside the workspace are stored
relative to the workspace root; external source paths are normalized separately.
All commands resolve sidecars through catalog rows.

### Decision: Archive IDs are assigned once and persisted

On first registration the catalog assigns an opaque archive ID. Later runs find
the existing row by normalized source identity and compare a fingerprint made
from size, modification time, and optionally a content digest. Duplicate
basenames remain independent. Moving a source requires an explicit catalog
rebind operation or a verified fingerprint match.

### Decision: Modes have separate semantics

- `add`: register only sources not already present;
- `update`: process new sources and changed existing sources;
- `rescan`: rebuild selected derived tables while retaining archive identity;
- `force`: rebuild even when the fingerprint appears unchanged.

The CLI must not model a default-true boolean as a one-way flag.

### Decision: Batch writes are atomic at sidecar granularity

Record/header rows are converted into bounded Arrow batches. Writers target
temporary files under the workspace. A successful close and validation precedes
an atomic rename and catalog transaction. Checkpoints record the source,
fingerprint, last safe position, counts, and temporary outputs.

### Decision: Schema changes are versioned

A catalog metadata table stores the schema version. Opening code either reads,
migrates, rebuilds, or rejects the version before issuing normal queries.
Migrations take a recoverable backup of catalog metadata and never delete WARC
sources.

## Risks / Trade-offs

- File modification time alone is not a reliable identity. Mitigation: combine
  attributes and support optional digests and explicit rebind.
- Compressed WARC offsets depend on the selected reader. Mitigation: use one
  tested offset abstraction per archive type and verify extraction after index.
- Atomic replacement is filesystem-dependent. Mitigation: require temporary and
  final files to share a filesystem and document unsupported layouts.
- Batch schemas can drift when metadata fields vary. Mitigation: define stable
  record/header schemas and version typed metadata separately.

## Migration Plan

1. Add schema detection without changing existing indexes.
2. Introduce the workspace resolver and catalog abstractions.
3. Add a migration that maps legacy source/table rows to stable archive IDs.
4. Preserve legacy sidecars until migrated rows validate successfully.
5. Add batch/atomic writers and checkpoint state.
6. Switch index, stats, query, and API paths to catalog resolution.
7. Offer `doctor --repair` only for recoverable catalog/path inconsistencies.

Rollback restores the catalog backup and leaves legacy sidecars untouched.

## Open Questions

- Should default fingerprints always include a sampled digest or only metadata?
- Which compressed WARC reader is canonical for offset creation and extraction?
- What maximum batch size balances Arrow overhead and memory use by default?
- Should moved-source fingerprint rebinding be automatic or always explicit?

