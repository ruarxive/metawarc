## Context
The 2026-09-17 review (`PRODUCT_REVIEW_AND_IMPROVEMENT_PLAN.md`) closed the
P0–P2 findings from the 2026-08-04 review and identified four maintainability
watchlist items. The current 2026-10-06 review (this document's companion)
finds that the security boundary, the test depth on public surfaces, the
CI matrix, and the OpenSpec hygiene still have concrete, evidence-backed
gaps that can be closed without changing user-visible behavior.

The `is_loopback` helper at `metawarc/settings.py:58` uses set membership on
`{"127.0.0.1", "::1", "localhost"}`. The IPv6 long-form
`0:0:0:0:0:0:0:1` is a different string from `::1` and would be rejected
as "non-loopback" by the current implementation, prompting a non-loopback
bind that requires authentication or `--allow-insecure`. A user setting
`METAWARC_HOST=0:0:0:0:0:0:0:1` (a perfectly valid IPv6 loopback)
would therefore be told their loopback bind is insecure.

The REST server's authentication branch (`metawarc/cmds/server.py` line 48,
plus the assertion at lines 85–97 and the dispatch at line 121–123) sits on
the security boundary. Module coverage is 90 % but the authentication code
itself is exercised only by its absence. A future refactor of the bearer
middleware could silently break authentication and CI would stay green.

The CI matrix in `.github/workflows/ci.yml` has three entries: Ubuntu
3.10, Ubuntu 3.13, and macOS 3.13. DuckDB and WARC paths behave
identically across POSIX systems but Windows differs in path separators,
drive letters, line endings, and temp-dir conventions. Without a
Windows runner, a Windows-only regression is caught only by a Windows
contributor running `pytest` after a failure.

`pip-audit` is currently invoked only in the `package` job, against the
built wheel's transitive closure. The `test` job installs the package
through `pip install -e '.[all,dev]'`, which resolves the editable source's
dependencies. The two jobs therefore audit different dependency closures,
and a contributor's local install can diverge from CI.

`metawarc/__main__.py` is six lines (`from .core import cli` /
`if __name__ == "__main__": cli(...)`) and is reported as 0 % covered.
The CI run that produces the coverage report executes `metawarc` through
the `metawarc.core:cli` entry point, never through `python -m metawarc`.

The repository ships `CONTRIBUTING.md` and `SECURITY.md` but not
`CODE_OF_CONDUCT.md` or `SUPPORT.md`. Comparable projects with published
docs sites and a public REST/MCP surface normally ship all four.

Twelve of thirteen OpenSpec spec files still carry the placeholder line
`TBD - created by archiving change …. Update Purpose after archive.`
The placeholder is the first paragraph a new contributor reads when
inspecting a capability, and it reads as "this spec is unfinished."
The archived change files reference the spec changes by capability name,
so writing the Purpose paragraphs is straightforward.

## Goals / Non-Goals

- Goals:
  - close the loopback-bypass vector in `is_loopback`;
  - add tests for every REST authentication branch so the security
    surface is covered by an automated assertion;
  - extend the per-module coverage gate to every public remote-surface
    module;
  - add Windows to the CI matrix;
  - run `pip-audit` in the contributor-path CI job;
  - cover the `python -m metawarc` entry point with an automated test;
  - add the missing governance files;
  - finalize the OpenSpec Purpose paragraphs.
- Non-Goals:
  - any change to user-visible CLI, REST, or MCP behavior;
  - replacing the `httpx2` Pin (this is handled by
    `ship-2.0.2-and-cleanup`);
  - bumping the supported Python floor or ceiling;
  - introducing a new authorization model (a static bearer token remains
    sufficient for the supported deployment model per
    `openspec/specs/remote-interfaces/spec.md`).

## Decisions

### Decision: Use `ipaddress.ip_address(...).is_loopback`

The Python standard library's `ipaddress` module already handles all
canonical IPv4 and IPv6 representations, including compressed and
long-form. Using `ipaddress.ip_address(host).is_loopback` (with a
`try/except ValueError` for invalid strings) is shorter, more correct,
and removes the maintenance burden of enumerating representations.

### Decision: Use `fastapi.testclient.TestClient`

The existing `tests/test_interfaces_cli.py` exercises HTTP behavior via
`subprocess` and `curl`-like patterns. Using `TestClient` (the
fastapi-recommended in-process client) gives synchronous control of
headers and bodies and avoids port collisions in parallel CI runs. The
`httpx>=0.27` switch from `ship-2.0.2-and-cleanup` is the dependency
that makes `TestClient` work in tests; the swap is therefore a
prerequisite of this change.

### Decision: Mirror the indexer gate, don't add a separate "matrix" gate

The existing gate structure (`pytest … --cov=metawarc.cmds.indexer
--cov-fail-under=70`) is the established pattern. Replicating it three
times is consistent and avoids introducing a new gate shape.

### Decision: Place Windows runner in the same matrix, not a separate job

A separate Windows job would duplicate every other step and slow CI. A
matrix entry adds the runner without code duplication; the existing
`actions/setup-python@v7` and `pip install` steps work on Windows
without modification.

### Decision: Run `pip-audit` after the editable install

The `pip-audit` step in the `test` job runs against the same install
the developer would run locally (`pip install -e '.[all,dev]'`).
Catching a CVE at this point prevents a contributor from running tests
against a vulnerable closure.

### Decision: Adopt Contributor Covenant 2.1 verbatim

The project has one Committer listed in `AUTHORS.md`. The Contributor
Covenant 2.1 is the industry standard, has an established enforcement
process, and can be referenced verbatim without customization.

## Risks / Trade-offs

- `ipaddress` may reject strings that the current set-membership
  implementation accepts (e.g. `127.0.0.1:8000` carries a port suffix).
  Mitigation: the call site validates port presence separately; the
  `ipaddress` call only handles the host portion.
- The Windows runner adds CI minutes. Mitigation: the matrix entry runs
  the same suite; the marginal cost is the Windows boot time, which is
  acceptable for the path-separator regression value.
- Per-module gates that mirror the indexer gate can fail loudly. That
  is the intent: a regression on a public surface should break CI.
- The 13 spec Purpose paragraphs are prose-only. They are
  documentation-quality changes and are scoped to this change so they
  are not lost across future changes.

## Migration Plan

1. Land the `ship-2.0.2-and-cleanup` change first (or in parallel)
   so the `httpx` switch is in place.
3. Land this change through a single PR on `master`.
4. Verify the CI matrix on all four runners before merging.
5. Confirm `openspec validate --strict` passes after the Purpose
   rewrites.

## Open Questions

- Should the Windows runner use Python 3.12 or 3.13? Recommendation:
  3.13, matching the macOS runner, to minimize matrix variance.
- Should `SUPPORT.md` reference GitHub Discussions specifically, or
  leave the channel open? Recommendation: name Discussions for
  general help and Security Advisories for vulnerabilities, matching
  the policy in `SECURITY.md`.
- Should `pip-audit` fail the `test` job on any severity or only on
  the configured severity policy? Recommendation: fail on any known
  CVE in the direct dependency closure; fail on `urllib3`/`pyjwt`
  transitive CVEs only when the closure contains a non-vulnerable
  version.