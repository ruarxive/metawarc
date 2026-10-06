## ADDED Requirements

### Requirement: Collection summary tool
The MCP server SHALL register a `collection_stats` tool that wraps the
existing `AnalysisService.summary()` report and returns the result as a
serialisable mapping. The tool SHALL accept an optional archive
allowlist, a tuple of dimension names from the documented allowlist
(`mime`, `ext`, `status`, `host`, `date`, `size_bucket`), and an
optional `top` bound.

#### Scenario: Summary over the whole workspace
- **WHEN** an MCP client calls `collection_stats()` against a
  populated workspace
- **THEN** the tool returns a `data` mapping keyed by every requested
  dimension, with each entry listing the top values, counts, and
  bytes for that dimension

#### Scenario: `top` is rejected when zero
- **WHEN** an MCP client passes `top=0`
- **THEN** the tool returns a validation error rather than executing
  an unbounded query

### Requirement: Stored metadata summary tool
The MCP server SHALL register a `metadata_summary` tool that wraps the
existing `AnalysisService.stored_metadata()` report. The tool SHALL
accept the same `metadata_types` enum accepted by the local CLI
(`pdfs`, `images`, `ooxmldocs`, `oledocs`, `videos`, `audio`, `fonts`,
or `all` as the exclusive shorthand) and SHALL return one rollup row
per selected type plus documented `not-indexed` rows for any selected
type that has no current sidecar.

#### Scenario: `all` selects every supported type
- **WHEN** an MCP client passes `metadata_types="all"`
- **THEN** the tool returns one rollup for every entry in
  `STORED_METADATA_TYPES` in deterministic order, with
  `not-indexed` rows for types that have no active sidecar

#### Scenario: Unknown metadata type is rejected
- **WHEN** an MCP client passes a value that is neither `all` nor a
  member of `STORED_METADATA_TYPES`
- **THEN** the tool returns a validation error naming the unsupported
  value

### Requirement: MCP tool inventory contract
The MCP server SHALL keep its tool inventory consistent with the
existing contract: no tool accepts arbitrary SQL, arbitrary filesystem
paths, or catalog mutation operations. New tools added in this change
SHALL inherit that contract and SHALL be discoverable through the
existing `test_mcp_inventory_is_minimal_and_read_only` assertion.

#### Scenario: Inventory check still passes
- **WHEN** the CI suite runs
- **THEN** the inventory test still passes and the new tools appear in
  the allowlist with the documented read-only signatures