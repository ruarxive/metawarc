# incremental-ingestion Specification

## Purpose
TBD - created by archiving change add-incremental-ingestion. Update Purpose after archive.
## Requirements
### Requirement: Incremental source planning
Before mutation, an incremental run SHALL classify requested sources as add,
unchanged, update, missing, moved candidate, or conflict.

#### Scenario: Dry run is requested
- **WHEN** a user starts incremental ingestion with dry run enabled
- **THEN** the command reports planned actions and performs no catalog or
  filesystem mutation

### Requirement: Unchanged source avoidance
Incremental ingestion SHALL avoid reading record bodies from sources whose
registered fingerprint and required derived tables are current.

#### Scenario: Existing collection receives one new WARC
- **WHEN** all registered sources are unchanged and one source is new
- **THEN** only the new source is scanned and the unchanged sources are reported
  as skipped

### Requirement: Stable update behavior
A changed registered source SHALL be rebuilt under its existing archive identity
and SHALL retain its previous complete sidecars until replacement commits.

#### Scenario: Replacement fails validation
- **WHEN** a changed source produces an invalid replacement sidecar
- **THEN** the previous catalog revision remains active and the run records the
  failed update

### Requirement: Verified checkpoints
The system SHALL persist checkpoints containing source fingerprint, reader
identity, safe position, completed batches, counts, and temporary output state.

#### Scenario: Resume state matches
- **WHEN** resume is requested and checkpoint validation succeeds
- **THEN** processing continues from the last safe point without duplicating
  committed records

#### Scenario: Source changed after interruption
- **WHEN** checkpoint fingerprint differs from the current source
- **THEN** the checkpoint is rejected and the source is restarted or requires
  explicit user action

### Requirement: Single-writer workspace
Only one process SHALL mutate an index workspace at a time, while readers SHALL
continue using the last committed catalog revision.

#### Scenario: Second writer starts
- **WHEN** a workspace mutation lock is already held
- **THEN** the second writer exits without modifying state and reports the active
  run identity

### Requirement: Auditable run manifest
Every incremental run SHALL persist its inputs, planned actions, completed
actions, skips, failures, counts, bytes, timestamps, and resulting revision.

#### Scenario: Run completes with mixed outcomes
- **WHEN** some sources update, some skip, and one fails
- **THEN** the manifest records each outcome and the catalog contains only
  atomically committed actions

### Requirement: Safe retired-state cleanup
Superseded and interrupted files SHALL be removed only by a retention-aware
cleanup operation that preserves the last complete catalog revision.

#### Scenario: Cleanup previews candidates
- **WHEN** cleanup runs in dry-run mode
- **THEN** it lists retired and temporary candidates with reasons and removes
  none of them

