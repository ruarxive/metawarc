## 1. Analysis Service
- [x] 1.1 Define supported stored metadata analysis types and deterministic `all` expansion
- [x] 1.2 Aggregate extraction status, warnings, metadata coverage, bytes, and duration by type
- [x] 1.3 Aggregate normalized field coverage and bounded top values
- [x] 1.4 Report missing sidecars and isolate malformed stored JSON

## 2. CLI and Output
- [x] 2.1 Add `analyze metadata` with repeatable `--type` and bounded `--top` options
- [x] 2.2 Reject `all` combined with explicit types and default omitted types to `all`
- [x] 2.3 Reuse archive filtering and table, JSON, CSV, and Parquet report output

## 3. Verification and Documentation
- [x] 3.1 Test single, multiple, omitted, and `all` type selection
- [x] 3.2 Test archive filtering, missing sidecars, extraction failures, warnings, and malformed JSON
- [x] 3.3 Verify equivalent report content across output formats
- [x] 3.4 Update CLI and metadata-analysis documentation with examples and `all` semantics
- [x] 3.5 Run focused tests, full test suite, lint, and type checks
