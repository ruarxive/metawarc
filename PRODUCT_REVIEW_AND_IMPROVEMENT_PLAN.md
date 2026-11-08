# Metawarc Product Review and Improvement Plan

**Review date:** 2026-11-05
**Scope:** `master` at `74a8a0b` (`v2.0.3-5-g74a8a0b`)
**Product version:** 2.0.3
**Companion documents:** `REPOSITORY_REVIEW_AND_IMPROVEMENT_PLAN.md` (historical), `openspec/roadmap.md`, and the 15 current capability specs

## 1. Executive summary

Metawarc has a broad and coherent 2.x product: versioned DuckDB/Parquet workspaces, stable archive identities, incremental ingestion, bounded metadata and text extraction, typed query/export services, collection analysis, local website replay, and CLI, REST, and MCP interfaces. The architectural constraints that matter for preservation work remain visible in the implementation: immutable WARC sources, atomic sidecar publication, allowlisted queries, bounded output, and loopback-first network services.

The baseline engineering checks are strong. This review ran 206 tests successfully with 88% branch coverage; Ruff, formatting, mypy, package builds, documentation builds, `pip check`, and strict validation of all 15 OpenSpec specifications also passed. The core runtime requirements resolved by `requirements.txt` produced no known pip-audit findings.

The current checkout is nevertheless **not ready for an immediate 2.0.4 release**. The newest user-facing workflows contain verified contract failures:

1. Batch exports above 1,000 rows fail even though the CLI, REST API, and documentation advertise up to 100,000 rows and repeatedly demonstrate 50,000-row exports.
2. The batch runner uses the 30-second request timeout instead of the configured 300-second job timeout. Standalone CLI cancellation returns success but leaves the job `pending`.
3. Search can return a snippet that does not contain the match, treats `%` and `_` as wildcards rather than phrase characters, and reports the number of returned rows as `total`.
4. The full optional/development environment has 35 known vulnerability findings across 10 installed packages, and `uv.lock` is stale. The core-only requirements audit is clean; the principal exposure is in the optional MCP and contributor dependency closure.
5. Current guides and specs repeat nonexistent options, incorrect command names, unsupported filters, and unverified performance claims. A successful Docusaurus build does not detect these semantic errors.

**Recommended direction:** make 2.0.4 a stabilization release. Fix and prove the batch and search contracts, restore dependency/lockfile gates, align current specs and guides, then resume product expansion. The highest-value new feature remains a read-only collection exploration dashboard, preceded by filtered and reproducible search.

## 2. Review method and evidence

The review covered the README, changelog, current OpenSpec baseline, implementation, tests, CI, packaging metadata, and user guides. In addition to the standard gates, focused disposable probes exercised the exact boundary conditions below; probe files and temporary workspaces were removed afterward.

| Check | Observed result |
|---|---|
| `pytest --cov=metawarc --cov-report=term` | **206 passed**; 4,462 statements; **88% branch coverage** against a 75% gate |
| Ruff lint and format | Clean; 224 files already formatted |
| `mypy metawarc` | Clean; 32 source files |
| `pip check` | No broken requirements |
| `pip-audit` on the installed all/dev environment | **35 findings in 10 packages**, including Authlib, FastMCP, MCP, certifi, filelock, and joserfc |
| `pip-audit -r requirements.txt` | **No known vulnerabilities** in the resolved core requirement set |
| `uv lock --check` | Failed: the lockfile needs to be updated |
| `python -m build` | Source and wheel distributions built successfully |
| `npm run build` in `docs/` | Documentation built successfully |
| `openspec validate --all --strict` | **15 specs passed**, 0 failed |
| Focused export probe with `limit=1001` | `QueryValidationError: limit must be between 1 and 1000` |
| Focused CLI cancellation probe | Exit 0; returned and persisted status both remained `pending` |
| Focused job-timeout probe | `job_timeout_seconds=300`, but runner timeout was 30 seconds |
| Focused late-match search probe | Match returned, but its snippet did not contain `needle` |
| Focused literal `%` search probe | Matched both text rows instead of performing a literal phrase match |
| Release state | Five commits after `v2.0.3`; working tree was clean before this report update |

No large-corpus benchmark was run. Existing performance claims for multi-million-record search are therefore treated as unverified, not as established product facts.

## 3. Feature inventory and product assessment

