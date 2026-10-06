# Change: Extend text projection to PDF and OOXML payloads

## Why
The `add-full-text-search` change shipped HTML-only text projection through
`TextExtractor` and the `metawarc search` CLI. PDF and OOXML payloads are
also part of the indexed collection but currently produce no text blob,
so `metawarc search` cannot match phrases buried in PDF reports or Word
documents.

The PDF and OOXML extractors already exist for metadata extraction
(`metawarc/extractor/pdf.py`, `metawarc/extractor/office.py`). The text
projection is a sibling concern: read text, don't parse metadata. The
PDF side uses pdfminer's high-level page-text API; the OOXML side reads
`word/document.xml` from the OPC package and concatenates paragraph
text. Both reuse the `ExtractionLimits` budget and the `Managed_payload_path`
helper.

## What Changes
- New `metawarc/extractor/text_pdf.py` with a `PdfTextExtractor`
  that probes `%PDF-` and emits the concatenated page text under
  `ExtractionLimits.max_payload_bytes`
- New `metawarc/extractor/text_ooxml.py` with an `OoxmlTextExtractor`
  that probes `PK\x03\x04` and emits the joined paragraph text from
  `word/document.xml`
- Both are re-exported from `metawarc.extractor` and registered in
  the default `ExtractorRegistry` under `detected_type="links"`
  (mirroring `TextExtractor`), so the existing indexer picks them up
  alongside the metadata extractors
- The shared `Workspace.search_text` path is unchanged: it reads the
  `texts` sidecar; the new payloads simply populate it through the
  indexer
- New CLI flag `--text` on `metawarc content-index` that, in addition
  to its current behaviour, also calls `TextExtractor` / `PdfTextExtractor`
  / `OoxmlTextExtractor` and writes the `texts` sidecar
- Tests: format-specific extraction (token stripping, length capping,
  empty payload), registry picks the right extractor per MIME,
  end-to-end `metawarc search` round-trip on a fixture PDF

## Impact
- Affected specs: `metadata-extraction`, `record-query`
- Affected code: `metawarc/extractor/{__init__,text_pdf,text_ooxml}.py`,
  `metawarc/extractor/registry.py`, `metawarc/extractor/indexer.py`
  (or a new `index_texts` method), `metawarc/core.py`,
  `tests/test_text_extractor.py` (extended) and
  `tests/test_workspace_search.py` (extended)
- Dependencies: `add-full-text-search`

## Risk
- pdfminer and lxml are already required dependencies for the
  metadata extractors; no new dependency is added.
- PDFs with no extractable text (image-only scans) emit an empty
  `text` field rather than aborting; the same holds for OOXML
  documents that lack `word/document.xml`.
- The change does not enable text extraction by default; the
  `metawarc content-index` command only runs it when the new
  `--text` flag is passed (default behaviour preserved).