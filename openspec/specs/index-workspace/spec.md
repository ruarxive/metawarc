# index-workspace Specification

## Purpose
Defines the catalog and Parquet sidecar layout that backs every command,
with an explicit workspace root that owns its database and data directory.
Legacy 1.2 and 1.3 layouts are detected and migrated, rebuilt, or
rejected with a documented user-visible message.
## Requirements
### Requirement: Explicit workspace root
Every index SHALL have an explicit workspace root that owns its catalog,
sidecars, temporary files, checkpoints, and run metadata.

#### Scenario: Command runs from another directory
- **WHEN** a user supplies an index database path while the current directory is
  outside its workspace
- **THEN** the command resolves and queries the correct registered sidecars

### Requirement: Catalog-resolved sidecars
Commands SHALL obtain sidecar paths from validated catalog entries and SHALL NOT
use a global `data/*` glob as the source of index membership.

#### Scenario: Two workspaces exist
- **WHEN** separate indexes have sidecars under different roots
- **THEN** a command for one database cannot read sidecars owned by the other

### Requirement: Versioned catalog schema
The workspace SHALL persist a catalog schema version and validate it before
normal reads or writes.

#### Scenario: Supported migration is available
- **WHEN** an older supported schema is opened for a write operation
- **THEN** the tool requests or performs the documented recoverable migration
  before normal processing

### Requirement: Atomic sidecar publication
A sidecar SHALL be registered as complete only after its temporary file is
closed, structurally validated, and atomically moved to its final path.

#### Scenario: Process stops during a batch write
- **WHEN** indexing is interrupted before sidecar publication
- **THEN** the previous complete sidecar remains registered and the partial file
  is identified as resumable or disposable temporary state

### Requirement: Workspace diagnostics
The CLI SHALL provide a non-destructive `doctor` command that validates schema,
source fingerprints, catalog paths, sidecar readability, checkpoints, and
orphan files.

#### Scenario: Catalog references a missing sidecar
- **WHEN** `doctor` finds a catalog path whose file is absent
- **THEN** it reports the affected archive and sidecar type and recommends a
  rescan without silently deleting catalog state

### Requirement: Recoverable repairs
Any automatic workspace repair SHALL support a dry run and SHALL avoid deleting
the only complete copy of catalog or sidecar metadata.

#### Scenario: Repair is previewed
- **WHEN** a user runs `doctor --repair --dry-run`
- **THEN** the command lists every proposed catalog and filesystem change and
  performs none of them

### Requirement: `texts` sidecar
The workspace SHALL recognise a `texts` sidecar kind whose Parquet
schema carries `archive_id`, `warc_id`, `source`, `url`, `language`,
and `text` columns, and SHALL publish it through the existing sidecar
catalog without a new schema migration.

#### Scenario: `texts` sidecar is published
- **WHEN** a `texts` sidecar is written for an archive
- **THEN** `workspace.active_sidecars("texts", [archive_id])`
  returns true and `workspace.active_sidecar_paths("texts", ...)`
  returns the path

### Requirement: Phrase search over the `texts` sidecar
The workspace SHALL expose a `search_text(phrase, limit=50)` method that
reads every active `texts` sidecar via a columnar Parquet scan and
matches phrases with a case-insensitive `ILIKE` predicate. The result
SHALL carry `archive_id`, `warc_id`, `source`, `url`, and a `snippet`
of the matched text, capped at the configured `ServerSettings.max_page`.

#### Scenario: Search against an empty sidecar
- **WHEN** a user runs `metawarc search <phrase>` before any
  `texts` sidecar exists
- **THEN** the workspace reports no hits rather than erroring

#### Scenario: Subsequent searches reuse the columnar scan
- **WHEN** a second search runs after the first
- **THEN** no additional state is created on disk; the scan is repeated
  against the existing sidecar

### Requirement: Rescan-aware text indexing
The text-indexing entry point SHALL skip an archive that already has an
active `texts` sidecar unless `rescan=True` is set, mirroring the
existing behaviour of the structured-metadata indexer.

#### Scenario: Text sidecar exists, rescan is False
- **WHEN** a user runs `metawarc content-index --text` over an archive
  that already has an active `texts` sidecar
- **THEN** the workspace reports the archive as skipped and writes no
  new `texts` sidecar

#### Scenario: Text sidecar exists, rescan is True
- **WHEN** the user passes `--rescan --text`
- **THEN** the workspace overwrites the existing `texts` sidecar with
  the freshly-indexed rows

