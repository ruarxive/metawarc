## ADDED Requirements

### Requirement: Stored metadata analysis
The system SHALL analyze current registered metadata sidecars for PDF, image,
OOXML, and OLE records without reading source WARC payloads.

#### Scenario: User analyzes one metadata type
- **WHEN** the user selects `pdfs`
- **THEN** the report reads only current registered PDF metadata sidecars within
  the selected archive scope
- **AND** it identifies the analyzed catalog revision and applied filters

### Requirement: Stored metadata type selection
The metadata analysis command SHALL accept repeatable selections from `pdfs`,
`images`, `ooxmldocs`, and `oledocs`, and SHALL support `all` as an exclusive
shorthand for all four types.

#### Scenario: User selects all types
- **WHEN** the user supplies `--type all` or omits `--type`
- **THEN** the system analyzes `pdfs`, `images`, `ooxmldocs`, and `oledocs` in a
  deterministic order

#### Scenario: User combines all with a specific type
- **WHEN** the user supplies `--type all --type pdfs`
- **THEN** the command rejects the ambiguous selection with an actionable usage
  error

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

