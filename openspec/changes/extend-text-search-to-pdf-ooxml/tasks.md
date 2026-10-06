## 1. PDF text projection
- [ ] 1.1 Create `metawarc/extractor/text_pdf.py` with
      `PdfTextExtractor` that probes `%PDF-` and concatenates page
      text via `pdfminer.high_level.extract_text` under
      `ExtractionLimits.max_payload_bytes`
- [ ] 1.2 Re-export `PdfTextExtractor` from `metawarc.extractor`
- [ ] 1.3 Register `PdfTextExtractor` in
      `ExtractorRegistry.defaults()` under
      `detected_type="links"` so the existing indexer picks it up
      alongside the metadata extractors

## 2. OOXML text projection
- [ ] 2.1 Create `metawarc/extractor/text_ooxml.py` with
      `OoxmlTextExtractor` that probes `PK\x03\x04`, reads
      `word/document.xml` from the OPC package, and emits the
      joined paragraph text under `ExtractionLimits.max_payload_bytes`
- [ ] 2.2 Re-export `OoxmlTextExtractor` from `metawarc.extractor`
- [ ] 2.3 Register `OoxmlTextExtractor` in the default registry

## 3. Tests
- [ ] 3.1 Add `tests/test_text_pdf.py` covering probe, text
      extraction, length capping, empty payloads
- [ ] 3.2 Add `tests/test_text_ooxml.py` covering probe, text
      extraction from `word/document.xml`, missing `word/document.xml`
- [ ] 3.3 Extend `tests/test_workspace_search.py` to round-trip a
      fixture PDF and assert that `Workspace.search_text` matches a
      phrase present in the PDF

## 4. Verification
- [ ] 4.1 `pytest -q` reports 147 + ~10 new tests passing
- [ ] 4.2 Coverage holds at 87 % overall; the new
      `metawarc.extractor.text_pdf` and
      `metawarc.extractor.text_ooxml` modules stay above 85 %
- [ ] 4.3 `ruff format --check`, `ruff check`, and `mypy metawarc`
      remain clean