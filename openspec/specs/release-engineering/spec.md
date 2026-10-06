# release-engineering Specification

## Purpose
Designates one canonical branch as the source of released code,
documentation, version metadata, CI configuration, and signed `vMAJOR.MINOR.PATCH`
tags, and forbids moving existing tags. Every release declares the index
schema versions it can read, migrate, rebuild, or reject, and its artifacts
are built, installed, and smoke-tested from the tagged commit.
## Requirements
### Requirement: Canonical release source
The project SHALL designate one default branch as the source of released
code, documentation, version metadata, and CI configuration, and SHALL
publish every release from the tip of that branch as a Git tag.

#### Scenario: Release is prepared
- **WHEN** a release candidate is built
- **THEN** its package version, changelog, documentation, source, and
  Git tag all resolve to the same commit on the canonical branch, and the
  resulting tag is listed by `git tag --list 'v*'`

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
Release artifacts SHALL be built and tested from the exact commit identified
by the release tag, and the release tag SHALL be created from the same
commit that produced the changelog and `pyproject.toml` updates.

#### Scenario: Artifact is published
- **WHEN** a wheel or source distribution is selected for publication
- **THEN** CI has built, installed, and smoke-tested that artifact from
  the tagged commit, and `git describe --tags` on the artifact's source
  reports the tag name without an `-N-g` suffix

### Requirement: Release tag is required before publication
Every release that appears in `CHANGELOG.md` and `pyproject.toml` SHALL
also exist as a Git tag pointing at the same commit before any artifact
is published to PyPI or attached to a GitHub release.

#### Scenario: Changelog claims a version that has no tag
- **WHEN** a release engineer prepares a version listed in `CHANGELOG.md`
- **THEN** the corresponding Git tag exists, points at the commit whose
  source produced the published wheel, and is the only tag at that
  version

#### Scenario: Stale artifact is left in `dist/`
- **WHEN** a release is published
- **THEN** the working tree's `dist/` directory contains the artifact for
  the published version, and no artifact for an unpublished version
  remains in the tree

### Requirement: Orphan branch cleanup
Ad-hoc Git branches that pre-date the current canonical line and are not
referenced from the repository documentation SHALL be deleted or renamed
to an `archive/*` namespace within one release cycle of being identified.

#### Scenario: Pre-release branch is identified
- **WHEN** a branch is older than the most recent major release tag and is
  not the head of any tracked line
- **THEN** the branch is either removed from `origin` or renamed to make
  its archival intent explicit

