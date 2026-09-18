## ADDED Requirements

### Requirement: Replay home navigation
The serve application SHALL provide an HTML home page that lists archived
websites from the workspace catalog and links each site into rewritten replay.

#### Scenario: Home lists hosts with replay links
- **WHEN** a user opens `/` or `/replay` against a workspace that contains
  captures for one or more hosts
- **THEN** the response is an HTML page listing those hosts with navigation
  links to `/replay/<timestamp>mp_/<entry-url>`

#### Scenario: Preferred entry URL
- **WHEN** a host has both `https://example.com/` and deeper HTML paths
- **THEN** the home page prefers the site root URL as the entry link

### Requirement: Capture selection by URL and timestamp
The system SHALL select a response capture from the workspace catalog by exact
URL and a timestamp policy of closest or exact match. SURT or URL-key matching
is not required for this capability's first milestone.

#### Scenario: Closest timestamp wins
- **WHEN** a user requests URL `https://example.com/` at timestamp `20200101120000`
  and captures exist at `20191201000000` and `20200102000000`
- **THEN** the closer capture by absolute time difference is selected

#### Scenario: Exact timestamp match
- **WHEN** a user requests an exact timestamp policy and a capture exists with
  that `rec_date`
- **THEN** that capture is returned and no neighbor is substituted

#### Scenario: Missing URL
- **WHEN** no response record matches the requested URL
- **THEN** the system returns a not-found result without scanning WARC payloads

### Requirement: Inline payload replay without duplication
Replay SHALL stream the selected capture payload from the source WARC using the
catalog offset and length, without copying the payload into the workspace.

#### Scenario: Replay streams from WARC offset
- **WHEN** a capture is selected for replay
- **THEN** bytes are read from the archived source at the stored offset and
  served with the indexed content type as a navigable response

### Requirement: Bounded redirect following
When a selected capture is an HTTP redirect with a `Location` header, replay
SHALL rewrite the next hop into the replay URL space up to a configured hop
limit.

#### Scenario: Single redirect hop
- **WHEN** a capture returns status `302` with `Location: https://example.com/b`
- **THEN** the client is directed to the replay URL for `https://example.com/b`
  at the same timestamp context

#### Scenario: Hop limit exceeded
- **WHEN** redirect following would exceed the configured hop limit
- **THEN** replay stops and returns an actionable error without further fetches

### Requirement: HTML and CSS URL rewriting
In rewritten replay mode, the system SHALL rewrite HTML resource attributes and
CSS `url(...)` values that point at absolute `http`/`https` targets into the
local replay URL prefix for the same timestamp context.

#### Scenario: Stylesheet link is rewritten
- **WHEN** rewritten-mode HTML contains `<link rel="stylesheet" href="https://example.com/a.css">`
- **THEN** the served HTML references the replay URL for that stylesheet

#### Scenario: Raw identity mode skips rewriting
- **WHEN** a client requests identity/raw replay mode for an HTML capture
- **THEN** the original bytes are streamed without URL rewriting or banner injection

### Requirement: Optional CDXJ export for external replay engines
The system SHALL be able to export a CDXJ index derived from active record
sidecars and catalog archive paths so an external pywb (or compatible) engine
can replay the same WARC sources.

#### Scenario: CDXJ export lists captures
- **WHEN** a user exports CDXJ for a workspace
- **THEN** each indexed response record appears with URL, timestamp, status,
  MIME, digests when present, and WARC filename/offset/length fields needed by
  CDX consumers

### Requirement: Replay remains an optional dependency surface
Core indexing and querying SHALL remain installable and usable without replay
or pywb packages.

#### Scenario: Core install lacks replay extra
- **WHEN** only the core package is installed
- **THEN** index, query, and dump commands work and replay commands fail with
  guidance to install the replay extra
