## ADDED Requirements

### Requirement: Representative WARC fixtures
The test suite SHALL include generated compressed and uncompressed WARC fixtures
covering valid, empty, malformed, duplicate, unsupported, and hostile inputs.

#### Scenario: Uncompressed regression is introduced
- **WHEN** a code change breaks `.warc` while `.warc.gz` still works
- **THEN** the required fixture matrix fails CI before merge

### Requirement: Critical end-to-end workflows
CI SHALL execute indexing through query and export using built package artifacts,
not only unit tests against an editable checkout.

#### Scenario: Installed dependency is missing
- **WHEN** a core command imports a package absent from distribution metadata
- **THEN** the clean-install workflow fails before release

### Requirement: Interface contract tests
Every CLI command and remote endpoint SHALL have tests for success, invalid
input, missing data, configured limits, and resource cleanup.

#### Scenario: Missing database is requested
- **WHEN** a CLI or API operation targets a missing database
- **THEN** a test verifies the documented nonzero exit or 4xx response and
  verifies that no empty database was created

### Requirement: Migration tests
Every supported catalog migration SHALL be tested from a representative prior
schema and SHALL verify both success and recoverable failure behavior.

#### Scenario: Migration is interrupted
- **WHEN** a simulated failure occurs before the new catalog commits
- **THEN** the original catalog remains recoverable and the test detects no
  partially active schema

### Requirement: Full-tree static analysis
The selected linter and formatter SHALL run over every tracked Python source file
under one repository configuration.

#### Scenario: New module contains a correctness error
- **WHEN** a tracked module introduces an undefined name or equivalent enabled
  rule violation
- **THEN** static analysis fails CI regardless of the module's package path

### Requirement: Phased coverage gates
Coverage policy SHALL prioritize critical workflows and SHALL raise the
repository-wide threshold in documented stages.

#### Scenario: Aggregate coverage rises while indexing loses coverage
- **WHEN** a change removes a required critical indexing test but adds unrelated
  covered code
- **THEN** the critical-workflow gate still fails

### Requirement: Dependency and release evidence
CI SHALL track deprecation warnings, scan dependencies and secrets, and generate
an SBOM for release artifacts.

#### Scenario: Release candidate has a known policy violation
- **WHEN** scanning detects a vulnerability above the configured severity policy
- **THEN** publication is blocked or requires a documented approved exception

