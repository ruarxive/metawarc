## 1. Contract regressions
- [x] 1.1 Add failing REST tests proving that result bytes are not
      currently downloadable and local paths appear in job responses.
- [x] 1.2 Add malicious persisted-path, traversal, missing-file,
      directory, and symlink cases with exact 404/409 expectations.
- [x] 1.3 Capture current CLI/local-path behavior as a compatibility
      regression before changing the remote projection.

## 2. Safe artifact resolution
- [x] 2.1 Implement one resolver shared by metadata and content routes,
      using only validated id, allowlisted format, deterministic filename,
      regular-file checks, and resolved directory containment.
- [x] 2.2 Keep persisted job JSON and local CLI `result.path` unchanged;
      use actual validated file size for remote metadata.
- [x] 2.3 Add focused tests proving external content is never served for
      absolute-path injection, traversal, wrong suffix, or symlink input.

## 3. REST download and response migration
- [x] 3.1 Replace `path` with `download_url` in `JobResultResponse` and
      sanitize embedded job result mappings in list/get responses.
- [x] 3.2 Add authenticated `GET /jobs/{id}/result/content` with streaming
      file responses, exact media types, safe attachment names, content
      length, and `Cache-Control: no-store`.
- [x] 3.3 Preserve 404 unknown-job, 409 non-succeeded, and 404 invalid or
      missing artifact behavior across metadata and content routes.
- [x] 3.4 Extend bearer-token tests to both result routes and verify exact
      downloaded bytes for JSON, CSV, and Parquet.

## 4. Documentation and plan
- [x] 4.1 Apply the `remote-batch-job` delta and correct its current
      metadata-versus-streaming route description and CLI/REST result
      location semantics.
- [x] 4.2 Update REST and batch-job guides with authenticated download
      commands, response migration, media types, and error behavior.
- [x] 4.3 Mark the REST response change as breaking in the changelog and
      update improvement-plan item 1.8 only after acceptance checks pass.

## 5. Verification
- [x] 5.1 Run focused API/security/CLI tests, the complete suite with
      coverage, Ruff, mypy, and formatting checks.
- [x] 5.2 Build and install the wheel outside the source tree; run the
      authenticated submit → wait → metadata → download workflow for all
      formats, including one 50 000-row export.
- [ ] 5.3 Run existing claim/recovery subprocess tests and the supported
      CI matrix when pushed; do not claim unexecuted matrix coverage.
- [x] 5.4 Build documentation, sdist, and wheel; run strict OpenSpec,
      `pip check`, `uv lock --check`, `git diff --check`, and relevant
      dependency audits.
