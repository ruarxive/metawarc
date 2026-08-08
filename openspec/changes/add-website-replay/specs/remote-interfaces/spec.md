## ADDED Requirements

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
