## ADDED Requirements

### Requirement: Multi-platform CI matrix
CI SHALL execute the test suite on at least one Linux runner, one
macOS runner, and one Windows runner, with Python versions spanning
the supported Python range.

#### Scenario: A Windows-only path regression is introduced
- **WHEN** a code change breaks path handling on Windows while leaving
  POSIX runners green
- **THEN** the Windows matrix entry fails before the PR is merged

### Requirement: Contributor-path audit
CI SHALL run `pip-audit` against the editable install dependency closure
in the same job that runs the tests, so a contributor's local install is
audited in the same path it is used.

#### Scenario: Contributor install contains a known CVE
- **WHEN** a contributor-visible dependency test in the editable install
  closure reports a known CVE above the configured severity policy
- **THEN** the `test` job fails before the PR is merged, with the CVE
  identifier in the failure log

## MODIFIED Requirements

### Requirement: Reproducible package verification
CI SHALL build and install generated artifacts in clean environments
rather than testing only an editable source tree, SHALL execute the
test suite on at least one Linux, one macOS, and one Windows runner,
and SHALL fail the release if any common runtime install path still
reports known vulnerabilities above the configured severity policy.

#### Scenario: Distribution content is incomplete
- **WHEN** a required module or template is missing from a built artifact
- **THEN** the clean-install verification fails before publication

#### Scenario: Built artifact carries a known CVE
- **WHEN** `pip-audit` reports a known vulnerability above the configured
  severity policy against the built wheel's dependency closure
- **THEN** CI fails before the artifact is published and the release is
  blocked until the dependency is upgraded and the audit is clean