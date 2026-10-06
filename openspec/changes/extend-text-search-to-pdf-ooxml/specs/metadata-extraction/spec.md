## ADDED Requirements

### Requirement: Plain-text projection for PDF and OOXML
The metadata-extraction service SHALL project a bounded plain-text blob
for PDF and OOXML payloads, alongside the existing HTML projection,
into the shared `texts` sidecar.

#### Scenario: PDF payload with extractable content
- **WHEN** a user runs `metawarc content-index --text` over an archive
  containing a PDF record
- **THEN** the `texts` sidecar carries the concatenated page text
  truncated at `ExtractionLimits.max_payload_bytes`

#### Scenario: OOXML payload with extractable content
- **WHEN** a user runs `metawarc content-index --text` over an archive
  containing an OOXML record
- **THEN** the `texts` sidecar carries the joined paragraph text from
  `word/document.xml`, truncated at `ExtractionLimits.max_payload_bytes`

#### Scenario: PDF payload with no extractable text
- **WHEN** a PDF contains only image scans
- **THEN** the `texts` sidecar carries an empty `text` field for that
  record and indexing continues for the other records