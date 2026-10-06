# Change: Index the `texts` sidecar end-to-end

## Why
The `add-full-text-search` and `extend-text-search-to-pdf-ooxml` changes
shipped the search pipeline (extractors, `Workspace.search_text`, the
`metawarc search` CLI, the REST `/records/search` endpoint, the MCP
`search_records` tool), but the `texts` sidecar is only ever populated
by test fixtures. A user who runs the existing `metawarc content-index`
command cannot get text projection because the indexer only writes
structured-metadata sidecars.

Closing the loop: the indexer needs a new `index_texts` path that
runs the text extractor chain (`TextExtractor`, `PdfTextExtractor`,
`OoxmlTextExtractor`) and writes a `texts` sidecar using the existing
`TEXT_SCHEMA`. The workspace catalog already supports the `texts`
sidecar kind, so no schema migration is needed.

## What Changes
- New `ContentIndexer.index_texts(...)` method that walks the same
  candidate stream as `index_by_table_type` but writes to the `texts`
  sidecar via the text-extractor chain
- New `--text` flag on `metawarc content-index` that, when set, also
  runs `index_texts` after the structured-metadata index
- The text extractor chain selects `TextExtractor` for HTML, `PdfTextExtractor`
  for PDF, `OoxmlTextExtractor` for OOXML; payloads that hit no
  text extractor emit an empty `text` row with a warning
- Workspace already supports `texts` sidecars; no schema or `publish_sidecar`
  changes are required
- Tests: text sidecar written for HTML records; PDF records; OOXML
  records; bounds respected; existing metadata-index call unchanged
  when `--text` is omitted

## Impact
- Affected specs: `metadata-extraction`, `index-workspace`
- Affected code: `metawarc/extractor/indexer.py`,
  `metawarc/core.py`, `metawarc/extractor/registry.py` (default text
  chain exposure), `tests/test_extraction_analysis.py`,
  `tests/test_workspace_search.py` (extended end-to-end)
- Dependencies: `add-full-text-search`, `extend-text-search-to-pdf-ooxml`

## Risk
- The text extractor chain currently shares the same
  `ExtractorRegistry` as the metadata extractors. To avoid running
  the metadata extractors during text indexing, the indexer uses a
  filtered view that selects only extractors whose class is a subclass
  of `TextExtractor` (or a small `is_text` marker interface).
- The default `ExtractionLimits` apply; text payloads larger than
  `max_payload_bytes` are emitted with `truncated=true` rather than
  aborting the archive.
- The `--text` flag is opt-in; default indexing behaviour is preserved.