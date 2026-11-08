## 1. Contract regressions
- [x] 1.1 Add failing tests for absent progress projections, durable batch
      updates, `jobs wait` rendering, and stdout/exit-code compatibility.
- [x] 1.2 Add failing prune preview/apply, eligibility-cutoff, disabled-TTL,
      locked-job, persisted-path, and symlink safety tests.

## 2. Durable export progress
- [x] 2.1 Implement atomic per-job progress sidecar read/write helpers with
      validated counts, timestamps, bounded reads, and no lifecycle mutation.
- [x] 2.2 Publish initial, 256-row boundary, and final planned-row progress
      for JSON, CSV, and Parquet while preserving cancellation and atomic
      result publication.
- [x] 2.3 Project additive progress through REST list/get and CLI
      list/get/wait, with `null` for missing pre-change sidecars.
- [x] 2.4 Reuse the shared renderer for `jobs wait --progress/--no-progress`;
      keep final JSON on stdout and existing exit codes.

## 3. Safe retention and pruning
- [x] 3.1 Implement one store-level preview/apply policy using fresh terminal
      state, valid `ended_at`, injectable cutoff time, and per-job claims.
- [x] 3.2 Implement contained deletion of lifecycle/progress/result/staging
      files without following persisted paths or symlinks; handle locks,
      unexpected entries, and crash leftovers safely.
- [x] 3.3 Add preview-by-default `metawarc jobs prune --retention-days N
      --apply` with actionable JSON reports and no REST deletion route.
- [x] 3.4 Add opt-in `METAWARC_JOB_RETENTION_DAYS`, startup/60-second bounded
      cleanup off the event loop, and multi-process regression coverage.

## 4. Documentation and plan
- [x] 4.1 Update batch/REST/CLI guides with progress semantics, stderr/stdout
      behavior, retention defaults, preview/apply, and post-prune 404s.
- [x] 4.2 Update the changelog and product plan after acceptance; leave
      operational metrics and additional job kinds explicitly open.

## 5. Verification
- [x] 5.1 Run focused progress/retention tests and the complete suite with
      coverage, Ruff, formatting, mypy, and strict OpenSpec validation.
- [x] 5.2 Verify 0/1/256/257/50 000-row progress, cancellation/recovery races,
      prune cutoffs and batches beyond 50, and real two-process lock safety.
- [x] 5.3 Build/install the wheel outside the source tree and run authenticated
      progress/download and preview/apply/prune-to-404 workflows.
- [x] 5.4 Build documentation, sdist, and wheel; run dependency/lock/patch
      gates and supported CI matrix without claiming unexecuted coverage.
      Documentation, package, dependency, lock, patch, and supported CI matrix
      gates passed.
