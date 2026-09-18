# build-system Specification

## Purpose
TBD - created by archiving change consolidate-release-baseline. Update Purpose after archive.
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
REST API or MCP packages.

#### Scenario: Core package is installed
- **WHEN** a user installs `metawarc` without extras in a clean environment
- **THEN** every core CLI command imports successfully and a WARC smoke workflow
  completes without undeclared dependencies

### Requirement: Optional interface dependencies
The build system SHALL provide explicit extras for REST API and MCP features and
an aggregate extra for users who need all interfaces.

#### Scenario: API extra is omitted
- **WHEN** a user installs only the core package
- **THEN** the CLI reports how to install the API extra if `serve` is requested
  and does not fail during unrelated command imports

### Requirement: Reproducible package verification
CI SHALL build and install generated artifacts in clean environments rather than
testing only an editable source tree.

#### Scenario: Distribution content is incomplete
- **WHEN** a required module or template is missing from a built artifact
- **THEN** the clean-install verification fails before publication

