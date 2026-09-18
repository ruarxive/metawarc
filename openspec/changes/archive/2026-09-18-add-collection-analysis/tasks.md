## 1. Analysis Framework
- [x] 1.1 Define revision-scoped analysis run and report metadata
- [x] 1.2 Implement typed collection filters and deterministic dimensions
- [x] 1.3 Add terminal, JSON, CSV, and Parquet report writers
- [x] 1.4 Record partial failures and applied limits in every report

## 2. Collection Summary
- [x] 2.1 Aggregate count and bytes by MIME and extension
- [x] 2.2 Aggregate by status, host/domain, record date, and size bucket
- [x] 2.3 Add top-N controls and complete machine-readable output
- [x] 2.4 Test null, malformed, and high-cardinality dimensions

## 3. Hashes and Duplicates
- [x] 3.1 Define versioned payload-hash sidecar schema
- [x] 3.2 Add optional SHA-256 during indexing and resumable post-index hashing
- [x] 3.3 Reuse hashes only when archive fingerprint and record identity match
- [x] 3.4 Report duplicate groups and canonical-candidate metadata
- [x] 3.5 Verify hashing never mutates or removes source records

## 4. Link Graph
- [x] 4.1 Resolve relative targets against source record URLs
- [x] 4.2 Implement versioned URL normalization retaining original values
- [x] 4.3 Classify internal/external links by host and optional registrable domain
- [x] 4.4 Aggregate record, host, and domain edge summaries
- [x] 4.5 Test invalid URLs, base tags, fragments, ports, and internationalized hosts

## 5. Integrity Reporting
- [x] 5.1 Add catalog, sidecar, and source-availability fast checks
- [x] 5.2 Validate WARC framing, required headers, and declared lengths
- [x] 5.3 Add opt-in payload digest verification for supported algorithms
- [x] 5.4 Report unsupported algorithms, corrupt records, and last safe positions
- [x] 5.5 Make deep checks resumable with bounded memory

## 6. Verification
- [x] 6.1 Verify reports identify their catalog revision and analysis version
- [x] 6.2 Verify all output formats contain equivalent result data
- [x] 6.3 Test partial source availability and corrupt sidecars
- [x] 6.4 Add performance baselines for summary, hashing, links, and deep integrity

