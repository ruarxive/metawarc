## ADDED Requirements

### Requirement: Module entry smoke test
The `python -m metawarc` invocation SHALL be exercised by an automated
test that runs the subprocess and asserts the documented exit status and
output.

#### Scenario: `python -m metawarc --version` succeeds
- **WHEN** a contributor runs the test suite
- **THEN** an automated test invokes `[sys.executable, "-m", "metawarc",
  "--version"]` in a subprocess and asserts exit 0 and the package
  version in stdout

### Requirement: Per-module coverage floor for public surfaces
CI SHALL enforce a per-module coverage floor of 70 % for every public
surface module in addition to the repository-wide coverage gate.

#### Scenario: A public-surface refactor loses covered branches
- **WHEN** a refactor reduces coverage on `metawarc.cmds.server`,
  `metawarc.cmds.dump`, `metawarc.mcp_server`, or
  `metawarc.cmds.indexer` below 70 %
- **THEN** the matching `--cov-fail-under=70` step in the CI matrix
  fails before the PR is merged

## MODIFIED Requirements

### Requirement: Phased coverage gates
Coverage policy SHALL prioritize critical workflows and SHALL raise the
repository-wide threshold in documented stages, and SHALL additionally
enforce a per-module floor of 70 % for every public surface module
identified by the test-assurance capability.

#### Scenario: Aggregate coverage rises while indexing loses coverage
- **WHEN** a change removes a required critical indexing test but adds
  unrelated covered code
- **THEN** the critical-workflow gate still fails

#### Scenario: A non-indexer public surface loses coverage
- **WHEN** a change to `metawarc.cmds.server`, `metawarc.cmds.dump`, or
  `metawarc.mcp_server` drops its module coverage below 70 % without
  affecting the indexer
- **THEN** the corresponding per-module gate fails even if the
  repository-wide gate remains green

### Requirement: Interface contract tests
Every CLI command and remote endpoint SHALL have tests for success,
invalid input, success-path authentication, missing-data authentication,
configured limits, and resource cleanup, including authentication tests
for every documented REST endpoint that accepts a bearer token.

#### Scenario: Missing database is requested
- **WHEN** a CLI or API operation targets a missing database
- **THEN** a test verifies the documented nonzero exit or 4xx response
  and verifies that no empty database was created

#### Scenario: Bearer-protected endpoint is requested without a token
- **WHEN** a REST endpoint that requires a bearer token is requested
  without an `Authorization` header
- **THEN** a test verifies the documented 401 response

#### Scenario: Bearer-protected endpoint is requested with an invalid token
- **WHEN** a REST endpoint that requires a bearer token is requested
  with an `Authorization: Bearer <wrong>` header
- **THEN** a test verifies the documented 401 response