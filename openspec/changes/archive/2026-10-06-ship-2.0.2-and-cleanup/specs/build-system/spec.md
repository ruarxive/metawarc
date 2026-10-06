## MODIFIED Requirements

### Requirement: Reproducible package verification
CI SHALL build and install generated artifacts in clean environments rather
than testing only an editable source tree, and SHALL fail the release if
any common runtime install path still reports known vulnerabilities above
the configured severity policy.

#### Scenario: Distribution content is incomplete
- **WHEN** a required module or template is missing from a built artifact
- **THEN** the clean-install verification fails before publication

#### Scenario: Built artifact carries a known CVE
- **WHEN** `pip-audit` reports a known vulnerability above the configured
  severity policy against the built wheel's dependency closure
- **THEN** CI fails before the artifact is published and the release is
  blocked until the dependency is upgraded and the audit is clean

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