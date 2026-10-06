# Changelog

All notable changes to this project are documented in this file.

## Unreleased

### Added

- `metawarc.extractor.text.TextExtractor` strips HTML, scripts, and
  style blocks via BeautifulSoup and emits a bounded plain-text blob
  under `ExtractionLimits`.
- `metawarc search <phrase> [--limit N]` CLI subcommand for
  phrase-search over the indexed `texts` sidecar.
- `Workspace.search_text(phrase, limit=50)` method backed by a Parquet
  columnar scan over the `texts` sidecar (DuckDB's FTS extension
  regressed in 1.5.x so a columnar scan is the dependable backend).
- `GET /records/search?phrase=<text>&limit=<n>` REST endpoint with the
  same bearer-token discipline as `/warcs/list`.
- `search_records` MCP tool that calls `Workspace.search_text` and
  returns the structured result.
- `TEXT_SCHEMA` (archive_id, warc_id, source, url, language, text)
  for the new `texts` sidecar kind.
- `collection_stats(archive_ids, dimensions, top)` and
  `metadata_summary(metadata_types, archive_ids, top)` MCP tools
  that wrap `AnalysisService.summary()` and
  `AnalysisService.stored_metadata()` over the existing allowlist
  and pagination discipline.

## 2.0.2 (2026-10-06)

### Fixed

- Declare `pytz` as a core dependency so DuckDB can compare timezone-aware
  record timestamps on a fresh install.
- Align `requirements.txt` with the authoritative `pyproject.toml` dependency
  set (adds `pytz` and `fonttools[woff]`).
- Clear 17 transitive vulnerabilities in the dev closure:
  - `pyjwt` 2.13.0 → 2.15.1 (14 CVEs)
  - `urllib3` 2.7.0 → 2.8.0 (3 CVEs)
- Tighten `metawarc.settings.is_loopback` to use
  `ipaddress.ip_address(...).is_loopback` so every canonical IPv4 and
  IPv6 loopback representation (including the IPv6 long form
  `0:0:0:0:0:0:0:1`) is recognised before deciding whether the configured
  bind requires authentication.

### Changed

- Remove dead `metawarc.base` and `metawarc.data` packages from the source
  tree; they were already excluded from built distributions.
- Pin the `httpx2` development dependency to `>=2.12`; previously resolved
  2.9.1 carried six known CVEs (PYSEC-2026-3844 through PYSEC-2026-3849).
- Modernize GitHub Actions (v7), support Python 3.10–3.13 CI matrix, add a
  macOS test runner, and add a `windows-latest` Python 3.13 matrix entry.
- Add `pip-audit` to the `test` job so the contributor-path closure is
  audited in the same job that exercises the tests.
- Add a per-module coverage gate of 70 % for every public surface
  (`metawarc.indexer`, `metawarc.api_server`, `metawarc.dump`,
  `metawarc.mcp_server`); the indexer gate previously applied only to a
  subset of the test suite.
- Publish the Docusaurus documentation site and retarget repository URLs
  after the move to the `ruarxive` organization.
- Archive all completed OpenSpec changes; `openspec/specs/` now holds the
  shipped 2.x capability requirements with a non-placeholder Purpose
  paragraph for every spec.
- Add `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) and `SUPPORT.md`;
  link them from the README and the docs site.
- Flatten the `metawarc.cmds/` package to the package top level; every
  command module (`dump`, `indexer`, `api_server`, `extractor`) now
  lives at the top level alongside `analysis`, `replay`, `mcp_server`,
  and `ingestion`.
- Extract `metawarc.reporting.py` (95 LOC) as the dedicated presentation
  module so command-group wiring in `core.py` no longer mixes Rich-table
  and JSON rendering into the control flow.
- Move `logging.basicConfig` from `metawarc.core.cli()` to
  `metawarc.__main__` so library consumers retain control of their
  logger configuration.
- Split the 1 389-LOC `metawarc/extractor.py` into a per-format package
  (`metawarc/extractor/{__init__,envelope,pdf,office,links,media,
  registry,record,indexer}.py`); backward-compatible re-exports
  preserve the public API and the `metawarc.extractor.PDFDocument`
  symbol.

### Added

- 23 cases in `tests/test_settings.py` covering the loopback helper.
- 13 cases in `tests/test_server_auth.py` for the bearer-token surface
  (loopback vs non-loopback bind, malformed `Authorization` headers,
  replay-route coverage).
- 4 cases in `tests/test_module_entry.py` for the
  `python -m metawarc --version` / `--help` smoke.

## 2.0.1 (2026-08-08)

### Fixed

- Declare `beautifulsoup4` as a core dependency so `metawarc` imports cleanly
  from a fresh PyPI install.

## 2.0.0 (2026-08-08)

### Added

- Versioned DuckDB/Parquet workspace with stable archive identities, bounded
  atomic indexing, checkpoints, incremental ingestion, and diagnostics.
- Typed query/export services shared by the CLI, REST API, and MCP.
- Hardened metadata extraction and revision-scoped collection analysis.
- Stored PDF, image, OOXML, and OLE metadata analysis with extraction quality,
  normalized-field coverage, and top-value reports.
- Expanded media metadata extraction for common video, audio, and font formats.
- CLI progress reporting for long-running index, ingest, extract, dump, and
  analysis workflows.
- Website replay on `metawarc serve` / `metawarc replay`:
  - Home page at `/` listing archived hosts with navigation into replay.
  - `/replay/<stamp>/<url>` closest-timestamp capture serving with HTML/CSS
    rewriting, redirect remapping, and Memento headers.
  - `id_` identity mode and `mp_` rewritten mode.
  - Charset-aware rewriting (UTF-8, windows-1251, KOI8-R, and related) so
    Cyrillic and other non-ASCII pages render correctly.
  - `metawarc export-cdxj` for CDXJ (+ optional path index) pywb interop.
  - Optional `metawarc[replay]` extra (same dependencies as `api`).

### Fixed

- PDF metadata decoding for UTF-16BE and PDFDocEncoding text strings.

### Changed

- Consolidated package metadata in `pyproject.toml` and established CI gates.

## 1.2.0 (2022-07-26)

- Completely rewritten with DuckDB and Parquet files to store metadata and
  pre-index WARC records.

## 1.0.5 (2022-07-26)

- Added command headers to dump HTTP headers from WARC records and command
  index to index WARC records.

## 1.0.4 (2022-04-11)

- Better error handling, error messages, and error flag.
- Added zero-length file handling.

## 1.0.1 (2020-05-10)

- First public release on PyPI and updated GitHub code.
