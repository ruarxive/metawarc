## ADDED Requirements

### Requirement: Extractor package layout
The metadata extraction service SHALL be organized as a small registry
package plus per-format modules so that no single extractor module
exceeds a documented size budget.

#### Scenario: A new format family is added
- **WHEN** a contributor adds a new format family
- **THEN** the new extractor lives in its own per-format module under
  `metawarc/extractor/`, and the registry module grows by no more than
  the size of the registration entry

#### Scenario: An extractor module grows too large
- **WHEN** an extractor module under `metawarc/extractor/` exceeds
  500 lines of Python
- **THEN** the contributor splits the module before adding new
  functionality

### Requirement: Backward-compatible extractor imports
The pre-rename public symbols `metawarc.cmds.extractor.ContentIndexer`
and related entry points SHALL remain importable from their original
paths for one release cycle after the registry package is introduced.

#### Scenario: A downstream caller imports `metawarc.cmds.extractor`
- **WHEN** a third-party script imports
  `from metawarc.cmds.extractor import ContentIndexer` after the rename
- **THEN** the import resolves to the new `metawarc.extractor`
  implementation and the call site behaves identically

## MODIFIED Requirements

### Requirement: Extractor registry
The system SHALL select metadata extractors through a registry whose
entries declare supported MIME values, extensions, signature probes, and
schema version, and SHALL organize the registry as a small package of
per-format modules plus a single dispatch module.

#### Scenario: New extractor is registered
- **WHEN** an extractor implements the registry contract
- **THEN** it can be selected without adding format-specific branches to
  the WARC scanning service, and its implementation lives in a dedicated
  per-format file