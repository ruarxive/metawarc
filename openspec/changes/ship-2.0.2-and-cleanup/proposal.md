# Change: Ship 2.0.2 and clean release-hygiene debt

## Why
The 2026-09-17 review (R0–R3) closed every P0–P2 finding from the 2026-08-04
review: dead packages are removed, `httpx2` is pinned, the `pyjwt`/`urllib3`
CVEs are tracked through Dependabot, MCP and dump coverage is high, hostile
inputs are tested, and the docs site is published. The 2.0.2 entry already
exists in `CHANGELOG.md` and `pyproject.toml`, but no `v2.0.2` release tag
exists, no built wheel/sdist for 2.0.2 is on disk, and `git describe --tags`
reports `v2.0.1-12-gb272283`. Meanwhile `dist/` still contains the 2.0.1
artifacts and `pip-audit` reports 17 transitive CVEs (pyjwt 14, urllib3 3) that
the two open Dependabot PRs (#34, #35) already fix. An orphan `v2` branch at
`94db570` (older than the 2.0.0 tag) misleads new contributors about which
line is canonical.

This change ships 2.0.2 from a tagged commit, clears the immediate CVE/audit
debt, removes the orphan branch, and tightens two small `.gitignore` /
`httpx2` footguns so the contributor path matches the CI build.

## What Changes
- Create the missing `v2.0.2` annotated tag at `b272283`, build the wheel and
  sdist from the tagged commit, smoke-test every extras combination, and
  attach the artifact to the GitHub release
- Merge the two open Dependabot security PRs (pyjwt 2.15.0, urllib3 2.8.0) so
  the published dev install is clean and `pip-audit` reports zero findings
- Delete the orphan `v2` branch from `origin` (after confirming no fork
  depends on it) and document the canonical-default-branch policy in the
  repository
- Add `.coverage` to the root `.gitignore` (already satisfied; line 44
  lists `.coverage` directly) and clarify the `httpx2` comment in
  `pyproject.toml` to reflect the starlette-internal dependency (no
  swap to plain `httpx`; starlette 1.x does `import httpx2 as httpx`)
- No public-API changes; consumers see only the new tag and the CVE fixes

## Impact
- Affected specs: `release-engineering`, `build-system`
- Affected code: `pyproject.toml` (dev extras pin), `.gitignore` (one
  entry), `dist/` (rebuilt artifacts), git tags and Dependabot PRs
- Dependencies: none; this is the first hygiene change after the 2026-09-18
  archive

## Risk
- Tagging and publishing to PyPI is a one-way operation. Mitigation: build
  and smoke-test in CI before publishing; keep the existing `v2.0.1` tag
  immutable per the `release-engineering` requirement.
- `httpx2` removal could break an unusual contributor setup. Mitigation:
  the change is scoped to the `dev` extra only; runtime installs are
  unaffected.
- Deleting `v2` is destructive. Mitigation: confirm no fork depends on
  the branch via `git branch -r --contains 94db570` before deletion; if
  uncertain, rename to `archive/pre-2.0-line` instead of deleting.