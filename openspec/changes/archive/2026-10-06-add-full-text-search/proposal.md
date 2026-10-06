# Change: Add full-text search over indexed records

## Why
The catalog stores HTML response payloads in the `html` Parquet sidecar but
the resulting text is not searchable: a researcher who wants to find a
record containing a particular phrase must re-scan every WARC. DuckDB
ships an FTS extension that indexes a single text column against a primary
key column, so the workspace already has the storage substrate needed
for sub-second phrase search across an indexed collection.

The recent refactor (`refactor-extractor-and-flatten-cmds`) split the
extractor into a per-format package with a clean extension point, so
adding a `TextExtractor` is a per-format module rather than another
1 000-LOC diff to a single file. The `record-query` capability already
defines a typed query service with allowlisted fields; the search
service can be layered on top of it without re-implementing limits.

## What Changes
- Add `metawarc/extractor/text.py` with a `TextExtractor` that strips
  HTML tags, scripts, and style blocks via BeautifulSoup and emits a
  bounded text blob under the existing `ExtractionLimits` (no per-
  record byte budget explosion; uses `managed_payload_path` if needed)
- Register `TextExtractor` in the default `ExtractorRegistry` for
  `text/html`, `application/xhtml+xml`, `text/xhtml`, and `text/sgml`
  under the existing `detected_type="links"` group
- Add a new sidecar kind `texts` whose Parquet schema carries
  `archive_id`, `warc_id`, `source`, `url`, `language`, and `text`
- Add a `metawarc workspace create-fts-index` subcommand (or a
  `--build-fts` flag on `analyze`) that creates a DuckDB FTS index
  named `records_text` over `text` keyed by `warc_id`
- Add a `metawarc search` subcommand that accepts a phrase, runs the
  FTS match against the index, and prints matches with URL, archive,
  and timestamp
- Expose the same FTS index through the REST API at `GET /records/search`
  and through the MCP server as a `search_records` tool, both gated
  by the existing bearer-token discipline
- Tests: a synthetic HTML record round-trip; FTS index creation;
  search returns matches; bounds respected; auth tests cover the new
  REST endpoint

## Impact
- Affected specs: `metadata-extraction`, `record-query`, `index-workspace`
- Affected code: `metawarc/extractor/{text.py,__init__.py,indexer.py}`,
  `metawarc/query.py`, `metawarc/core.py`, `metawarc/api_server.py`,
  `metawarc/mcp_server.py`, `metawarc/constants.py` (text mime/extensions
  group), `metawarc/workspace.py` (new sidecar kind, FTS schema),
  `tests/test_*` (extraction, query, REST auth, MCP)
- Dependencies: `ship-2.0.2-and-cleanup`,
  `harden-network-binding-and-extend-test-coverage`,
  `refactor-extractor-and-flatten-cmds`

## Risk
- DuckDB's FTS extension is loadable on every supported platform but
  requires `INSTALL fts; LOAD fts;` on first use. Mitigation: the
  index-creation path caches the extension load via `SET autoinstall_known_extensions=true; SET autoload_known_extensions=true;`.
- HTML stripping can be slow on large payloads. Mitigation: text
  extraction is bounded by `extractor.text` size budget (default 1
  MiB) and runs only when the user opts in via the `search index`
  subcommand, not as part of the default indexing pipeline.
- The new REST endpoint and MCP tool expose a new query surface; the
  existing `record-query` allowlist, page size limit, and bearer-token
  discipline apply unchanged. No new input vector for SQL injection.