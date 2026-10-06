## 1. Loopback Recognition
- [ ] 1.1 Replace the `is_loopback` set-membership in
      `metawarc/settings.py:58` with `ipaddress.ip_address(host).is_loopback`
- [ ] 1.2 Wrap the call site in `metawarc/core.py` so that an invalid
      host string raises a `click.UsageError` with the same actionable
      message used for non-loopback binds
- [ ] 1.3 Add unit tests covering `127.0.0.1`, `::1`,
      `0:0:0:0:0:0:0:1`, `localhost`, `0.0.0.0`, and the empty string

## 2. REST Authentication Tests
- [ ] 2.1 Add `tests/test_server_auth.py` exercising the bearer-token
      paths in `metawarc/cmds/server.py`:
      - `serve` started with `--token` returns 401 on missing/invalid
        `Authorization` header
      - `serve` started with `--token` returns 200 on the documented
        authenticated endpoint
      - `serve` started without `--token` on a loopback bind accepts
        unauthenticated requests
      - `serve` started without `--token` on `0.0.0.0` fails with the
        actionable security message
- [ ] 2.2 Verify coverage of `metawarc/cmds/server.py` rises from 90 %
      to at least 95 % and that the new gate at 70 % does not regress

## 3. Per-Module Coverage Gates
- [ ] 3.1 In `.github/workflows/ci.yml`, add a fourth pytest invocation
      that runs the full suite with `--cov=metawarc.cmds.dump
      --cov-fail-under=70`
- [ ] 3.2 Add a fifth invocation with `--cov=metawarc.mcp_server
      --cov-fail-under=70`
- [ ] 3.3 Add a sixth invocation with `--cov=metawarc.cmds.server
      --cov-fail-under=70`
- [ ] 3.4 Confirm the existing `--cov=metawarc.cmds.indexer
      --cov-fail-under=70` step (currently the second pytest run) still
      passes after the additions

## 4. CI Matrix and Audit
- [ ] 4.1 Add a `windows-latest` / Python 3.13 entry to the
      `.github/workflows/ci.yml` test strategy matrix
- [ ] 4.2 Add `pip-audit` to the `test` job, run after the editable
      install step and before the existing `pytest` step
- [ ] 4.3 Add a `pip-audit --strict` failure annotation so that any
      known CVE in the dev install fails the PR

## 5. Module Entry Test
- [ ] 5.1 Create `tests/test_module_entry.py` with one test that runs
      `[sys.executable, "-m", "metawarc", "--version"]` in a subprocess
      and asserts exit 0 and `2.0.2` (or the current version) in stdout
- [ ] 5.2 Add a second test that runs
      `[sys.executable, "-m", "metawarc", "--help"]` and asserts exit 0
      and the documented `--version` mention
- [ ] 5.3 Confirm `metawarc/__main__.py` coverage rises from 0 % to 100 %

## 6. Governance Files
- [ ] 6.1 Add `CODE_OF_CONDUCT.md` based on the Contributor Covenant
      2.1; reference the maintainer email from `pyproject.toml`
- [ ] 6.2 Add `SUPPORT.md` pointing to GitHub Discussions and Security
      Advisories as documented support channels
- [ ] 6.3 Link both files from `README.md` and from
      `docs/docs/development/contributing.md`

## 7. OpenSpec Purpose Finalization
- [ ] 7.1 Write a 1–3 sentence Purpose paragraph for each of:
      `archive-indexing`, `cli-progress`, `collection-analysis`,
      `documentation-quality`, `incremental-ingestion`,
      `index-workspace`, `metadata-extraction`, `payload-export`,
      `record-query`, `release-engineering`, `remote-interfaces`,
      `test-assurance`, `website-replay` (13 spec files; the report
      references 12, but the build-system spec also carries the TBD
      line)
- [ ] 7.2 Confirm `openspec validate --strict` still passes after the
      Purpose rewrites

## 8. Verification
- [ ] 8.1 `pip-audit` reports zero findings in both the `test` job
      (after install) and the `package` job (after build)
- [ ] 8.2 The full test matrix (Ubuntu 3.10, Ubuntu 3.13, macOS 3.13,
      Windows 3.13) is green
- [ ] 8.3 All four per-module coverage gates pass:
      `metawarc.cmds.indexer`, `metawarc.cmds.server`,
      `metawarc.cmds.dump`, `metawarc.mcp_server` all ≥ 70 %
- [ ] 8.4 Overall coverage holds at 87 % (gate 75 %)
- [ ] 8.5 `openspec validate --strict` reports a clean tree
- [ ] 8.6 `pytest -q` reports at least 92 tests passing (87 baseline
      plus 5 new in §2 and §5)