| Product area | Current surface | Assessment |
|---|---|---|
| Archive indexing | `index` with add/update/rescan/force modes; stable archive IDs; compressed and uncompressed WARC support | **Strong foundation.** Batched Parquet writes, checkpoints, atomic publication, and bounded-memory tests support the preservation workflow. |
| Incremental ingestion | `ingest`, `catalog`, `rebind`, `cleanup` | **Strong.** Explicit move/rebind behavior avoids guessing archive identity. Keep regression coverage for interrupted and moved sources. |
| Diagnostics and recovery | `doctor`, dry-run/apply repair, staging cleanup | **Valuable and appropriately non-destructive.** Recovery behavior should remain a required end-to-end gate as new sidecar kinds appear. |
| Record query | `list-files`, `stats`, `get`; typed `QueryService` | **Sound design.** Filters and sort fields are allowlisted, values are parameterized, and raw SQL is isolated behind the local `--unsafe-where` flag. |
| Payload export | `dump`, `dump-metadata`; JSONL manifests and SHA-256 | **Strong synchronous path.** Filename sanitization, overwrite avoidance, byte limits, and 94% module coverage are appropriate for user-data protection. |
| Metadata extraction | `index-content --type ...`; PDF, OOXML/OLE, links, images, video, audio, fonts | **Broad and well structured.** The per-format extractor split is an improvement. Continue testing hostile inputs and extraction limits rather than adding formats indiscriminately. |
| Collection analysis | Summary, stored metadata, hashes, duplicates, links, integrity | **Research-ready.** Stored-metadata analysis avoids unnecessary payload reads. The 1,415-line `analysis.py` remains a maintainability hotspot, not an immediate rewrite target. |
| Text extraction and search | HTML, PDF, and OOXML Word-document text projection; `search`; REST and MCP search | **Useful MVP, but contract defects block promotion.** It is a bounded substring scan, not ranked FTS. Correct snippets, literal matching, result semantics, and docs come before scaling work. |
| Website replay | `serve`/`replay`, rewritten and identity modes, CDXJ export | **Well scoped.** Charset-aware HTML/CSS rewriting and explicit JavaScript limitations are honest. Full JS replay should remain delegated to pywb interoperability. |
| REST API | Typed records, headers, payloads, search, replay, and jobs | **Good security defaults; incomplete job semantics.** Token discipline and trace IDs are present. Search should open the workspace read-only like the other read paths. |
| MCP | Seven read-only tools for archives, records, headers, search, stats, and metadata summaries | **Good least-privilege surface and 100% module coverage.** Search currently opens a writable connection despite the read-only contract; fix this without expanding the tool inventory. |
| Batch jobs | Durable JSON state; CLI and REST lifecycle; JSON/CSV/Parquet record exports | **Not dependable at its advertised scale.** Large-export, timeout, cancellation, streaming, restart, and result-delivery behavior need a corrective change before adding job kinds. |
| Documentation | Docusaurus site, command reference, cookbook, architecture, use cases | **Extensive but semantically stale in the newest sections.** Add executable example tests and keep current specs aligned with actual command names and limits. |

### Product gaps worth retaining on the roadmap

- Filtered, paginated, reproducible text search with match-centered snippets and honest total counts.
- A read-only collection exploration dashboard for hosts, MIME types, timelines, archives, and search, distinct from website replay.
- Operationally mature batch jobs: progress, retention, downloadable results, and eventually payload-export or analysis job kinds.
- Automatic freshness/invalidation reporting for derived text and metadata sidecars after archives change.

These are secondary to the correctness and security findings below.

## 4. Prioritized findings

### P0 — Release blockers

#### P0.1 Large batch exports cannot perform the advertised workflow

`EXPORT_HARD_LIMIT` is 100,000 (`metawarc/jobs.py:46`), but `run_export_records` passes the requested limit to `QueryService.list_records` (`metawarc/jobs.py:375-379`). The synchronous query validator caps that path at 1,000 (`metawarc/query.py:14`, `metawarc/query.py:143-144`). A focused probe with `limit=1001` failed exactly at this boundary.

The README, quick start, performance guide, batch-job guide, and querying guide all advertise 50,000-row jobs. The README also adds an unsupported `--output-format` option to `jobs submit` (`README.md:158`).

**Required outcome:** one bounded streaming export implementation supports every documented format and the full 1–100,000 range without routing a bulk export through the synchronous page validator.

