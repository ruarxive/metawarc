# Metawarc Product Review and Improvement Plan

**Review date:** 2026-09-17
**Scope:** `master` at `c809666` (post-2.0.1, after the 2026-08-04 repository review drove the 2.0 rewrite)
**Companion documents:** `REPOSITORY_REVIEW_AND_IMPROVEMENT_PLAN.md` (2026-08-04, historical), `openspec/roadmap.md`

## 1. Executive summary

The 2.0 rewrite successfully delivered everything the August review demanded: a
versioned DuckDB/Parquet workspace with stable archive identities, incremental
ingestion, hardened extraction, secure typed query/export surfaces, a read-only
MCP server, local website replay, a Docusaurus documentation site, and real CI
quality gates. The product has grown from a fragile indexer into a credible,
documented preservation tool with three interfaces (CLI, REST, MCP).

Quality gates are green today: 65 tests pass, 85% coverage (gate: 75%), Ruff
and mypy clean, CI tests Python 3.10–3.13, smoke-tests wheel variants, and
produces an SBOM and provenance.

The main findings of this review are not code defects but **process and
hardening debt**:

1. **OpenSpec discipline has lapsed.** All 11 change proposals are implemented
   (10 marked complete) yet none are archived, `openspec/specs/` is empty, and
   the roadmap still lists work as "proposed" that shipped weeks ago. The spec
   corpus — the project's declared source of truth — does not exist.
2. **The dev environment carries known-vulnerable packages** (`httpx2`/
   `httpxcore2` 2.9.1, six CVEs), and `httpx2` appears unused in the test suite.
3. **Dead code remains in the tree** (`metawarc/base/`, `metawarc/data/`), and
   unreleased work (pytz fix, CI updates, docs site) needs a 2.0.2 release.
4. **Test coverage is thin exactly where the product is riskiest**: MCP tools,
   payload dump edge cases, ingestion recovery, and hostile-input handling.
5. The **roadmap's deferred capabilities** (full-text search, batch-job API,
   exploration dashboard) are now unblocked and are the natural next features.

Recommended direction: close the process debt first (it is cheap and compounds),
release 2.0.2, then invest in hostile-input hardening and test depth before
starting the next feature change.

## 2. Feature inventory and assessment

| Area | Commands / surface | Assessment |
|---|---|---|
| Indexing | `index` (add/update/rescan/force), `ingest`, `catalog`, `rebind`, `cleanup` | Strong. Stable archive IDs, batched atomic writes, checkpoints, resume. Move/rebind is explicit — good preservation hygiene. |
| Diagnostics | `doctor` (+ `--repair` dry-run/apply) | Strong concept; coverage gap in repair paths (workspace.py lines 804–856, 937–979 untested). |
| Query | `list-files`, `stats`, `get` | Typed, allowlisted, parameterized; raw SQL only via visibly named CLI `--unsafe-where`. Sound design. |
| Export | `dump`, `dump-metadata` | Manifest with SHA-256, no overwrites, record/byte limits. Dump edge cases least tested (78% coverage). |
| Metadata extraction | `index-content`, `analyze metadata/hashes/duplicates/links/integrity` | Broad format coverage (OOXML, PDF, images, video, audio, fonts); versioned envelopes with warnings and stable error codes. The largest modules (`cmds/extractor.py` 1389 lines, `analysis.py` 1415 lines) are approaching the size where a registry/plugin split would help, though no acute problem yet. |
| Replay | `serve` / `replay`, `export-cdxj` | Wayback-style replay with charset-aware rewriting; honest about JS limits and defers to pywb. Good scoping. |
| REST API | `serve` | Loopback-by-default, token for non-loopback, no raw SQL. Solid. |
| MCP | `mcp` | Read-only, 4 typed tools. Safe but **narrow** — no analysis, stats, or export-intent tools; lowest coverage in the package (61%). |
| Docs | Docusaurus site, per-command pages, architecture, cookbook, release checklist | Excellent for a project this size; published to ruarxive.org/metawarc. |

