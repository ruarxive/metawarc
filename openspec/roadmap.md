# OpenSpec Change Roadmap

All changes from the 2026-08-04 repository review were implemented with the
2.0 release and archived on 2026-09-18. The archived changes now live under
`changes/archive/2026-09-18-*` and their requirements are merged into
`specs/`, which is the current source of truth for the shipped 2.x surface.

See `PRODUCT_REVIEW_AND_IMPROVEMENT_PLAN.md` (2026-11-05) for the active
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
| `remote-interfaces` | `secure-query-export-interfaces`, `add-website-replay`, `add-full-text-search`, `extend-text-search-to-pdf-ooxml`, `add-index-texts`, `enrich-mcp-readonly-surface`, `add-batch-job-api` |
| `remote-batch-job` | `add-batch-job-api` |
| `cli-progress` | `add-cli-progress-reporting` |
| `build-system` / `release-engineering` / `test-assurance` / `documentation-quality` | `consolidate-release-baseline`, `establish-quality-gates` |

## Deferred proposals

The following are deliberately not approved or scaffolded yet (see the
2026-11-05 review, Phase 3, for ordering; Phases 0–2 are stabilization
prerequisites):

1. Filtered, reproducible text search — shared filters, pagination, documented
   ordering, freshness semantics, and representative performance benchmarks.
2. Collection exploration dashboard — read-only web UI over the catalog
   (hosts, MIME stats, timelines, and search), distinct from page replay.
3. Additional payload-export or analysis job kinds after the runner and
   observability contracts are accepted.

Batch retention, durable progress, result downloads, and retained-job
operational metrics are implemented. The metrics change lives in
`changes/add-job-operational-metrics/` until deployment and archival. Every
remaining deferred item requires its own future OpenSpec change rather than
being silently included in an earlier implementation.
