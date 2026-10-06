## ADDED Requirements

### Requirement: Text sidecar population
The metadata-extraction service SHALL populate the `texts` sidecar when
the caller opts in via the `metawarc content-index --text` flag, by
running the text-extractor chain (`TextExtractor`, `PdfTextExtractor`,
`OoxmlTextExtractor`) and writing one row per record.

#### Scenario: HTML archive indexed with `--text`
- **WHEN** a user runs `metawarc content-index --text sample.warc`
- **THEN** the workspace produces a `texts` sidecar whose rows carry
  `archive_id`, `warc_id`, `source`, `url`, `language`, and `text`
  for every HTML response record

#### Scenario: PDF archive indexed with `--text`
- **WHEN** a user runs `metawarc content-index --text` over an archive
  containing a PDF record
- **THEN** the `texts` sidecar carries the concatenated page text for
  that record

#### Scenario: Default indexing without `--text`
- **WHEN** a user runs `metawarc content-index` without the flag
- **THEN** no `texts` sidecar is written; existing structured-metadata
  sidecars are unchanged