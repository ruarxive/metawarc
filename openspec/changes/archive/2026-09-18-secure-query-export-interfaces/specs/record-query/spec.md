## ADDED Requirements

### Requirement: Typed record filters
The query service SHALL support typed filters for archive ID, MIME type,
extension, URL or host pattern, HTTP status, record date, and content length.

#### Scenario: Multiple filters are combined
- **WHEN** a client specifies PDF extension, successful status, and a minimum
  content length
- **THEN** the service returns only records satisfying all supplied filters

### Requirement: Parameterized values
All user-controlled query values SHALL be passed as database parameters and
SHALL NOT be interpolated into SQL text.

#### Scenario: Filter contains a quote
- **WHEN** a URL or MIME filter contains SQL quote or comment characters
- **THEN** the characters are treated as data and cannot change query structure

### Requirement: Allowlisted query structure
Queryable fields, comparison operators, sort fields, and sort directions SHALL
be selected from an explicit allowlist.

#### Scenario: Unsupported sort field is requested
- **WHEN** a client supplies a field outside the allowlist
- **THEN** the service rejects the request with a validation error before
  executing a database query

### Requirement: Catalog-scoped data access
The query service SHALL read only sidecars registered to the selected workspace
and archive identifiers.

#### Scenario: External path is supplied as an identifier
- **WHEN** a client supplies a filesystem path where an archive ID is expected
- **THEN** the service rejects it and does not open the path

### Requirement: Deterministic bounded pagination
Record lists SHALL use deterministic ordering and SHALL enforce configured
maximum limits for offsets or cursors, page sizes, and query duration.

#### Scenario: Page size exceeds the maximum
- **WHEN** a client requests more records than the configured maximum page size
- **THEN** the request is rejected or clamped according to the documented API
  contract and cannot allocate an unbounded result

### Requirement: Trusted local SQL isolation
If advanced raw SQL remains available, it SHALL require an explicit local-only
unsafe option and SHALL never be accepted by REST or MCP interfaces.

#### Scenario: Remote client submits a raw query
- **WHEN** a REST or MCP client sends an arbitrary SQL fragment
- **THEN** the interface rejects the unsupported field without executing it

