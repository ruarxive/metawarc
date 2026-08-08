# OpenSpec Change Roadmap

This roadmap translates `REPOSITORY_REVIEW_AND_IMPROVEMENT_PLAN.md` into
independently reviewable OpenSpec changes. All entries under `changes/` are
proposals and must not be implemented until approved.

## Delivery order

1. `consolidate-release-baseline`
2. `establish-quality-gates` and `stabilize-index-workspace`
3. `harden-metadata-extraction` and `secure-query-export-interfaces`
4. `add-incremental-ingestion`
5. `add-collection-analysis`

`establish-quality-gates` can begin alongside repository consolidation, but its
packaging and migration fixtures depend on the chosen canonical baseline.
Security and extraction changes depend on the catalog/query boundaries from
`stabilize-index-workspace`. Incremental ingestion depends on stable identity,
checkpoints, and atomic workspace writes. Collection analysis depends on stable
typed queries and versioned metadata.

## Plan traceability

| Review plan area | OpenSpec change |
|---|---|
| R0.1-R0.4; packaging and release alignment | `consolidate-release-baseline` |
| R1.1-R1.4; R2.1-R2.2; R2.6 | `stabilize-index-workspace` |
| R1.5-R1.7; R3.1-R3.6 | `secure-query-export-interfaces` |
| R2.3-R2.5 | `harden-metadata-extraction` |
| Test, documentation, lint, packaging, and migration gates | `establish-quality-gates` |
| F4.1, F4.2, F4.5, F4.7 | `add-collection-analysis` |
| F4.3 and resumable ingestion portions of R1/R2 | `add-incremental-ingestion` |

## Deferred proposals

The following roadmap ideas remain deliberately unscoped until the typed query
service and versioned workspace are implemented and measured:

- optional extracted-text/full-text search;
- authenticated durable batch-job API;
- read-only web exploration interface (F4.10 catalog dashboard; distinct from
  page replay).

## Proposed next capabilities

- `add-website-replay` — local URL+timestamp page replay on the workspace
  catalog, with HTML/CSS rewriting and optional CDXJ/pywb interoperability.
  Does not replace F4.10 exploration UI.

Each deferred item requires its own future OpenSpec change rather than being
silently included in an earlier implementation.
