# release-engineering Specification

## Purpose
TBD - created by archiving change consolidate-release-baseline. Update Purpose after archive.
## Requirements
### Requirement: Canonical release source
The project SHALL designate one default branch as the source of released code,
documentation, version metadata, and CI configuration.

#### Scenario: Release is prepared
- **WHEN** a release candidate is built
- **THEN** its package version, changelog, documentation, and source all resolve
  to the same commit on the canonical branch

### Requirement: Immutable release history
The project SHALL preserve published tag history and SHALL NOT move an existing
release tag to a different commit during branch consolidation.

#### Scenario: Existing tag differs from the candidate baseline
- **WHEN** consolidation discovers a published tag on another commit
- **THEN** the tag remains unchanged and the corrected release receives a new
  version and tag

### Requirement: Index compatibility declaration
Every release that changes catalog or sidecar behavior SHALL declare which index
schema versions it can read, migrate, rebuild, or reject.

#### Scenario: User opens an unsupported index
- **WHEN** the tool detects an index schema it cannot safely read
- **THEN** it exits without modifying the index and prints a migrate or rebuild
  instruction

### Requirement: Artifact provenance
Release artifacts SHALL be built and tested from the exact commit identified by
the release tag.

#### Scenario: Artifact is published
- **WHEN** a wheel or source distribution is selected for publication
- **THEN** CI has built, installed, and smoke-tested that artifact from the
  tagged commit

