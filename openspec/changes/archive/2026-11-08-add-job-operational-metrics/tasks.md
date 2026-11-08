## 1. Contract regressions
- [x] 1.1 Add failing aggregation tests for every lifecycle status, exact queue
      and execution durations, empty summaries, and timestamp edge cases.
- [x] 1.2 Add failing selection/bounds tests for deterministic newest-first
      limits, total/included/truncated, malformed and oversized files, symlink
      rejection, and concurrent file disappearance.

## 2. Store and interface implementation
- [x] 2.1 Implement the shared read-only store metrics calculation with bounded
      per-file reads, bounded selection/accumulators, and no lifecycle mutation.
- [x] 2.2 Add typed metrics responses and authenticated `GET /jobs/metrics`
      before the dynamic job route, with bounded limit validation and blocking
      filesystem work off the event loop.
- [x] 2.3 Add `metawarc jobs metrics --limit N` using the same calculation and
      machine-readable stdout JSON without starting a runner.

## 3. Concurrency and compatibility
- [x] 3.1 Test metrics during completion, cancellation, recovery, and pruning;
      prove no claims, writes, scheduling, result changes, or non-finite values.
- [x] 3.2 Verify old jobs with incomplete timing metadata, route precedence,
      response privacy, authentication, and unchanged existing job interfaces.

## 4. Documentation and plan
- [x] 4.1 Document the response contract, duration formulas, empty values,
      limit/truncation, invalid files, retention caveats, and non-transactional
      observation semantics in REST/CLI/batch guides.
- [x] 4.2 Update the changelog and product plan after acceptance; keep persistent
      telemetry, rates/percentiles/ETA, and additional job kinds out of scope.

## 5. Verification
- [x] 5.1 Run focused metrics/concurrency tests and the complete suite with
      coverage, Ruff, formatting, mypy, and strict OpenSpec validation.
- [x] 5.2 Build/install the wheel outside the source tree and run authenticated
      REST plus CLI metrics over mixed jobs before and after pruning.
- [x] 5.3 Build documentation, sdist, and wheel; run dependency/lock/patch gates
      and the supported CI matrix without claiming unexecuted coverage.
      Documentation, package, dependency, lock, patch, and supported CI matrix
      gates passed.
