## Context
The 2026-10-06 refactor (`refactor-extractor-and-flatten-cmds`) shipped
`metawarc/extractor/` as a per-format package so a new format family
lands in its own module. The next obvious gap is searchable text: the
HTML Parquet sidecar stores the raw response payload but a researcher
cannot query for a phrase without re-scanning every WARC.

DuckDB ships an FTS extension that maintains an inverted index over a
single text column against a primary key. The workspace already uses
DuckDB for the catalog and the sidecars, so the storage substrate is
already loaded — the work is (a) write a text-stripping extractor,
(b) define a new `texts` sidecar schema, (c) maintain an FTS index
over the `text` column, and (d) expose the index through the existing
remote interfaces.

## Goals / Non-Goals

- Goals:
  - extract plain text from HTML responses into a dedicated `texts`
    sidecar;
  - maintain a DuckDB FTS index over the sidecar;
  - expose phrase search through a new `metawarc search` CLI
    subcommand and an opt-in flag on `analyze`;
  - expose the same index through the REST API and MCP server under
    the existing bearer-token discipline;
  - keep the opt-in surface small: the default indexing pipeline is
    unchanged; text extraction is gated behind an explicit flag so
    users who only want structured metadata pay nothing.

- Non-Goals:
  - full-text search over non-HTML response payloads (PDFs, OOXML,
    text/plain) in this change; the architecture allows it, but the
    extractor additions for those families are tracked as follow-ups
    so this change stays bounded;
  - a server-side `web/search` endpoint or read-model; the existing
    `remote-interfaces` capability already covers endpoint surface
    rules;
  - query rewriting or relevance tuning beyond DuckDB FTS defaults;
  - changes to the `record-query` allowlist or the REST/MCP
    allowlists (those are owned by `record-query` and
    `remote-interfaces` and stay untouched).

## Decisions

### Decision: separate `TextExtractor`, same `detected_type="links"`

`LinkExtractor` returns anchor metadata. `TextExtractor` returns plain
text. Both target the same MIME set (HTML/XHTML/SGML). Registering both
under `detected_type="links"` means the indexer's existing
`extractor.detected_type == "links"` match picks them up; the envelope
gets an extra `text` field when the registry's HTML matcher runs
`TextExtractor` after `LinkExtractor`.

The alternative — a single extractor that returns both anchors and
text — couples the two concerns. Two small classes with one shared
helper for HTML parsing is the cleaner split.

### Decision: opt-in via a flag, not a default

`metadata-extraction` already ships 53 functions across 9 modules.
Adding text stripping to the default indexing pipeline would slow every
run for users who don't search. A `text_extraction=False` default on
`ContentIndexer.index_by_table_type` keeps the existing behavior;
users run `metawarc content-index ... --text` (or pass
`text_extraction=True` programmatically) when they want search support.

### Decision: FTS via DuckDB, not an external engine

DuckDB's FTS extension is single-binary, runs in-process, and uses the
existing workspace connection. Spinning up Elasticsearch or Meilisearch
would add an operational dependency for a feature that fits in
DuckDB's existing footprint.

### Decision: REST `GET /records/search` with `phrase` and `limit`

Phrase is a required query parameter; limit defaults to 50 and is
capped at the existing `ServerSettings.max_page` (500). The endpoint
reuses the existing bearer-token middleware, the existing
`query.py` allowlist, and the existing pagination shape. No new
input surface.

### Decision: MCP `search_records` tool

The current MCP server exposes a small set of read-only tools (catalog
listing, replay URL). Adding `search_records` keeps the MCP surface
read-only and matches the existing tool signatures (typed input schema,
typed output, deterministic pagination). The tool reuses
`Workspace.search` directly.

## Risks / Trade-offs

- HTML stripping can be slow on large payloads. Mitigation: the
  extractor is bounded by `ExtractionLimits.max_payload_bytes`
  (default 64 MiB) and runs only when the user opts in via the
  `text_extraction=True` flag.
- DuckDB FTS is a best-effort match; relevance ranking is its
  default. Mitigation: future work can swap in BM25; this change
  ships the surface, not the relevance tuning.
- The new REST endpoint exposes a new query vector. Mitigation:
  every input passes through `query.py`'s allowlist and the existing
  bearer-token middleware; no raw SQL is reachable from the search
  path.

## Migration Plan

1. Land this Change as a single PR on `master`.
2. Verify CI on all four runners (Ubuntu 3.10/3.13, macOS 3.13,
   Windows 3.13) including the new per-module coverage floors.
3. Ship as `metaxar` 2.1.0 with the new subcommand documented in the
   docs site.
4. Mark the broader roadmap item "Full-text search" as done in
   `openspec/roadmap.md` once 2.1.0 is published.

## Open Questions

- Should `text_extraction` be a separate subcommand
  (`metawarc extract-text`) rather than a flag on `content-index`?
  Recommendation: flag first (lower surface); split into a separate
  subcommand if the flag becomes a bottleneck.
- Should the FTS index be per-workspace or per-catalog-revision?
  Recommendation: per-catalog-revision, so a re-index creates a new
  index in the same DuckDB file and the old index is dropped.
- Should the `language` column be auto-detected (via `langdetect`)
  or left null? Recommendation: leave null in this change; track
  language detection as a follow-up.