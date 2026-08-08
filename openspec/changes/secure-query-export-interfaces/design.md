## Context

CLI, dump, API, and catalog helpers currently build SQL independently. Regex
rejection of selected keywords does not make arbitrary DuckDB expressions safe,
especially when a network user can invoke data-reading functions or expensive
queries. Export uses identifiers controlled by WARC input as local filenames.

## Goals / Non-Goals

- Goals:
  - centralize record selection and pagination behavior;
  - prevent values, identifiers, and paths from changing SQL structure;
  - make remote defaults safe for local use;
  - make extraction bounded, reproducible, and path-safe;
  - keep MCP capabilities explicitly allowlisted and read-only.
- Non-Goals:
  - provide a general DuckDB console over HTTP;
  - implement user accounts or a multi-tenant authorization system;
  - expose arbitrary local filesystem paths through API/MCP.

## Decisions

### Decision: Query objects compile to controlled SQL

A `RecordQuery` value object contains typed optional filters: archive IDs, MIME,
extension, URL/host pattern, status, date range, content-length range, sort,
offset/cursor, and limit. An allowlist maps fields/operators to SQL fragments.
All values use DuckDB parameters. Sidecar paths come from the workspace catalog.

### Decision: Raw SQL is local-only and explicitly unsafe

The network API and MCP tools have no raw query field. The CLI can retain an
advanced WHERE expression only under a visibly named unsafe/trusted flag, with a
warning that it is for local trusted input. It is never passed through remote
interfaces.

### Decision: Exports use generated safe names and manifests

Filenames use a sanitized record-ID token plus a detected extension. Directory
separators, control characters, reserved names, and traversal tokens are
removed. Collisions receive deterministic suffixes. Every output maps to its
archive, record ID, URL, source, content type, byte count, and checksum in a
manifest.

### Decision: Remote interfaces are adapters over services

FastAPI and MCP call the same query/export services used by the CLI. The server
binds to `127.0.0.1` by default. Non-loopback binding requires configured
authentication or an explicit insecure acknowledgement. MCP registers a small
set of named, read-only tools rather than converting the full application.

### Decision: Streaming owns resource lifetime

The payload iterator opens the source only when iteration begins and closes it
on completion, exception, timeout, or client cancellation. Page, byte, and time
limits are applied before and during streaming.

## Risks / Trade-offs

- Removing raw network queries reduces flexibility. Mitigation: expand typed
  filters based on concrete use cases and keep trusted local SQL available.
- Authentication adds configuration. Mitigation: loopback remains zero-config;
  public binding requires deliberate setup.
- Generated filenames differ from previous exports. Mitigation: the manifest
  preserves identifiers and an optional safe template can be documented.
- Offset pagination can change under concurrent index updates. Mitigation: use
  deterministic ordering and expose a catalog revision or cursor for remote use.

## Migration Plan

1. Implement the typed query object and service with parity tests.
2. Route CLI list/dump/get through the service.
3. Add safe filename and manifest behavior with an opt-in compatibility preview.
4. Replace API query construction and remove raw network SQL.
5. Add response models, authentication configuration, and safe bind defaults.
6. Replace automatic MCP conversion with explicit tools.
7. Deprecate old remote parameters for one documented transition where feasible.

## Open Questions

- Is a static bearer token sufficient for the supported deployment model?
- Should remote pagination use opaque cursors from the first release?
- Which checksum is included in export manifests by default?
- Is local unsafe SQL retained indefinitely or deprecated after typed-filter parity?

