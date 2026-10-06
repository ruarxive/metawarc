# remote-interfaces Specification

## Purpose
Exposes the typed query and export services through a read-only REST API
and an explicit read-only MCP tool allowlist. Both servers bind to loopback
by default, recognize every canonical IPv4 and IPv6 loopback representation,
require configured authentication or an explicit insecure acknowledgement
for non-loopback binds, and enforce the same page, byte, time, and
concurrency limits as the local CLI.
## Requirements
### Requirement: Safe bind default
REST and MCP servers SHALL bind to `127.0.0.1` by default and SHALL
recognize every canonical IPv4 and IPv6 loopback representation,
including the IPv6 long form, before deciding whether the configured
host requires authentication or insecure acknowledgement.

#### Scenario: Server starts without host configuration
- **WHEN** a user runs the serve or MCP command with defaults
- **THEN** the listener is available only through the loopback interface

#### Scenario: Loopback host is provided in long IPv6 form
- **WHEN** a user sets `METAWARC_HOST=0:0:0:0:0:0:0:1` (or any other
  canonical IPv6 loopback string) without authentication or acknowledgement
- **THEN** startup succeeds on the loopback interface and does not require
  a token or `--allow-insecure`

#### Scenario: Host string is invalid
- **WHEN** a user supplies a string that is neither a valid IP address nor
  a recognized hostname
- **THEN** startup fails with an actionable error message naming the
  invalid value

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

### Requirement: Batch jobs share remote safety defaults
When batch jobs are exposed over REST, they SHALL mount on the existing
`metawarc serve` application, bind to loopback by default, require
authentication or explicit insecure acknowledgement for non-loopback
binds, and enforce the same concurrency, time, and payload-byte limits
as other remote payload operations. Job state, persistence, and
supported job kinds SHALL be defined by the `remote-batch-job`
capability spec.

#### Scenario: Batch job route requires authentication on a non-loopback bind
- **WHEN** the server is started with `--token` and a client calls
  `POST /jobs` without an `Authorization` header
- **THEN** the route returns 401 with the documented error envelope

#### Scenario: Batch job route inherits the request timeout
- **WHEN** a job handler runs longer than
  `ServerSettings.request_timeout_seconds`
- **THEN** the runner marks the job `failed`, the route returns
  the documented timeout code, and the worker is released

