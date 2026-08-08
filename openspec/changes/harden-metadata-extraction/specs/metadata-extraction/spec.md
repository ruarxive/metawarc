## ADDED Requirements

### Requirement: Extractor registry
The system SHALL select metadata extractors through a registry whose entries
declare supported MIME values, extensions, signature probes, and schema version.

#### Scenario: New extractor is registered
- **WHEN** an extractor implements the registry contract
- **THEN** it can be selected without adding format-specific branches to the
  WARC scanning service

### Requirement: Multi-signal content detection
Extractor selection SHALL normalize MIME parameters and case and SHALL combine
declared MIME, URL extension, and bounded signature detection according to a
documented precedence.

#### Scenario: MIME includes a charset parameter
- **WHEN** a supported MIME value includes parameters and mixed case
- **THEN** it is normalized and matched to the same extractor as its base MIME

#### Scenario: MIME and extension conflict
- **WHEN** MIME and extension indicate different supported formats
- **THEN** the documented precedence selects an extractor and the result records
  a mismatch warning

### Requirement: Versioned metadata envelope
Every extraction attempt SHALL return a versioned envelope containing
provenance, detected type, extractor identity, normalized metadata, raw metadata,
warnings, stable error state, bytes inspected, and duration.

#### Scenario: Parser returns no metadata
- **WHEN** a parser recognizes a format but finds no metadata
- **THEN** the envelope distinguishes an empty result from parser failure

### Requirement: Extraction resource limits
The extraction service SHALL enforce configured limits for payload bytes,
duration, temporary storage, and format-specific expansion before committing a
result.

#### Scenario: Payload exceeds byte limit
- **WHEN** a selected payload is larger than the configured extractor limit
- **THEN** parsing is skipped and the envelope records a stable limit-exceeded
  error without reading the complete payload

### Requirement: Safe archive and XML parsing
Container and XML extractors SHALL reject unsafe member paths, excessive member
counts or expansion, external entities, and network resolution.

#### Scenario: OOXML archive has excessive expansion
- **WHEN** declared or observed expanded content exceeds the configured limit
- **THEN** extraction stops before full expansion and records a container-limit
  error

### Requirement: Temporary resource cleanup
Temporary files and directories SHALL be removed after every extraction attempt
unless explicit debug retention is enabled.

#### Scenario: Parser raises an exception
- **WHEN** a path-based parser fails after a temporary file is created
- **THEN** the temporary file is removed before the error result is returned

### Requirement: Per-record failure isolation
An extraction failure SHALL NOT abort processing of unrelated records in the
same WARC when the archive reader can continue safely.

#### Scenario: Corrupt document is followed by a valid image
- **WHEN** document extraction fails and the next record is readable
- **THEN** the failure is recorded and image extraction still runs

### Requirement: Bounded metadata persistence
Extraction envelopes SHALL be written in bounded batches using stable base
columns and versioned handling for variable raw metadata.

#### Scenario: Archive contains many supported documents
- **WHEN** extraction spans multiple configured batches
- **THEN** completed batches are released and peak buffered result count remains
  within the documented bound
