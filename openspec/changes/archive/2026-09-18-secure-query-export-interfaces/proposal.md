# Change: Secure query, export, REST, and MCP interfaces

## Why
Current code interpolates filters, identifiers, paths, URLs, and SQL fragments.
The candidate REST API exposes an arbitrary WHERE fragment, binds publicly by
default, and has no authentication. Payload export also trusts WARC record IDs
as filenames and can overwrite files or escape the output directory.

## What Changes
- Add one typed query service shared by CLI, REST, MCP, and exporters
- Parameterize values and allowlist fields, operators, sorting, and sidecars
- Remove arbitrary SQL from network interfaces
- Keep advanced local SQL only behind an explicit trusted/unsafe option
- Add deterministic pagination and record/byte/time limits
- Sanitize and uniquify payload filenames and write an export manifest
- Default servers to loopback and require authentication for non-loopback use
- Define explicit, read-only MCP tools rather than automatically exposing all API
  routes
- Add response models, stable errors, and cancellation-safe streaming
- **BREAKING**: raw network `query` parameters are removed

## Impact
- Affected specs: `record-query`, `payload-export`, `remote-interfaces`
- Affected code: DuckDB helpers, Dumper, Click commands, FastAPI router/server,
  MCP setup, response models, settings, logging
- Dependencies: `stabilize-index-workspace`

