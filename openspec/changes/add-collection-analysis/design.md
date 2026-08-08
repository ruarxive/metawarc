## Context

DuckDB and Parquet can aggregate record metadata efficiently once workspace
membership and typed queries are stable. Some analysis, such as payload hashes
or digest verification, requires reading WARC payloads and must remain optional
and resumable. Link data needs URL resolution and normalization before graph use.

## Goals / Non-Goals

- Goals:
  - provide fast collection-level summaries from existing metadata;
  - add optional auditable payload hashing and duplicate grouping;
  - turn raw extracted links into useful domain relationships;
  - report preservation integrity without modifying source WARCs;
  - support machine-readable, revisioned exports.
- Non-Goals:
  - delete duplicates or rewrite WARC files;
  - crawl live targets or validate current web availability;
  - build full document-text search in this change;
  - implement a web dashboard.

## Decisions

### Decision: Analysis is revision-scoped

Every report records the workspace catalog revision, filters, analysis version,
start/end time, and failure counts. A report can be reproduced against the same
revision and parameters.

### Decision: Metadata-only summaries are the default

MIME, extension, status, host/domain, date, and size summaries query registered
record sidecars without opening source payloads. Payload hashing and digest
verification require an explicit option and produce resumable derived sidecars.

### Decision: Duplicates are evidence, not automatic cleanup

Duplicate groups are based on a documented content digest and include every
archive/record reference. The system can suggest a canonical representative but
does not remove or rewrite source records.

### Decision: Link graph uses normalized absolute targets

Relative links resolve against the source record URL. Targets normalize scheme
and host case, remove fragments, and apply a documented port/path policy. Reports
aggregate edges by record and registrable host/domain where available.

### Decision: Integrity checks are layered

Fast checks validate catalog/sidecar and required WARC/header structure. Deep
checks stream payloads, compare declared lengths, and verify WARC digests when
present and supported. Unsupported algorithms are reported, not treated as a
valid match.

## Risks / Trade-offs

- Hashing large collections is I/O intensive. Mitigation: optional resumable
  batches, progress estimates, and revision/fingerprint reuse.
- Domain classification needs public-suffix data. Mitigation: make the dependency
  optional or use host-level summaries when unavailable.
- URL normalization can merge semantically distinct targets. Mitigation: retain
  original target values and version the normalization policy.
- Corrupt records can stop deep iteration. Mitigation: report the last safe
  position and preserve completed analysis batches.

## Migration Plan

1. Implement metadata-only summary dimensions and exports.
2. Add versioned hash sidecars and duplicate grouping.
3. Add normalized link targets and domain edge summaries.
4. Add fast integrity checks, then opt-in deep verification.
5. Integrate all outputs with run manifests and catalog revisions.

## Open Questions

- Is SHA-256 sufficient as the initial canonical duplicate digest?
- Which URL normalization rules must be configurable?
- Should registrable-domain support be a core or optional dependency?
- Which WARC digest algorithms are required in the first deep-check release?

