## ADDED Requirements

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
