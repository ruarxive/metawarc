## ADDED Requirements

### Requirement: Shared progress events
Long-running core services SHALL accept an optional presentation-neutral
progress callback and SHALL emit monotonic events describing operation, phase,
unit, completed work, optional total work, and current item context.

#### Scenario: Service is called without a callback
- **WHEN** a library caller starts a covered long-running service without a
  progress callback
- **THEN** the service performs the same work without writing progress output

#### Scenario: Exact total is unavailable
- **WHEN** determining a total would require an additional full archive scan
- **THEN** events report completed work with no total rather than pre-scanning or
  presenting a misleading percentage or ETA

### Requirement: Interactive CLI progress
The CLI SHALL render shared progress events for covered long-running commands
when progress is enabled and SHALL show elapsed work plus counts or bytes, rate,
and an ETA only when the total supports one.

#### Scenario: Interactive content indexing
- **WHEN** a user runs `index-content` in an interactive terminal for multiple
  metadata types or archives
- **THEN** the CLI shows overall type/archive completion and current candidate
  records while identifying the active metadata type and archive

#### Scenario: Work is skipped or fails
- **WHEN** a covered operation skips or fails a selected work item
- **THEN** overall progress advances, the outcome counters reflect the result,
  and the final command summary remains authoritative

### Requirement: Progress mode controls
Each covered command SHALL support `--progress/--no-progress`; when neither is
specified, progress SHALL be enabled only for a human-oriented invocation whose
stderr is an interactive terminal.

#### Scenario: Interactive auto mode
- **WHEN** a covered human-oriented command runs with interactive stderr and no
  progress override
- **THEN** progress is displayed

#### Scenario: Redirected auto mode
- **WHEN** a covered command runs with non-interactive stderr and no progress
  override
- **THEN** no animated progress is displayed

#### Scenario: Progress is forced
- **WHEN** a user supplies `--progress` to a covered human-oriented invocation
  without silent output
- **THEN** progress is rendered even if terminal auto-detection would disable it

#### Scenario: Progress is disabled
- **WHEN** a user supplies `--no-progress`
- **THEN** no progress presentation is emitted

### Requirement: Output channel isolation
Progress presentation SHALL use stderr and SHALL NOT alter command result
schemas or contaminate stdout.

#### Scenario: JSON result is captured
- **WHEN** a covered command emits a JSON result
- **THEN** stdout contains valid JSON without progress frames or status text

#### Scenario: Silent mode is requested
- **WHEN** a user supplies `--silent`
- **THEN** no progress presentation is emitted even if `--progress` is also
  supplied

#### Scenario: Machine-readable output mode is requested
- **WHEN** a user explicitly selects a JSON or JSON Lines output mode
- **THEN** automatic progress is disabled and stdout remains machine-readable

### Requirement: Covered long-running commands
Progress reporting SHALL cover record indexing, applied incremental ingestion,
typed content indexing, bulk payload export, stored metadata export, payload
hashing, and integrity analysis.

#### Scenario: Ingestion is only planned
- **WHEN** a user runs incremental ingestion in dry-run mode
- **THEN** no processing progress is shown because no long-running indexing work
  is applied

#### Scenario: Bulk payload work runs
- **WHEN** a user indexes, exports, hashes, or verifies multiple payload records
- **THEN** progress identifies the current archive or record phase and advances
  at natural streaming boundaries

### Requirement: Safe progress lifecycle
Progress rendering SHALL stop cleanly after normal completion, service failure,
or keyboard interruption and SHALL preserve the command's normal summary,
error, exit status, checkpoint, and cleanup behavior.

#### Scenario: Content extraction raises an error
- **WHEN** a content-indexing operation fails while progress is active
- **THEN** the live display closes before the error is rendered and the run is
  recorded using the existing partial or failed semantics

#### Scenario: User interrupts indexing
- **WHEN** a user sends a keyboard interrupt during a covered operation
- **THEN** progress rendering closes and existing checkpoint and temporary-file
  handling runs unchanged

### Requirement: Bounded presentation overhead
Progress reporting SHALL NOT add unbounded buffering or an extra full payload
scan, and the terminal renderer SHALL coalesce refreshes to a bounded frequency.

#### Scenario: Large archive is processed
- **WHEN** a covered command processes a large archive
- **THEN** progress state remains bounded by active tasks and rendering frequency
  does not grow with the number of records

