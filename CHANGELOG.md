# Changelog

All notable changes to this project are documented in this file.

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