**Feature gaps relative to the roadmap's deferred list** (all now unblocked):

- Extracted-text / full-text search across the collection.
- Authenticated durable batch-job API (long exports/analysis as jobs).
- Read-only web exploration dashboard (catalog browsing distinct from replay).
- Richer MCP surface (collection stats, analysis summaries) without breaking
  the read-only, no-path, no-SQL contract.

## 3. Quality assessment

### Validation results (this review, run on the checkout)

| Check | Result |
|---|---|
| `pytest` | 65 passed, 0 failed |
| Coverage | 85% overall (gate 75%); CI adds a 70% gate on the indexer module |
| `ruff check` / `ruff format --check` | Clean |
| `mypy metawarc` | Clean (19 files) |
| `pip-audit` (dev env) | **6 known vulnerabilities: `httpcore2` 2.9.1 (PYSEC-2026-3844), `httpx2` 2.9.1 (PYSEC-2026-3845 through -3849); fixes in 2.10.0–2.12.0** |
| TODO/FIXME markers in `metawarc/` | None |
| OpenSpec state | 11 active changes, 10 fully checked; `specs/` empty; nothing archived |
| `metawarc/base/`, `metawarc/data/` | Dead packages, excluded from packaging/lint, still in tree |

### What is working well

- The architecture honored its constraints: payloads stay in WARCs, bounded
  memory (dedicated performance tests exist), atomic sidecar publication, and
  immutable sources.
- Tests use generated real `.warc`/`.warc.gz` fixtures, not mocks of the
  archive layer.
- CI validates the min and max supported Python, builds and smoke-tests wheel
  variants per extra, and emits an SBOM.
- The security posture documented in `README.md` matches the code: loopback
  defaults, token gating, allowlisted queries, sanitized exports.

### Risks and weaknesses (prioritized)

#### P0 — process debt (cheap to fix, compounds if ignored)

1. **OpenSpec specs do not exist.** `openspec/specs/` is empty while ten
   completed changes sit unarchived in `changes/`. The project's own
   convention says specs are truth and changes are proposals; today neither is
   true. Future changes have no baseline to delta against.
   *Fix:* archive the ten complete changes (`openspec archive <id> --yes`,
   which populates `specs/`), finish the two open tasks in
   `consolidate-release-baseline`, and refresh `roadmap.md` so "proposed"
   matches reality.
2. **Vulnerable dev dependency.** `httpx2>=0.1` resolves to 2.9.1 with six
   known CVEs. No test imports httpx/httpx2, so it is likely vestigial.
   *Fix:* remove it, or replace with standard `httpx` pinned `>=0.27` if a
   future TestClient-based API test needs it. CI runs `pip-audit` on built
   artifacts only, so this leaks into contributor environments silently.

#### P1 — release and hygiene

3. **Unreleased work on master.** Commits after 2.0.1 (pytz dependency, CI
   modernization, Docusaurus site, URL retargeting) are unreleased and
   unchangelogged. The pytz fix is user-visible for timezone-aware catalogs.
   *Fix:* cut 2.0.2 with a CHANGELOG entry; make the release checklist
   (docs/development/release-checklist.md) the template.
4. **Dead packages in the tree.** `metawarc/base/` (empty except `__pycache__`)
   and `metawarc/data/` (a 6-line `common.py` at 0% coverage) are excluded
   from packaging, lint, and types, but still confuse contributors and tooling.
   *Fix:* delete both directories and their exclusions from `pyproject.toml`.
5. **`requirements.txt` is drifting** from `pyproject.toml` (missing `pytz`,
   `fonttools[woff]`, version floors differ). Either generate it from
   pyproject or delete it — two dependency manifests will disagree again.

#### P2 — test depth where risk lives

6. **MCP tools are barely tested** (61% coverage; tool functions, transport
   options, and error paths unexercised). This is a public interface.
   *Fix:* add MCP tool-level tests via fastmcp's client/test harness; cover
   the ImportError guidance path for missing extras.
