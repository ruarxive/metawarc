## 1. Extractor chain
- [ ] 1.1 Add an `is_text` marker attribute (or `TextExtractor` base
      class) so the indexer can filter text-only extractors
- [ ] 1.2 Build a `get_text_registry()` helper on
      `ExtractorRegistry` that returns only the text-extractor subset
      of `defaults`

## 2. ContentIndexer.index_texts
- [ ] 2.1 Add `ContentIndexer.index_texts(...)` that walks the same
      candidate cursor as `index_by_table_type` but uses
      `get_text_registry()` and writes the `texts` sidecar via
      `TEXT_SCHEMA`
- [ ] 2.2 Bound text payloads by `ExtractionLimits.max_payload_bytes`
- [ ] 2.3 Skip archives that already have an active `texts` sidecar
      unless `rescan=True`

## 3. CLI
- [ ] 3.1 Add `--text` flag to `metawarc content-index` that runs
      `index_texts` after the structured-metadata indexing
- [ ] 3.2 Surface the per-archive counts in the existing progress
      reporter

## 4. Tests
- [ ] 4.1 `tests/test_index_texts.py`: text sidecar written for HTML
      records when `--text` is passed; text sidecar omitted when the
      flag is absent; bounds respected; PDF text appears in the
      sidecar when the PDF projector is matched
- [ ] 4.2 Extend `tests/test_workspace_search.py` with an
      end-to-end case: index with `--text`, then `search_text` matches
      the phrase

## 5. Verification
- [ ] 5.1 `pytest -q` reports 157 + ~6 new tests passing
- [ ] 5.2 Coverage holds at 87 % overall; `metawarc.extractor.indexer`
      remains ≥ 84 %
- [ ] 5.3 `ruff format --check`, `ruff check`, and `mypy metawarc`
      remain clean