#### P0.2 Job timeout and cancellation contracts are not implemented reliably

- `ServerSettings` defines `job_timeout_seconds=300`, but `JobRunner` reads `request_timeout_seconds` (`metawarc/settings.py:40-43`, `metawarc/jobs.py:213`). The API lifespan log reports the same wrong timeout (`metawarc/api_server.py:57-60`).
- `metawarc jobs cancel` constructs a new in-memory runner. It has no access to the server runner's task or cancellation set (`metawarc/cli_jobs.py:37-41`, `metawarc/jobs.py:261-275`). The probe returned exit 0 and left the persisted job `pending`.
- `run_export_records` is declared async but performs blocking DuckDB, filesystem, CSV, and Parquet work without an await (`metawarc/jobs.py:354-403`). This blocks the event loop and prevents `asyncio.wait_for` from interrupting the work at the requested deadline.
- Results are written directly to their final paths rather than staged and atomically published. Cancellation or failure can therefore conflict with the guide's claim that partial results do not appear (`docs/docs/use-cases/batch-jobs.md:129-132`).
- Startup resumes only jobs returned by `store.list()` with its default limit of 50 (`metawarc/jobs.py:225-230`). There is no persisted cross-process claim for pending jobs, so the comment that another server can claim work is not an actual coordination protocol.

**Required outcome:** a single persisted lifecycle is honored by CLI and REST callers; blocking work runs off the event loop; timeout/cancellation stops or safely rolls back work; results publish atomically; restart behavior is explicit and tested.

#### P0.3 The audited optional/development dependency closure is vulnerable and the lock is stale

The installed all/dev environment reported 35 known findings across 10 packages. Directly relevant examples include FastMCP 3.4.5, MCP 1.29.0, Authlib 1.7.2, certifi 2026.7.22, and joserfc 1.7.4; the audit supplied patched versions for each. `uv lock --check` also failed.

The audited checkout fails the same contributor-path `pip-audit` command used by CI. CI installs with pip rather than `uv.lock`, so a fresh CI resolution may differ from this environment; reproducible local and CI audit evidence is currently missing. The package job audits its build-tool environment, not each freshly installed wheel extra. The clean core-only audit is good news, but it does not clear the MCP or contributor surfaces.

**Required outcome:** regenerate and commit a fresh lock with patched compatible versions, apply secure floors to direct dependencies where appropriate, and audit clean installations of core, API, MCP, all, and dev closures.

#### P0.4 Primary documentation currently teaches failing commands

This is not just editorial polish: the quick start's featured batch workflow fails, and the search guide shows an unsupported `search --archive-ids` option (`docs/docs/use-cases/index-and-search.md:61`). Other material mismatches include:

- `index` is described as building the text sidecar and as the only command that opens WARCs, although `index-content --text` does both text extraction and WARC reading (`docs/docs/use-cases/index-and-search.md:7-10`, `:64-67`, `:97-100`).
- Search results are described as catalog-joined and filterable, but `search_text` only scans `texts` Parquet files (`metawarc/workspace.py:1084-1096`).
- Multi-million-record searches are claimed to take seconds without a reproducible benchmark (`docs/docs/use-cases/index-and-search.md:64-67`).
- The docs use `METAWARC_REQUEST_TIMEOUT_SECONDS`; the implemented variable is `METAWARC_REQUEST_TIMEOUT` (`metawarc/settings.py:56`).
- Current specs repeatedly say `content-index`, while the executable command is `index-content` (`openspec/specs/metadata-extraction/spec.md`, `openspec/specs/index-workspace/spec.md`).
- The batch spec says the result route streams a file and uses request timeout/concurrency settings; the API returns metadata with a local path, and the docs describe that metadata contract (`openspec/specs/remote-batch-job/spec.md:111-121`, `metawarc/api_server.py:380-410`).

**Required outcome:** all featured workflows execute successfully against a built artifact, and current specs, CLI help, guides, and API contracts tell the same story.

### P1 — Correctness and assurance gaps

#### P1.1 Search results violate basic phrase-search expectations

