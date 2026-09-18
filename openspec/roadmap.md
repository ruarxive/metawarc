# OpenSpec Change Roadmap

All changes from the 2026-08-04 repository review were implemented with the
2.0 release and archived on 2026-09-18. The archived changes now live under
`changes/archive/2026-09-18-*` and their requirements are merged into
`specs/`, which is the current source of truth for the shipped 2.x surface.

See `PRODUCT_REVIEW_AND_IMPROVEMENT_PLAN.md` (2026-09-17) for the active
improvement plan and full traceability.

## Shipped capabilities (specs)

| Capability | Delivered by |
|---|---|
| `archive-indexing` | `stabilize-index-workspace`, `add-incremental-ingestion` |
| `index-workspace` | `stabilize-index-workspace` |
| `record-query` | `secure-query-export-interfaces` |
| `payload-export` | `secure-query-export-interfaces` |
| `metadata-extraction` | `harden-metadata-extraction`, `expand-media-format-extraction` |
| `collection-analysis` | `add-collection-analysis`, `add-metadata-analysis` |
| `website-replay` | `add-website-replay` |
| `remote-interfaces` | `secure-query-export-interfaces`, `add-website-replay` |
| `cli-progress` | `add-cli-progress-reporting` |
| `build-system` / `release-engineering` / `test-assurance` / `documentation-quality` | `consolidate-release-baseline`, `establish-quality-gates` |

## Deferred proposals

The following remain deliberately unscoped until they are picked up as their
own change proposals (see the 2026-09-17 review, Phase 2, for ordering):

1. Collection exploration dashboard — read-only web UI over the catalog
   (hosts, MIME stats, timelines), distinct from page replay.
2. Full-text search — searchable index of extracted text (PDF/HTML).
3. Richer read-only MCP surface — collection stats and analysis summary tools,
   preserving the no-SQL/no-path/no-mutation contract.
4. Authenticated durable batch-job API — async export/analysis jobs for large
   collections.

Each deferred item requires its own future OpenSpec change rather than being
silently included in an earlier implementation.
