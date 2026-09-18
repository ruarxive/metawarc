# Changelog

All notable changes to this project are documented in this file.

## 2.0.2 (2026-09-18)

### Fixed

- Declare `pytz` as a core dependency so DuckDB can compare timezone-aware
  record timestamps on a fresh install.
- Align `requirements.txt` with the authoritative `pyproject.toml` dependency
  set (adds `pytz` and `fonttools[woff]`).

### Changed

- Remove dead `metawarc.base` and `metawarc.data` packages from the source
  tree; they were already excluded from built distributions.
- Pin the `httpx2` development dependency to `>=2.12`; previously resolved
  2.9.1 carried six known CVEs (PYSEC-2026-3844 through PYSEC-2026-3849).
  `pip-audit` is clean again.
- Modernize GitHub Actions (v7), support Python 3.10–3.13 CI matrix, and add
  a macOS test runner.
- Publish the Docusaurus documentation site and retarget repository URLs
  after the move to the `ruarxive` organization.
- Archive all completed OpenSpec changes; `openspec/specs/` now holds the
  shipped 2.x capability requirements.

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
