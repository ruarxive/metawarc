## ADDED Requirements

### Requirement: Safe output paths
Payload export SHALL generate filenames that remain direct children of the
selected output directory regardless of WARC record ID, URL, or MIME values.

#### Scenario: Record ID contains traversal characters
- **WHEN** an exported record ID contains directory separators or `..`
- **THEN** those tokens cannot affect the output directory and the payload is
  written under a sanitized generated name

### Requirement: No silent overwrite
Payload export SHALL detect filename collisions and SHALL NOT silently replace a
payload selected earlier in the same run or an existing file by default.

#### Scenario: Two records generate the same base filename
- **WHEN** both records are exported
- **THEN** each receives a distinct deterministic path and both mappings appear
  in the manifest

### Requirement: Bounded streaming export
Payload export SHALL stream selected records without retaining all result rows or
payload bytes in memory and SHALL enforce record and total-byte limits.

#### Scenario: Byte limit is reached
- **WHEN** writing the next payload would exceed the configured total-byte limit
- **THEN** export stops before that payload, closes resources, and reports the
  limit in the run summary and manifest

### Requirement: Export manifest
Every export run SHALL create a machine-readable manifest containing output
path, archive ID, record ID, source, URL, content type, byte count, and checksum
for each completed payload.

#### Scenario: Export completes partially
- **WHEN** some selected records fail or a configured limit stops the run
- **THEN** the manifest distinguishes completed, skipped, and failed records

### Requirement: Resource cleanup
Every WARC and output handle SHALL close on normal completion, parser failure,
keyboard interruption, timeout, and remote-client cancellation.

#### Scenario: Client disconnects during streaming
- **WHEN** a remote payload download is cancelled
- **THEN** the source archive handle is closed and no output is reported complete
  unless its full byte stream was delivered

