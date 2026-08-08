## ADDED Requirements

### Requirement: Revision-scoped reports
Every collection analysis report SHALL identify the workspace catalog revision,
analysis version, filters, limits, timestamps, and partial failure counts.

#### Scenario: Collection changes after a report
- **WHEN** a report is viewed after the workspace advances to a new revision
- **THEN** the report still identifies the exact earlier revision it analyzed

### Requirement: Collection summary dimensions
The system SHALL summarize record count and content bytes by MIME, extension,
HTTP status, host or domain, record date, and configurable size bucket.

#### Scenario: User requests extension summary
- **WHEN** a collection contains records with known, empty, and null extensions
- **THEN** the report includes deterministic groups for all three states and
  totals reconcile with the selected record set

### Requirement: Machine-readable analysis export
Collection reports SHALL support JSON, CSV, and Parquet outputs in addition to a
human-readable terminal view.

#### Scenario: Same report is exported in two formats
- **WHEN** JSON and Parquet are generated with identical filters and revision
- **THEN** both contain equivalent dimensions, measures, metadata, and failures

### Requirement: Optional payload hashes
The system SHALL optionally calculate a versioned SHA-256 payload digest during
indexing or through resumable post-index analysis.

#### Scenario: Existing valid hash is available
- **WHEN** archive fingerprint and record identity match the hash provenance
- **THEN** analysis reuses the hash without rereading the payload

### Requirement: Duplicate groups
The system SHALL report records sharing the same supported content digest as a
duplicate group without deleting or rewriting source data.

#### Scenario: Same payload occurs in multiple archives
- **WHEN** equal verified digests are found for records in different sources
- **THEN** one group lists every archive ID, record ID, URL, and payload size

### Requirement: Normalized link graph
The system SHALL resolve relative links, retain original targets, normalize
absolute targets with a versioned policy, and classify internal and external
relationships.

#### Scenario: Relative link is extracted
- **WHEN** a page at `https://example.org/a/` contains `../b#part`
- **THEN** the graph stores the original target and a normalized absolute target
  according to the documented fragment policy

### Requirement: Layered integrity checks
The system SHALL provide fast metadata/workspace checks and optional deep WARC
payload verification without modifying source archives.

#### Scenario: Declared payload digest does not match
- **WHEN** deep verification computes a different supported digest
- **THEN** the report identifies the archive and record, expected and observed
  algorithms/values, and marks the check failed

### Requirement: Resumable bounded deep analysis
Payload hashing and deep integrity checks SHALL use bounded memory and resumable
batches tied to the source fingerprint and catalog revision.

#### Scenario: Deep analysis is interrupted
- **WHEN** a run stops after committed batches
- **THEN** a later resume continues from verified state without recomputing
  completed unchanged records
