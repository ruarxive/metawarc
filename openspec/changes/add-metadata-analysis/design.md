## Context

Document and image metadata sidecars share a stable envelope schema. Raw and
normalized parser values are JSON strings, while extraction status, warnings,
bytes inspected, and duration are fixed columns. Link sidecars have a different
schema and already feed the link-graph analysis.

## Goals / Non-Goals

- Goals:
  - analyze selected stored metadata without reopening WARC payloads;
  - expose extraction quality and normalized metadata coverage;
  - make `all` a convenient deterministic selection;
  - retain the existing revision-scoped report and export contract.
- Non-Goals:
  - rescan payloads or repair failed extraction rows;
  - infer type-specific fields from arbitrary raw parser output;
  - combine link analysis with document/image metadata analysis;
  - change metadata sidecar schemas.

## Decisions

### Decision: Analyze the four shared-envelope metadata types

The command accepts `pdfs`, `images`, `ooxmldocs`, and `oledocs`. `all` expands
to those four types in that deterministic order and cannot be combined with an
explicit type. Links remain under `analyze links` because they do not use the
metadata envelope schema.

### Decision: Use fixed rollups and normalized fields

Each selected type reports total rows, successful and failed rows, rows and
occurrences with warnings, rows containing raw and normalized metadata, bytes
inspected, and extraction duration. Field coverage and top-value counts are
computed for the normalized `title`, `creator`, `created`, `modified`, and
`application` fields. A bounded `--top` option limits values returned for each
field.

### Decision: Missing and malformed stored data remains observable

A selected type with no current registered sidecars is returned with an
explicit `not-indexed` status and zero totals. Invalid JSON in an individual row
is counted and recorded as a partial failure without preventing analysis of
other rows or types.

### Decision: Query registered sidecars only

Analysis resolves current sidecars through the workspace catalog and applies
archive IDs before reading Parquet. It never scans the data directory directly,
so retired, staged, and orphan sidecars cannot affect results.

## Risks / Trade-offs

- High-cardinality normalized values can be expensive to group. Mitigation:
  aggregate in DuckDB and apply a bounded top-N result per field.
- Malformed legacy JSON may prevent field extraction. Mitigation: retain envelope
  rollups, count malformed values, and expose partial failures.
- Terminal and flat formats cannot represent nested data directly. Mitigation:
  reuse the existing report writer's deterministic JSON encoding for nested
  fields.

## Migration Plan

1. Add metadata-sidecar aggregation to the analysis service.
2. Add the CLI command, type validation, and `all` expansion.
3. Add service, CLI, malformed-data, and export-equivalence tests.
4. Document supported types, `all` semantics, and examples.

