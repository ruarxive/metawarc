## 1. Repository Consolidation
- [x] 1.1 Create a reviewed integration branch from `testing`/`v1.3.1` (completed through the reviewed `master` consolidation that shipped 2.0; `testing` history is preserved in the merged lineage)
- [x] 1.2 Reconcile changes made independently on `master`
- [x] 1.3 Exclude generated, ignored, and user workspace artifacts from the change
- [x] 1.4 Select and document the canonical default branch and repository URL

## 2. Build Metadata
- [x] 2.1 Make `pyproject.toml` the authoritative package configuration
- [x] 2.2 Align version, license, Python classifiers, URLs, and console entry point
- [x] 2.3 Define `api`, `mcp`, `all`, and `dev` optional dependency groups
- [x] 2.4 Remove duplicate or contradictory requirements and setup metadata
- [x] 2.5 Confirm package templates and other runtime data are included

## 3. Compatibility and Documentation
- [x] 3.1 Document behavior for existing 1.2 and 1.3 index layouts
- [x] 3.2 Align README feature claims with the consolidated implementation
- [x] 3.3 Align changelog, version module, tag policy, and release instructions
- [x] 3.4 Document installation of core, API, MCP, and development variants

## 4. Verification
- [x] 4.1 Build wheel and source distribution from a clean checkout (verified 2026-09-18 via `git archive HEAD` export; sdist and wheel built successfully, and CI builds from clean checkouts on every push)
- [x] 4.2 Install every extras combination in isolated environments
- [x] 4.3 Run `metawarc --version`, CLI help, and a minimal index/query smoke test
- [x] 4.4 Run API and MCP startup smoke tests with their respective extras
- [x] 4.5 Confirm release artifacts report the same version and source commit
