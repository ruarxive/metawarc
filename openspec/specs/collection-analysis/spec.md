# collection-analysis Specification

## Purpose
TBD - created by archiving change add-collection-analysis. Update Purpose after archive.
## Requirements
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

### Requirement: Stored metadata analysis
The system SHALL analyze current registered metadata sidecars for PDF, image,
OOXML, OLE, video, audio, and font records without reading source WARC payloads.

#### Scenario: User analyzes one metadata type
- **WHEN** the user requests stored metadata analysis for one supported type
- **THEN** the report reads only current registered sidecars for that type
  within the selected archive scope

### Requirement: Stored metadata type selection
The metadata analysis command SHALL accept repeatable selections from `pdfs`,
`images`, `ooxmldocs`, `oledocs`, `videos`, `audio`, and `fonts`, and SHALL
support `all` as an exclusive shorthand for every supported stored metadata
type.

#### Scenario: User selects all types
- **WHEN** the user selects `all`
- **THEN** the system analyzes every supported current metadata sidecar type in
  deterministic order

#### Scenario: User combines all with a specific type
- **WHEN** the user combines `all` with an explicit metadata type
- **THEN** the command rejects the ambiguous selection with an actionable error

### Requirement: Extraction quality rollups
For every selected metadata type, the system SHALL report row, success, error,
warning, raw-metadata, normalized-metadata, inspected-byte, and extraction-time
measures.

#### Scenario: Stored extraction contains warnings and an error
- **WHEN** selected sidecars contain successful rows with warnings and a failed
  extraction row
- **THEN** the report includes deterministic warning-row, warning-occurrence,
  success, and error counts whose row totals reconcile

### Requirement: Normalized metadata coverage and top values
The system SHALL report coverage and bounded top-value counts for the normalized
title, creator, created, modified, and application fields.

#### Scenario: Creator values repeat
- **WHEN** multiple selected rows contain the same normalized creator
- **THEN** the creator coverage count includes those rows and the top-values list
  contains that creator with its occurrence count subject to the requested limit

### Requirement: Missing and malformed metadata isolation
The system SHALL identify selected types that have not been indexed and SHALL
isolate malformed stored JSON without aborting analysis of valid rows or other
types.

#### Scenario: A selected type has no sidecar
- **WHEN** no current registered sidecar exists for a selected metadata type
- **THEN** that type is reported as `not-indexed` with zero totals

#### Scenario: One normalized metadata value is malformed
- **WHEN** a selected sidecar contains invalid normalized JSON
- **THEN** the row remains represented in envelope rollups
- **AND** the malformed value is counted and recorded as a partial failure

### Requirement: Stored metadata analysis export
Stored metadata analysis SHALL support terminal, JSON, CSV, and Parquet output
using the common revision-scoped analysis report contract.

#### Scenario: Report is exported in multiple formats
- **WHEN** identical metadata analysis is exported as JSON and Parquet
- **THEN** both outputs contain equivalent selected types, rollups, coverage,
  top values, provenance, limits, and partial failures

