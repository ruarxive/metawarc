## 1. Shared Query Service
- [x] 1.1 Define typed query, sort, pagination, and result models
- [x] 1.2 Implement allowlisted field/operator compilation and parameter binding
- [x] 1.3 Resolve archive membership and sidecar paths through the catalog
- [x] 1.4 Add deterministic ordering and page/record/time limits
- [x] 1.5 Route stats, list, dump, get, API, and MCP reads through the service
- [x] 1.6 Add explicit trusted local SQL option outside network adapters

## 2. Safe Export
- [x] 2.1 Implement filename sanitization for hostile record IDs and URLs
- [x] 2.2 Implement deterministic collision handling without silent overwrite
- [x] 2.3 Stream selected records grouped by source archive
- [x] 2.4 Enforce selected-record and total-byte limits
- [x] 2.5 Write a manifest mapping each result to source metadata and checksum
- [x] 2.6 Close source/output handles on success, error, interrupt, and cancellation

## 3. REST API
- [x] 3.1 Replace raw query parameter with typed filters
- [x] 3.2 Define response and error models for every endpoint
- [x] 3.3 Default bind address to `127.0.0.1`
- [x] 3.4 Add authentication configuration for non-loopback deployments
- [x] 3.5 Add request page, byte, duration, and concurrency limits
- [x] 3.6 Make payload streaming cancellation-safe

## 4. MCP
- [x] 4.1 Define a minimal allowlisted read-only tool inventory
- [x] 4.2 Implement tools over the shared query service
- [x] 4.3 Exclude arbitrary SQL, arbitrary file paths, and mutation operations
- [x] 4.4 Document authentication and transport exposure

## 5. Verification
- [x] 5.1 Test quote, comment, statement, path, and DuckDB file-reader injection cases
- [x] 5.2 Test directory traversal, reserved names, and duplicate export filenames
- [x] 5.3 Test deterministic pagination during a stable catalog revision
- [x] 5.4 Test disconnect, timeout, and byte-limit resource cleanup
- [x] 5.5 Verify OpenAPI and MCP schemas expose only supported typed operations

