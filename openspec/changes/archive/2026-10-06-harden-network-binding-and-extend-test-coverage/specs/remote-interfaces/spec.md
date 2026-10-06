## MODIFIED Requirements

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