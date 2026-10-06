## 1. Release v2.0.2
- [ ] 1.1 Confirm `b272283` is green on all CI matrix entries (Ubuntu 3.10,
      Ubuntu 3.13, macOS 3.13)
- [ ] 1.2 Run `python -m build` locally; verify wheel and sdist appear under
      `dist/metawarc-2.0.2-*`
- [ ] 1.3 In clean `venv`s, install `metawarc-2.0.2-py3-none-any.whl` for
      each of `core`, `api`, `mcp`, `all` extras and smoke-test
      `metawarc --version` plus `.github/scripts/installed_smoke.py`
- [ ] 1.4 Create annotated tag `v2.0.2` at `b272283` referencing the
      changelog commit (`8ed99f5 chore: prepare 2.0.2 and clean dependency
      hygiene`); push the tag
- [ ] 1.5 Publish the wheel/sdist to PyPI from the same commit; attach the
      artifacts to the GitHub `v2.0.2` release with the changelog excerpt
- [ ] 1.6 Replace the stale `dist/metawarc-2.0.1-*` files in the working
      tree with the freshly built `dist/metawarc-2.0.2-*` files

## 2. Clear Transitive CVE Debt
- [ ] 2.1 Merge Dependabot PR #34 (`pyjwt` 2.13.0 → 2.15.0) and PR #35
      (`urllib3` 2.7.0 → 2.8.0)
- [ ] 2.2 Run `pip-audit` in the dev install; confirm zero findings in the
      runtime dependency closure
- [ ] 2.3 Re-run CI to confirm the bumps do not regress the package
      install/smoke job

## 3. Repository Branch Hygiene
- [ ] 3.1 Confirm no other branch or tag in the network contains
      `94db570` (the `v2` orphan tip); record the result in this change
- [ ] 3.2 Delete `origin/v2` (or rename to `archive/pre-2.0-line` if any
      fork depends on it); record the chosen action
- [ ] 3.3 Confirm `git branch -r` no longer surfaces an unlabeled `v2`
      branch on first-time clone

## 4. Working-Tree Hygiene
- [x] 4.1 Add a `.coverage` entry to the root `.gitignore` (the
      `coverage-tooling` block already lists `.coverage.*`) — already
      satisfied; `.gitignore:44` lists `.coverage` directly and
      `.gitignore:45` lists `.coverage.*`
- [x] 4.2 Replace `httpx2>=2.12` with `httpx>=0.27` in `pyproject.toml`
      `[project.optional-dependencies].dev` — reverted; starlette 1.x
      does `import httpx2 as httpx` internally in
      `starlette/testclient.py`, so the dev extra must keep providing
      httpx2. The `>=2.12` pin keeps the closure off the vulnerable
      2.9.1 release; the explanatory comment is updated to clarify
      the dependency relationship
- [x] 4.3 Re-run `pip-audit` and `pytest` — verified; `httpx2 2.13.1`
      is the current resolved pin, `pip-audit` reports zero httpx2
      findings, `pytest` reports 87 passing tests

## 5. Verification
- [ ] 5.1 `git describe --tags` reports `v2.0.2-0-gb272283` (or whatever
      commit the tag is created at)
- [ ] 5.2 `pip-audit` reports zero known vulnerabilities in the dev
      install
- [ ] 5.3 All four extras (`core`, `api`, `mcp`, `all`) install cleanly
      from the new tag's wheel and pass the smoke harness
- [ ] 5.4 `pytest` reports the same 87 passing tests as the pre-change
      baseline
- [ ] 5.5 `ruff check .` and `mypy metawarc` remain clean