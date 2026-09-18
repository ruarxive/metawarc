# remote-interfaces Specification

## Purpose
TBD - created by archiving change secure-query-export-interfaces. Update Purpose after archive.
## Requirements
### Requirement: Safe bind default
REST and MCP servers SHALL bind to `127.0.0.1` by default.

#### Scenario: Server starts without host configuration
- **WHEN** a user runs the serve or MCP command with defaults
- **THEN** the listener is available only through the loopback interface

### Requirement: Authenticated non-loopback exposure
The server SHALL require configured authentication or an explicit documented
insecure acknowledgement before binding to a non-loopback address.

#### Scenario: Public bind lacks authentication
- **WHEN** a user requests `0.0.0.0` without authentication or acknowledgement
- **THEN** startup fails with an actionable security message

### Requirement: Stable API models
Every REST endpoint SHALL declare success and error response models, validation
rules, and pagination fields in OpenAPI.

#### Scenario: Invalid filter is supplied
- **WHEN** request validation rejects a filter
- **THEN** the API returns the documented error envelope with a 4xx status

### Requirement: Bounded remote operations
REST and MCP operations SHALL enforce configured page, payload-byte, query-time,
and concurrency limits.

#### Scenario: Query exceeds its time budget
- **WHEN** a remote query reaches the configured duration limit
- **THEN** it is cancelled, resources are closed, and the client receives a
  bounded error response

### Requirement: Explicit read-only MCP tools
The MCP server SHALL register an explicit allowlist of read-only archive and
record tools backed by typed services.

#### Scenario: MCP tool inventory is inspected
- **WHEN** a client lists available tools
- **THEN** no tool accepts arbitrary SQL, arbitrary filesystem paths, or catalog
  mutation operations

### Requirement: Request traceability without secret leakage
Remote requests SHALL receive a trace identifier and structured logs SHALL omit
authentication secrets and payload content.

#### Scenario: Authenticated request is logged
- **WHEN** a request includes an authorization credential
- **THEN** the log contains request metadata and trace ID but not the credential

### Requirement: Replay endpoints inherit remote safety defaults
When replay is exposed over HTTP, it SHALL mount on the existing `metawarc serve`
application, bind to loopback by default, require authentication or explicit
insecure acknowledgement for non-loopback binds, and enforce the same
payload-byte, time, and concurrency limits as other remote payload operations.

#### Scenario: Replay starts on loopback
- **WHEN** a user starts `metawarc serve` with default host settings
- **THEN** replay routes are available only on the loopback interface with the
  same listener as the existing API

#### Scenario: Replay payload exceeds byte budget
- **WHEN** a replay response would exceed the configured maximum payload bytes
- **THEN** the server stops streaming, closes resources, and returns a bounded
  error response

### Requirement: Replay routes on the serve application
The serve application SHALL expose replay under `/replay/...` without requiring
a second long-running process.

#### Scenario: Replay path is reachable from serve
- **WHEN** `metawarc serve` is running against a workspace that includes a
  matching capture
- **THEN** a client can request `/replay/<timestamp>/<url>` on that same server
  and receive the selected capture

