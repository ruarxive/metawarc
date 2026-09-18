## 1. Test Infrastructure
- [x] 1.1 Add generated `.warc` and `.warc.gz` fixture builders
- [x] 1.2 Add empty, no-response, malformed-header, and truncated fixtures
- [x] 1.3 Add supported, mismatched, corrupt, and oversized content fixtures
- [x] 1.4 Add duplicate basename/record-ID and unsafe filename fixtures
- [x] 1.5 Add legacy index fixtures for every supported migration path

## 2. Critical Workflow Coverage
- [x] 2.1 Test every CLI command, option, error code, stdout, and stderr contract
- [x] 2.2 Test index to stats/list/dump/get end-to-end workflows
- [x] 2.3 Test typed metadata extraction and cleanup
- [x] 2.4 Test update, rescan, force, interruption, and resume behavior
- [x] 2.5 Test REST and MCP authentication, filters, limits, and streaming cleanup
- [x] 2.6 Add bounded-memory performance regression tests

## 3. Static and Dependency Quality
- [x] 3.1 Configure Ruff format/check over the complete tracked Python tree
- [x] 3.2 Resolve existing correctness, unused-code, and formatting findings
- [x] 3.3 Add type checking to catalog, query, index, extraction, and API models
- [x] 3.4 Track and resolve dependency deprecation warnings
- [x] 3.5 Add dependency vulnerability, secret, and SBOM generation jobs

## 4. Packaging and CI
- [x] 4.1 Test minimum and latest supported Python versions
- [x] 4.2 Build wheel and source distribution in CI
- [x] 4.3 Install core, API, MCP, and all extras from built artifacts
- [x] 4.4 Run critical smoke workflows against installed artifacts
- [x] 4.5 Add phased critical-module and repository coverage gates

## 5. Documentation
- [x] 5.1 Test or generate CLI command reference from Click
- [x] 5.2 Correct database names, feature status, and memory/coverage claims
- [x] 5.3 Document architecture, workspace schema, migration, and threat model
- [x] 5.4 Add `CONTRIBUTING.md`, `SECURITY.md`, and a release checklist
- [x] 5.5 Add tested examples for core, API, and MCP installation variants

