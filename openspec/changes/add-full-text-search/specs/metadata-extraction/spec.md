## ADDED Requirements

### Requirement: Plain-text sidecar
The metadata-extraction service SHALL extract a script-free, tag-free text
projection of HTML responses into a `texts` Parquet sidecar when the
caller opts in.

#### Scenario: HTML indexing with text extraction enabled
- **WHEN** a user runs `metawarc content-index ... --text`
- **THEN** the workspace produces a `texts` sidecar whose rows match
  the HTML responses and carry `archive_id`, `warc_id`, `source`,
  `url`, `language`, and `text` columns

#### Scenario: HTML indexing with text extraction disabled
- **WHEN** a user runs `metawarc content-index ...` without the flag
- **THEN** no `texts` sidecar is written and the existing
  `links` sidecar is unaffected

### Requirement: Per-record text budget
The text extractor SHALL respect the existing
`ExtractionLimits.max_payload_bytes` ceiling and SHALL emit an empty
`text` field for payloads that exceed the limit rather than aborting
the archive.

#### Scenario: HTML payload exceeds the budget
- **WHEN** a single HTML response is larger than the configured
  per-record byte limit
- **THEN** the row is still written with an empty `text` field and a
  warning, and indexing continues for the remaining records