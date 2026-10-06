# Change: Harden network binding and extend test depth

## Why
The `metawarc` remote-interfaces surface is the project's security boundary.
After the 2026-09-17 review closed the high-priority items, three concrete
gaps remain:

1. `metawarc.settings.is_loopback` (`metawarc/settings.py:58`) uses set
   membership on a fixed string set (`{"127.0.0.1", "::1", "localhost"}`)
   and therefore misses the IPv6 long-form `0:0:0:0:0:0:0:1`, which a
   user could supply through `METAWARC_HOST` and bypass the loopback check.
2. The REST authentication surface (`metawarc/cmds/server.py` lines 48,
   85–97, 121–123) is the part of the code with the lowest test coverage
   on a security-critical module (90 % module coverage, with the
   authentication branches exercised only by their absence).
3. The current CI matrix covers Ubuntu 3.10, Ubuntu 3.13, and macOS 3.13.
   Windows is missing, despite path-separator, drive-letter, and
   line-ending differences that affect DuckDB and WARC handling. A
   contributor's first run on Windows is unguarded.
4. The per-module coverage gate in CI applies only to
   `metawarc.cmds.indexer`. The other public surfaces (`cmds.server`,
   `cmds.dump`, `mcp_server`) are unprotected by an equivalent floor, and
   a refactor could drop their coverage below 70 % without breaking the
   gate.
5. `pip-audit` runs in the `package` job but not in the `test` job.
   Contributor environments and the build job therefore disagree on CVE
   status.
6. `metawarc/__main__.py` is 0 % covered (3 trivial lines) and the
   `python -m metawarc` entry point is not directly tested.
7. The repository lacks `CODE_OF_CONDUCT.md` and `SUPPORT.md`, which are
   standard governance files for a project with a published docs site and
   a public REST/MCP surface.
8. Twelve of thirteen OpenSpec specification files in
   `openspec/specs/*/spec.md` still carry the placeholder line
   `TBD - created by archiving change …. Update Purpose after archive.`
   The OpenSpec principle "Specs are truth" is undermined when the
   first paragraph of every spec reads as "this is unfinished."

This change closes all eight gaps. The expected net effect is:
`pip-audit` clean in both build and test jobs, every public remote-
interface code path tested, every spec file complete, and the
governance surface aligned with the rest of the published product.

## What Changes
- Replace `is_loopback` set-membership with `ipaddress.ip_address(host).is_loopback`
  in `metawarc/settings.py` so all IPv4 and IPv6 loopback representations
  are recognized and `ValueError` (invalid host strings) is handled
  cleanly
- Add REST authentication tests via `TestClient`: missing token,
  invalid token, valid token, and the loopback-vs-non-loopback bind
  guard
- Mirror the per-module coverage gate for `metawarc.cmds.server`,
  `metawarc.cmds.dump`, and `metawarc.mcp_server` at 70 % (the same
  floor already applied to `metawarc.cmds.indexer`)
- Add a Windows runner (`windows-latest` / Python 3.13) to the CI
  matrix and add `pip-audit` to the `test` job after the editable
  install
- Add a `tests/test_module_entry.py` smoke test that runs
  `python -m metawarc --version` in a subprocess and asserts exit 0
- Add `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1) and `SUPPORT.md`
  to the repository root; reference them from the README and from the
  Docusaurus docs site
- Write a 1–3 sentence Purpose paragraph for each of the 12 spec
  files that still carry the `TBD` placeholder
- No public CLI, API, or MCP behavior changes

## Impact
- Affected specs: `remote-interfaces`, `test-assurance`, `build-system`,
  `documentation-quality`
- Affected code: `metawarc/settings.py`, `metawarc/cmds/server.py`
  (tests only), `tests/test_interfaces_cli.py` (new cases),
  `tests/test_module_entry.py` (new), `.github/workflows/ci.yml`,
  repository root (`CODE_OF_CONDUCT.md`, `SUPPORT.md`), all
  `openspec/specs/*/spec.md` files (Purpose paragraph only)
- Dependencies: `ship-2.0.2-and-cleanup` (so the wheel/sdist reflects
  the post-merge CVE fix closure)