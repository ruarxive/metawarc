# Change: Establish test, quality, documentation, and release gates

## Why
The default branch contains no tracked tests and hundreds of lint findings. The
candidate branch has 13 passing tests but only 39% overall coverage and does not
exercise major CLI, extraction, export, streaming, migration, or security paths.
Documentation claims are not verified against actual commands.

## What Changes
- Add a representative WARC fixture matrix and critical end-to-end tests
- Cover CLI contracts, extraction, dump/get, API/MCP security, and migrations
- Run one lint/format configuration across all tracked Python code
- Add type checking incrementally at service and data boundaries
- Build and install package artifacts and extras in clean CI environments
- Treat documentation examples as tested behavior
- Add phased coverage gates, warning tracking, dependency scanning, and SBOMs
- Add contributor, security, architecture, and release documentation

## Impact
- Affected specs: `test-assurance`, `documentation-quality`
- Affected code: tests, fixtures, CI, lint/type/coverage configuration, packaging
  jobs, README, contributor/security/release documents
- Dependencies: begins after `consolidate-release-baseline`; expands alongside
  every later approved change

