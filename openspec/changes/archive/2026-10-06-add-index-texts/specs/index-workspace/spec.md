## ADDED Requirements

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