- Snippets always use `substring(text, 1, 256)` (`metawarc/workspace.py:1089-1095`). A match later in the document is guaranteed to disappear from the returned snippet, contradicting the record-query spec (`openspec/specs/record-query/spec.md:81-85`).
- Wrapping user input in `ILIKE '%...%'` without escaping means `%` and `_` change match semantics. The probe confirmed that `%` returned every row.
- There is no `ORDER BY`, so a limited result set is not deterministic.
- REST and MCP return `total=len(rows)`, which is the returned hit count, not the total number of matches (`metawarc/api_server.py:306-319`, `metawarc/mcp_server.py:102-104`).
- Both remote search adapters use `read_only=False`, unlike their other read paths (`metawarc/api_server.py:299-303`, `metawarc/mcp_server.py:102`).
- `Workspace.search_text` reads process-global environment settings rather than receiving the owning app's validated configuration (`metawarc/workspace.py:1081`). API parameter bounds are also initialized from `ServerSettings.from_env()` instead of the passed `config` (`metawarc/api_server.py:294-297`).

**Required outcome:** literal phrase semantics, match-centered snippets, deterministic results, truthful count fields, read-only connections, and explicit configuration injection, all covered by boundary tests.

#### P1.2 Tests measure coverage but sometimes permit the defects they should catch

Examples:

- The running-job cancellation test accepts `cancelled`, `succeeded`, or `failed` (`tests/test_jobs.py:218-224`).
- The CLI wait-timeout test accepts either 0 or 124 (`tests/test_cli_jobs.py:96-111`).
- CLI submission is tested as creating a job, but standalone cancellation of that pending job is not asserted (`tests/test_cli_jobs.py:42-57`).
- Job tests use limits of 1–10, leaving the advertised 50,000-row path untested.
- Search tests only assert a snippet when the phrase is already near the beginning (`tests/test_workspace_search.py:37-74`).
- The test-assurance spec still references removed `metawarc.cmds.*` paths and claims interface limits/resource behavior that the weak assertions do not prove (`openspec/specs/test-assurance/spec.md:76-81`, `:102-111`).

**Required outcome:** strict state assertions, boundary tests at 1,000/1,001/100,000, real cancellation and restart tests, late-match/wildcard search cases, and executable documentation scenarios. Coverage should remain a floor, not substitute for contract assertions.

#### P1.3 Result delivery is not remote-ready

`GET /jobs/{id}/result` exposes a server-local path and metadata but no authenticated way to download the bytes. This is consistent with the current guide but not the current spec or a remote client workflow.

**Recommended contract:** keep `/result` for non-sensitive metadata, add an authenticated `/result/content` streaming route, replace the absolute local path in public responses with a download URL, and confine resolved files to the owning job directory. If a different contract is chosen, version and document it explicitly.

### P2 — Product depth and operational maturity

#### P2.1 Search needs an evidence-based scalability and relevance step

The current implementation scans active Parquet files for each query and has no archive/MIME/host/date/language filters, offset/cursor, ranking, or reproducible total. These are acceptable MVP constraints only when documented accurately.

Do not choose a new FTS backend solely to match a roadmap label. First publish a representative corpus benchmark for scan latency, memory, index-build time, sidecar size, and update freshness. Then compare the current scan with a maintained DuckDB FTS path or another local index under the workspace's atomic-publication and portability constraints.

#### P2.2 Batch operations need retention and observability before more job kinds

Durable export progress, safe terminal-job retention, and retained-job operational metrics are now implemented. Metrics provide bounded lifecycle counts and queue/execution observations without claiming all-time history after pruning. Payload export, integrity analysis, and metadata reports should each have a separate OpenSpec proposal; persistent telemetry, rates, percentiles, and ETA remain out of scope.

#### P2.3 The exploration dashboard remains the highest-visibility new capability

A read-only dashboard would make the existing catalog, statistics, and search useful to non-CLI users without taking on full replay complexity. It should reuse the existing authenticated server and typed services, provide archive/host/MIME/timeline exploration, link to replay where appropriate, and never expose raw SQL or arbitrary paths.

### P3 — Maintainability and release hygiene

- `analysis.py` (1,415 lines), `core.py` (1,106), `workspace.py` (1,106), and `extractor/indexer.py` (814) remain complexity centers. Split search/query configuration and batch export services when correcting them; avoid a broad rewrite unrelated to observed defects.
- `reporting.py` has 49% coverage. Add direct rendering tests for catalog, ingest, table, and JSON output rather than raising the global percentage with unrelated tests.
- `MANIFEST.in` still prunes deleted `metawarc/base` and `metawarc/data` directories, producing build warnings. Remove stale rules.
- Python 3.14 is absent from the classifiers and CI matrix. Evaluate compatibility and add it only after dependencies pass; do not claim support by metadata alone.
- Five commits are already unreleased after `v2.0.3`, including Windows typing and Click compatibility fixes. Include them in the eventual 2.0.4 changelog and release evidence.

