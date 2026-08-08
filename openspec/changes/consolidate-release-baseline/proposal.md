# Change: Consolidate the release baseline

## Why
The default `master` branch reports version 1.2.0 and lacks the tests, packaging,
API, MCP, and fixes already tagged as `v1.3.1` on `testing`. This split makes the
repository, documentation, and distributable package describe different
products and encourages contributors to change obsolete code.

## What Changes
- Integrate the reviewed `testing`/`v1.3.1` work into one candidate baseline
- Establish one canonical default branch and repository URL
- Replace conflicting setup metadata with one `pyproject.toml` source of truth
- Separate core CLI, API, and MCP dependency groups
- Add explicit compatibility guidance for existing 1.2 and 1.3 indexes
- Require built artifacts and release metadata to come from the same commit
- **BREAKING**: remove contradictory legacy packaging configuration after a
  clean-install compatibility check

## Impact
- Affected specs: `release-engineering`, `build-system`
- Affected code: git branches, `pyproject.toml`, `setup.py`, `setup.cfg`,
  requirements files, package version metadata, README, changelog, CI workflows
- Dependencies: none; this is the first roadmap change

