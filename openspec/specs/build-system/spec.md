# build-system Specification

## Purpose
Defines package metadata, dependencies, optional extras, and the entry point
from a single authoritative `pyproject.toml`. CI builds and smoke-tests wheel
and sdist artifacts in clean environments so the published closure matches
the contributor install.
## Requirements
### Requirement: Single package metadata source
The build system SHALL define package metadata, supported Python versions,
dependencies, entry points, and package data from one authoritative
`pyproject.toml` configuration.

#### Scenario: Package metadata is inspected
- **WHEN** a wheel and source distribution are built
- **THEN** both artifacts report the same version, license, dependencies, Python
  requirement, and `metawarc` console entry point

### Requirement: Minimal core installation
The default package installation SHALL include everything required for CLI
indexing, querying, metadata extraction, and payload export without requiring
REST API or MCP packages, and SHALL use only canonical, currently-maintained
distributions for every required dependency.

#### Scenario: Core package is installed
- **WHEN** a user installs `metawarc` without extras in a clean environment
- **THEN** every core CLI command imports successfully and a WARC smoke
  workflow completes without undeclared dependencies, and no required
  dependency points at an unmaintained PyPI mirror

#### Scenario: Dev extra pulls an unmaintained mirror
- **WHEN** a `[dev]`-extra distribution resolves to an unmaintained PyPI
  mirror instead of the canonical package
- **THEN** the canonical package is used in its place and the dev extra
  continues to provide the same functionality

### Requirement: Optional interface dependencies
The build system SHALL provide explicit extras for REST API and MCP features and
an aggregate extra for users who need all interfaces.

#### Scenario: API extra is omitted
- **WHEN** a user installs only the core package
- **THEN** the CLI reports how to install the API extra if `serve` is requested
  and does not fail during unrelated command imports

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

