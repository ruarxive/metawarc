## ADDED Requirements

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
