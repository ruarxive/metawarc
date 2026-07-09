# Changelog

## 1.3.1 (2026-07-09)

- Migrated documentation from reStructuredText to Markdown (`README.md`, `CHANGELOG.md`)
- Expanded README with workflow overview, configuration table, API curl examples, and additional CLI usage samples
- Removed legacy `AUTHORS.rst`

## 1.3.0 (2026-07-09)

- Fixed schema mismatches (`warcfile` vs `wf_id`/`wf_filename`) in dump and metadata export
- Fixed `calc_stats` empty output, CLI error messages, and indexer typos
- Added REST API and MCP server with proper HTTP errors and configurable DB path
- Consolidated CLI into a single command group; added `--dbfile` to list/dump/serve/mcp
- Added `pyproject.toml`, complete dependency list, test suite, and GitHub Actions CI
- Fixed silent-mode indexing with current warcio (record offset/length)
- Fixed ReDoc documentation page (pinned ReDoc 2.4.0, `Redoc.init()` rendering)
- Removed unused legacy modules (SQLAlchemy models, analyzer, standalone MCP stub)
- Updated documentation for `warcindex.db` and server usage

## 1.2.0 (2022-07-26)

- Completely rewritten with DuckDB and Parquet files to store metadata and pre-indexing WARC records

## 1.0.5 (2022-07-26)

- Added command headers to dump HTTP headers from WARC records and command index to index WARC records

## 1.0.4 (2022-04-11)

- Better error handling; added error messages and error flag; added zero-length file handling

## 1.0.1 (2020-05-10)

- First public release on PyPI and updated GitHub code
