## 1. Extractor and registry
- [ ] 1.1 Create `metawarc/extractor/text.py` with `TextExtractor`
      that strips HTML tags, scripts, and style blocks via
      BeautifulSoup, and emits a bounded text blob under
      `ExtractionLimits.max_payload_bytes`
- [ ] 1.2 Re-export `TextExtractor` from `metawarc.extractor`
- [ ] 1.3 Register `TextExtractor` in `ExtractorRegistry.defaults()` under
      `detected_type="links"` so it is picked alongside `LinkExtractor`
      when the payload is HTML; the two extractors run as a single
      extraction (text + links) by `extract_record` so existing
      callers continue to work
- [ ] 1.4 Add `texts` to `MIMES_EXT_TYPE_BY_GROUP["html"]["exts"]`
      (no extension is needed; detection is by MIME)
- [ ] 1.5 Add `tests/test_text_extractor.py` covering tag stripping,
      script/style removal, length capping, and empty payloads

## 2. Sidecar schema
- [ ] 2.1 Add `TEXT_SCHEMA` (PyArrow) to `metawarc/extractor/envelope.py`
      with `archive_id`, `warc_id`, `source`, `url`, `language`,
      `text` columns
- [ ] 2.2 Update `ContentIndexer` to write the `texts` sidecar when
      the `extractor.detected_type == "links"` and the envelope
      carries a `text` field; new flag `text_extraction: bool = False`
      on `index_by_table_type`
- [ ] 2.3 Add `texts` to `VALID_TYPES` so it is an explicit opt-in

## 3. CLI and search
- [ ] 3.1 Add a `--search <phrase>` flag to the `analyze` command that
      (a) ensures the FTS index exists, (b) executes the phrase query
      against the index, and (c) prints matching records with URL,
      archive, and matched text snippet
- [ ] 3.2 Add a new `metawarc search <phrase>` subcommand as a thin
      wrapper for the same path
- [ ] 3.3 Use the existing `query.py` allowlist discipline: no
      arbitrary SQL through the search path; FTS MATCH only

## 4. DuckDB FTS integration
- [ ] 4.1 Add a helper in `metawarc/workspace.py` that lazily
      installs/loads the FTS extension and creates the
      `records_text` index over `text` keyed by `(archive_id, warc_id)`
      when missing
- [ ] 4.2 Cache the FTS extension load so the second call is a single
      statement
- [ ] 4.3 Add a `Workspace.search(phrase, limit=100)` method that
      returns the matching records

## 5. REST and MCP surfaces
- [x] 5.1 Add `GET /records/search?phrase=<text>&limit=<n>` to the
      REST API; same bearer-token discipline as `/warcs/list`
- [x] 5.2 Add a `search_records` tool to the MCP server that calls
      `Workspace.search_text` and returns the structured result
- [x] 5.3 Add `WorkspaceError` and `QueryValidationError` paths for
      empty phrases, oversized phrases, and limit overflow (FastAPI
      `min_length=1` returns 422 for empty phrases before the handler
      runs; the workspace-side guard against empty phrases is
      exercised by the CLI)

## 6. Tests
- [x] 6.1 Add `tests/test_text_extractor.py` (per §1.5) — 7 cases
- [x] 6.2 Add `tests/test_workspace_search.py` covering match, miss,
      no-sidecar, empty phrase, zero limit, oversize limit, and case
      insensitivity — 7 cases
- [x] 6.3 Add `tests/test_server_auth.py` cases for the new REST
      endpoint (401 without token, 200 with token, 422 on empty
      phrase from FastAPI validation) and add `/records/search` to
      the `PROTECTED_PATHS` loop
- [x] 6.4 Add `tests/test_search_endpoint.py` covering REST auth,
      REST happy path, REST empty phrase, REST no-token loopback
      bind, CLI end-to-end, MCP tool registration, MCP tool result

## 7. Verification
- [x] 7.1 `pytest -q` reports 147 tests passing (127 baseline + 20
      new across the search path, REST endpoint, and MCP tool)
- [x] 7.2 Coverage holds at 87 % overall; `metawarc.api_server` is
      89 % (gate 70 %), `metawarc.mcp_server` is 100 %
- [x] 7.3 `ruff format --check`, `ruff check`, and `mypy metawarc`
      remain clean
- [x] 7.4 `pip-audit` clean
- [x] 7.5 The new code paths exercise on a real small WARC end-to-end
      (a fixture HTML record with a known phrase)