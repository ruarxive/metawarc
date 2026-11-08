# Changelog

All notable changes to this project are documented in this file.

## 2.0.4 (2026-11-08)

### Added

- Authenticated streaming downloads for completed JSON, CSV, and Parquet batch
  exports through `GET /jobs/{id}/result/content`, with safe artifact
  resolution, exact media types, attachment filenames, and `Cache-Control:
  no-store`.
- Durable per-job export progress in REST and CLI job views, with atomic
  `processed_rows`, `total_rows`, and `updated_at` snapshots plus optional
  stderr rendering in `metawarc jobs wait --progress`.
- Safe terminal-job retention through preview-by-default
  `metawarc jobs prune --retention-days N [--apply]` and opt-in
  `METAWARC_JOB_RETENTION_DAYS` automatic cleanup with bounded batches.
- Read-only retained-job operational metrics through authenticated
  `GET /jobs/metrics` and `metawarc jobs metrics`, with lifecycle counts,
  bounded newest-first selection, queue/execution durations, and explicit
  invalid-file and truncation accounting.

### Fixed

- Stream batch exports through `QueryService.iter_records` so the configured
  bulk limit is no longer truncated by the synchronous 1 000-row page limit.
- Validate export formats, limits, filter names, and filter ranges before CLI
  or REST submission persists a job.
- Use the dedicated job timeout, persist CLI cancellation immediately, and
  publish JSON, CSV, and Parquet results atomically without leaving partial
  result files after failed or cancelled exports. A running server now
  discovers standalone CLI submissions without requiring a restart.
- Claim each batch job with an OS-backed cross-process lock, recover every
  eligible pending job beyond the list page size, and mark unowned running
  jobs as `failed` with `error="interrupted"` instead of leaving them stuck
  or executing them twice.
- Make text search literal and deterministic, center snippets on matches,
  report truthful remote counts, open remote workspaces read-only, and
  distinguish a missing text sidecar from a query with no matches.
- Correct documented `get` record IDs to their normalized form without angle
  brackets and pass `--dbfile collection.db` through documented batch-job
  commands so submissions and the server use the same job store.

### Changed

- **BREAKING:** REST job list/get/result responses replace the server-local
  `result.path` with a root-relative `download_url`. Clients must follow that
  URL with the same bearer token to download the artifact. Persisted job JSON
  and local `metawarc jobs get` / `jobs wait` output retain `result.path`.
- Require `fastmcp>=3.4.10,<4` for the MCP extras and refresh the locked
  security-sensitive transitive dependencies.
- Declare Python 3.14 support after a clean installed-wheel dependency audit and
  complete test run, and add Ubuntu 3.14 to the CI matrix.
- **BREAKING:** Require Python 3.11 or newer after Python 3.10 reached EOL, and
  require `filelock>=4.2.1` and `dnspython>=2.9.0` so all supported runtimes use
  patched dependency releases. Refresh and audit the documentation npm closure,
  including patched transitive overrides and Node.js 20+.

## 2.0.3 (2026-10-06)

### Added

- `metawarc.extractor.text.TextExtractor` strips HTML, scripts, and
  style blocks via BeautifulSoup and emits a bounded plain-text blob
  under `ExtractionLimits`.
- `metawarc.extractor.text_pdf.PdfTextExtractor` and
  `metawarc.extractor.text_ooxml.OoxmlTextExtractor` project PDF and
  OOXML response bodies into the shared `texts` Parquet sidecar
  via `pdfminer.high_level.extract_text` and `lxml` over
  `word/document.xml`.
- `metawarc search <phrase> [--limit N]` CLI subcommand for
  phrase-search over the indexed `texts` sidecar.
- `Workspace.search_text(phrase, limit=50)` method backed by a Parquet
  columnar scan over the `texts` sidecar (DuckDB's FTS extension
  regressed in 1.5.x so a columnar scan is the dependable backend).
- `ContentIndexer.index_texts()` opt-in path plus the
  `metawarc content-index --text` CLI flag — populates the `texts`
  sidecar from real WARCs without requiring a manual FTS rebuild.
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
- Authenticated, durable batch-job API: `POST/GET/DELETE /jobs` on
  `metawarc serve`, `metawarc jobs submit|list|get|wait|cancel`
  CLI subcommand, and a JSON-file backed `JobRunner` started from
  FastAPI's lifespan handler. The MVP ships the `export-records`
  job kind, which materialises the result of
  `QueryService.list_records` to JSON, CSV, or Parquet. Job state
  persists across restarts; execution is bounded by
  `METAWARC_JOB_MAX_CONCURRENT` (default 4) and
  `METAWARC_JOB_TIMEOUT` (default 300s); bearer-token discipline
  is inherited from the existing `/records` and `/replay`
  endpoints.

### Changed

- Per-format `metawarc/extractor/` package split: the 1389-LOC
  `metawarc.extractor` module is reorganised as a registry of
  per-format files (`envelope`, `pdf`, `office`, `links`, `media`,
  `record`, `text`, `text_pdf`, `text_ooxml`, `indexer`,
  `registry`). The `metawarc.cmds.*` namespace is removed; the old
  import paths are kept working via `__getattr__` re-exports.
- OpenSpec roadmap aligned with shipped surface: the
  `metadata-extraction`, `record-query`, `index-workspace`, and
  `remote-interfaces` capability specs now describe the search and
  batch-job features; the deferred list drops full-text search,
  richer MCP surface, and authenticated batch-job API.

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
