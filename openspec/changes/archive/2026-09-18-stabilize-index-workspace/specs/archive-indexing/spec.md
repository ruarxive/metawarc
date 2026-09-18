## ADDED Requirements

### Requirement: Supported WARC containers
The indexer SHALL process both uncompressed `.warc` and compressed `.warc.gz`
sources with equivalent record metadata and extractable offsets.

#### Scenario: Uncompressed archive is indexed silently
- **WHEN** a user indexes a valid `.warc` source with silent output enabled
- **THEN** the same records and headers are committed as in interactive mode and
  no progress presentation is emitted

#### Scenario: Compressed archive offset is reused
- **WHEN** a record indexed from `.warc.gz` is selected for extraction
- **THEN** the stored offset locates the same WARC record and payload

### Requirement: Stable archive identity
The catalog SHALL assign an archive identifier once and SHALL preserve it across
updates, rescans, and forced rebuilds of the same registered source.

#### Scenario: Same archive is indexed again
- **WHEN** an unchanged registered source is processed in update mode
- **THEN** its archive identifier remains unchanged and no duplicate catalog or
  sidecar rows are created

#### Scenario: Duplicate basename is added
- **WHEN** two sources in different directories share a filename
- **THEN** each receives a distinct archive identity and independent sidecars

### Requirement: Explicit processing modes
The CLI SHALL expose unambiguous add, update, rescan, and force behavior and
SHALL report the selected behavior before modifying catalog state.

#### Scenario: Changed source is updated
- **WHEN** update mode detects a changed fingerprint
- **THEN** the source is reprocessed under its existing archive ID and the prior
  complete sidecars remain usable until replacement commits

#### Scenario: Unchanged source is rescanned for metadata
- **WHEN** rescan selects a derived metadata type for an unchanged archive
- **THEN** only that selected derived sidecar is rebuilt

### Requirement: Bounded indexing memory
The indexer SHALL write record and header metadata in bounded batches whose size
does not grow with the total number of records in a source.

#### Scenario: Large archive is scanned
- **WHEN** record count exceeds multiple configured batches
- **THEN** completed batches are released after writing and peak buffered row
  count remains within the documented batch bound

### Requirement: Per-record fault isolation
Malformed or unsupported individual records SHALL be counted and reported
without aborting other valid records unless archive framing can no longer be
read safely.

#### Scenario: Response lacks an optional HTTP header
- **WHEN** a response record is missing an optional content header
- **THEN** the index stores a null normalized value and continues scanning

#### Scenario: Required WARC framing is corrupt
- **WHEN** the reader cannot find the next safe record boundary
- **THEN** the run is marked failed or partial, its incomplete outputs are not
  registered as complete, and a diagnostic identifies the source position

### Requirement: Empty archive handling
An archive with no indexable response records SHALL produce valid catalog state
without constructing a schema-less Parquet or Arrow table.

#### Scenario: Archive has no response records
- **WHEN** the scan completes with zero indexable responses
- **THEN** the archive is registered with zero records and no invalid sidecar
  catalog row is inserted