## 5. Improvement plan

### Phase 0 — Restore release and documentation gates (1–2 days)

- [x] **0.1 Add regression tests first** for export limits 1,000/1,001, configured job timeout, standalone CLI cancellation, late-match snippets, literal `%`/`_`, deterministic search ordering, and truthful totals.
- [ ] **0.2 Refresh dependencies and `uv.lock`.** Use versions that resolve the audit findings while retaining Python 3.11–3.14 compatibility; Python 3.10 is excluded after reaching EOL and losing patched dependency releases. Re-run the full test matrix and MCP smoke tests. Dependencies, lockfile, local tests, and MCP smoke checks are complete; the supported OS/Python CI matrix remains pending.
- [x] **0.3 Audit isolated install closures** for core, API, MCP, all, and dev. Keep the core audit clean and block release on unapproved findings in any supported closure.
- [x] **0.4 Stop documentation from promising broken behavior.** Until code fixes land, remove or correct the 50,000-row and unsupported-option examples, state that CLI-submitted jobs require a running server, and remove the unsupported search-filter and multi-million-performance claims.
- [x] **0.5 Correct current specs and command references** (`index-content`, actual environment variables, current module paths, job defaults). Do not rewrite archived proposals merely to hide historical mistakes.

**Phase exit criteria:** `uv lock --check` passes; supported dependency audits are clean or have explicit reviewed exceptions; no primary guide contains a known-failing command; all new regression tests fail for the intended pre-fix reason.

### Phase 1 — Make batch exports correct and durable (3–5 days)

- [x] **1.1 Implement streaming record export** using the iterator/export path rather than `list_records`; stream JSON, CSV, and Parquet in bounded batches and enforce `EXPORT_HARD_LIMIT` independently of synchronous page size.
- [x] **1.2 Validate submissions eagerly** with a typed filter model shared by CLI and REST. Unknown filters, invalid ranges, and unsupported formats must fail at submission rather than becoming opaque background failures.
- [x] **1.3 Honor `job_timeout_seconds`** and use `job_max_concurrent` consistently in settings, logs, runner behavior, docs, and specs.
- [x] **1.4 Move blocking work off the event loop** and add cooperative cancellation at bounded batch boundaries. If hard interruption cannot be guaranteed, document the precise bound and choose a worker design that can enforce it.
- [x] **1.5 Persist cancellation requests** so CLI and REST affect the same job. Prevent a completing worker from overwriting a terminal cancellation with `succeeded`.
- [x] **1.6 Publish results atomically** from temporary files and remove incomplete artifacts after failure/cancellation.
- [x] **1.7 Define restart and multi-process behavior.** Resume every eligible pending job, explicitly requeue or fail interrupted running jobs, and prevent two runners from executing the same job concurrently.
- [x] **1.8 Provide authenticated result download** and remove server-local paths from the public remote contract.

**Phase exit criteria:** a built wheel completes a 50,000-row export in every documented format; a request above 100,000 fails immediately; configured timeout is observed; CLI and REST cancellation reach `cancelled`; no partial result becomes visible; restart and concurrent-runner tests pass; API clients can download results without filesystem access.

### Phase 2 — Correct search and make the contract executable (2–3 days)

- [x] **2.1 Implement literal phrase matching** by escaping LIKE metacharacters or using a literal contains operation.
- [x] **2.2 Return match-centered snippets** with deterministic context and tests for matches at the start, middle, end, and beyond character 256.
- [x] **2.3 Add deterministic ordering** and make `total`, `returned`, and `limit` semantics explicit. Compute a real total or rename the field through a versioned API change.
- [x] **2.4 Open remote search workspaces with `read_only=True`** and inject `max_page` from the active server configuration rather than reading global environment defaults inside the workspace method.
- [x] **2.5 Distinguish “text sidecar missing” from “no matches”** with an actionable CLI message and a documented API response.
- [x] **2.6 Align specs and guides** with the implemented snippet, truncation, filtering, and refresh behavior. Test every quick-start and cookbook command against built artifacts. All 27 documented command forms now run in the installed-wheel scenario; CI executes the same coverage check alongside the documentation build.