7. **Dump/export edge cases** (collision handling, traversal rejection,
   manifest checksums on failure, resume behavior) sit in the least-covered
   command module (78%). These protect user data — prioritize.
8. **Ingestion recovery paths** (interrupted checkpoints, corrupted sidecars,
   repair apply) are lightly covered (ingestion.py 77%, workspace repair
   lines untested). Preservation users feel these failures most.
9. **Hostile-input testing is thin.** The domain notes call out malformed
   headers, hostile URLs, and compressed bombs; current tests are mostly
   well-formed fixtures. *Fix:* add a small fuzz/property suite (truncated
   WARCs, random header garbage, zip-bomb-adjacent payloads within limits)
   feeding `index` and `index-content`.
10. **CI is Ubuntu-only.** WARC paths, DuckDB, and tempdir behavior differ on
    Windows and macOS. *Fix:* add a macOS (and optionally Windows) runner to
    the test matrix; keep packaging job on Ubuntu.

#### P3 — maintainability watchlist

11. `cmds/extractor.py` (53 functions) and `analysis.py` (26 functions,
    1415 lines) are the complexity centers. No action needed now; if the next
    format family lands, introduce an extractor registry before adding a
    fourth dispatch table.
12. `core.py` mixes CLI group wiring, option decorators, and report emission
    (1091 lines). Consider splitting `core.py` (command wiring) from
    `reporting.py` (rendering) when the next command is added.

## 4. Improvement plan

### Phase 0 — Close the loop (1–2 days, no product risk)

- [x] P0.1 Archive the ten complete OpenSpec changes; populate `openspec/specs/`;
      finish `consolidate-release-baseline` tasks 17–18; refresh `roadmap.md`.
- [x] P0.2 Remove or replace `httpx2` in dev dependencies; re-run `pip-audit`.
- [x] P1.3 Delete `metawarc/base/` and `metawarc/data/`; drop their exclusions.
- [x] P1.4 Reconcile `requirements.txt` with `pyproject.toml` (or delete it).
- [x] P1.5 Release 2.0.2 (pytz fix, CI, docs site) with CHANGELOG entry,
      signed tag, per the release checklist.

### Phase 1 — Harden the surfaces users touch (1–2 weeks)

- [x] P2.6 MCP tool tests with fastmcp test client; cover transport/bind and
      missing-extra guidance.
- [x] P2.7 Dump/export tests: collision, traversal rejection, manifest
      integrity, limit enforcement, resume.
- [x] P2.8 Ingestion recovery tests: interrupted checkpoint resume, corrupted
      sidecar rejection, `doctor --repair --apply` end-to-end.
- [x] P2.9 Hostile-input fuzz suite for `index`/`index-content`
      (truncation, garbage headers, oversize payloads near limits).
- [x] P2.10 Add macOS CI runner (Windows optional) for the test job.

### Phase 2 — Next capabilities (each as its own OpenSpec change)

Ordered by value-to-effort, aligned with the deferred roadmap items:

1. **Collection exploration dashboard** — read-only web UI over the catalog
   (hosts, MIME stats, timelines) distinct from replay. Extends `serve`'s
   existing home page; high visibility, moderate effort.
2. **Full-text search** — index extracted text (PDF/HTML) into a searchable
   store (DuckDB FTS or sidecar). Highest user value for research workflows;
   needs an OpenSpec design decision on storage and scope.
3. **Richer read-only MCP surface** — collection stats and analysis summary
   tools, preserving the no-SQL/no-path/no-mutation contract.
4. **Durable batch-job API** — authenticated async export/analysis jobs for
   large collections. Largest effort; defer until 1–3 are done.

### Success criteria for this plan

- `openspec validate --strict` passes; `openspec list` shows only new,
  genuinely-proposed changes; `specs/` reflects the shipped 2.x surface.
- `pip-audit` clean in dev and CI environments.
- Coverage gates hold with MCP and dump modules above 85%.
- 2.0.2 published from a commit where tag, changelog, docs, and artifacts agree.
