# Project Context

## Purpose
`metawarc` is a command-line tool for indexing, querying, analyzing, and
extracting metadata and payloads from WARC web archives. It keeps source
payloads in their original WARC files, stores an operational catalog in
DuckDB, and writes record, header, link, and document metadata to Parquet
sidecars. A newer candidate implementation also exposes read-only REST and MCP
interfaces.

## Tech Stack
- Python package and Click CLI
- `warcio` and candidate `fastwarc` support for WARC processing
- DuckDB catalog with PyArrow/Parquet sidecars
- Hachoir, pdfminer.six, lxml, and Beautiful Soup metadata extraction
- Rich and tqdm terminal output
- Candidate FastAPI, Uvicorn, structlog, and FastMCP interfaces
- pytest for tests; Ruff is the preferred consolidated lint/format tool

## Project Conventions

### Code Style
- Python code uses four-space indentation, LF endings, and UTF-8.
- New public functions and service boundaries require type annotations.
- Prefer small, single-responsibility modules and context managers for every
  file, database, parser, archive, and temporary resource.
- Use one formatter/linter configuration over the entire tracked Python tree.
- CLI messages are concise and actionable; machine-readable output goes to
  stdout and diagnostics go to stderr.

### Architecture Patterns
- Source WARC files remain the authoritative payload store.
- DuckDB is the catalog and query engine; Parquet files hold scalable metadata.
- An index workspace owns a database and its sidecars; code must not assume the
  caller's current working directory.
- Core indexing, catalog, query, extraction, and export services are independent
  of Click, FastAPI, and MCP adapters.
- Query values are parameterized and query fields/operators are allowlisted.
- Large collections are processed with bounded batches and atomic output files.

### Testing Strategy
- Use pytest with generated real `.warc` and `.warc.gz` fixtures.
- Cover unit, integration, CLI, API/MCP security, packaging, migration, and
  bounded-memory performance behavior.
- Critical end-to-end workflows are required regardless of aggregate coverage.
- Every documented CLI example is tested directly or by an equivalent scenario.
- CI validates the minimum supported Python version and the latest supported
  version, builds wheel/sdist artifacts, and installs them in clean environments.

### Git Workflow
- `master` is currently the default branch; `testing` contains the `v1.3.1`
  candidate and must be consolidated through a reviewed integration change.
- OpenSpec changes are proposals only until explicitly approved.
- Implement one approved change at a time where dependencies require ordering.
- Release tags, version metadata, changelog, documentation, and artifacts must
  originate from the same commit.

## Domain Context
- WARC collections can be very large and can contain malformed or hostile HTTP
  headers, identifiers, URLs, compressed documents, XML, and payloads.
- Record offsets allow payload extraction without duplicating payload storage,
  but offset semantics must work for both compressed and uncompressed archives.
- Archive filenames are not unique collection identifiers; duplicate basenames
  in different directories are valid.
- MIME headers, URL extensions, and payload signatures can disagree.
- Preservation users require reproducible manifests, integrity information,
  clear error accounting, and non-destructive update behavior.

## Important Constraints
- Indexing memory use must remain bounded as record count grows.
- Interrupted writes must not register incomplete sidecars as complete.
- Existing 1.2 and 1.3 indexes need an explicit migrate, rebuild, or reject path.
- Public API/MCP interfaces must not expose arbitrary DuckDB SQL or unrestricted
  local file access.
- Exported filenames must not traverse directories or silently overwrite data.
- The core CLI must remain usable without installing API or MCP dependencies.

## External Dependencies
- Local WARC/WARC.GZ files and optional CDX files
- Local filesystem for the DuckDB catalog, Parquet sidecars, and exports
- No external network service is required for core indexing and querying
- Optional REST and MCP servers are local by default and require explicit secure
  configuration before non-loopback exposure