**Phase exit criteria:** all focused search probes pass; repeated limited searches return the same ordered results; remote adapters never request writable connections; docs no longer claim unsupported filters or unverified scale; all 15 specs and executable examples pass in CI.

### Phase 3 — Deliver the next user-visible capabilities (separate OpenSpec changes)

1. **`update-text-search` — filtered and reproducible search (estimated 3–5 days).**
   - Add archive/MIME/host/date/language filters shared by CLI, REST, and MCP.
   - Add offset or cursor pagination and a documented relevance/order policy.
   - Benchmark a representative corpus before selecting a scan or FTS backend.
   - Publish sidecar freshness and update semantics.
2. **`add-collection-dashboard` — read-only exploration UI (estimated 5–10 days).**
   - Archive, host, MIME, timeline, and search views using typed endpoints.
   - Reuse loopback/token controls and bounded pagination.
   - Link to replay without attempting to replace pywb's JS fidelity.
   - Include accessibility, empty/error states, and installed-artifact browser smoke tests.
3. **`extend-batch-operations` — operations and additional job kinds (estimated 3–5 days per slice).**
   - Retention/deletion, durable progress, authenticated result downloads, and retained-job operational metrics are complete; persistent telemetry, rates, percentiles, and ETA remain out of scope.
   - Payload export or analysis jobs require separate OpenSpec proposals after Phase 1 proves the lifecycle contract.

Do not start these capability proposals until the P0 release blockers are closed.

### Phase 4 — Keep the baseline healthy (continuous)

- [x] Enforce the existing per-public-module coverage policy with current module names and add `jobs`, `cli_jobs`, `workspace` search, and reporting as explicit surfaces.
- [x] Replace permissive assertions with exact lifecycle and exit-code assertions across the suite.
- [x] Add the documentation example runner to CI alongside the existing Docusaurus build.
- [ ] Evaluate Python 3.14 in CI and update metadata only after a clean install/test/audit cycle. Clean wheel installation, dependency audit, and all 298 tests passed on Python 3.14; the classifier and Ubuntu 3.14 CI matrix entry are now added, with remote execution still pending.
- [x] Remove stale manifest rules and refactor large modules only alongside the relevant corrective change.

## 6. Release 2.0.4 gate and success metrics

A 2.0.4 release should not be tagged until all of the following are true:

- [x] The 50,000-row workflow in README and the quick start succeeds from an installed wheel for JSON, CSV, and Parquet.
- [x] Job timeout, cancellation, restart, atomic publication, and result download have strict automated tests and match current specs.
- [x] Search returns literal, deterministic results with match-containing snippets and truthful counts across CLI, REST, and MCP.
- [x] `uv lock --check`, `pip check`, isolated dependency audits, Ruff, mypy, tests/coverage, package builds, documentation builds, and `openspec validate --all --strict` pass.
- [ ] CI proves the supported Python and OS matrix, and every supported wheel extra passes an operational smoke test—not only `--version` or import checks. Operational core/API/MCP/all scenarios pass locally; the supported OS matrix remains pending.
- [x] Documentation contains no known-failing examples and no unsupported performance claims.
- [ ] Changelog, version metadata, signed tag, docs, SBOM, provenance, and distribution artifacts originate from the same commit.

### Product success measures after release

- A new user can complete index → text extraction → search and submit → wait → download workflows by copying documentation commands without editing them.
- Bulk exports use bounded memory and produce no visible partial result on failure or cancellation.
- Search results are reproducible, every snippet shows the requested phrase, and API count fields have unambiguous semantics.
- The full dependency closure remains audit-clean in CI, with any exception documented and time-bounded.
- Subsequent dashboard work builds on stable typed services rather than adding another interface around broken job or search behavior.

## 7. Explicit non-goals for the stabilization release

- No full JavaScript replay engine; retain CDXJ/pywb interoperability.
- No broad extractor-format expansion while current correctness and dependency work is open.
- No wholesale rewrite of indexing, analysis, or workspace storage.
- No raw SQL, arbitrary filesystem access, or mutation tools added to REST/MCP.
- No new batch-job kind before the existing export-records lifecycle is trustworthy.
