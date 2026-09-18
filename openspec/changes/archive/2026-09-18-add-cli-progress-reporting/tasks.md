## 1. Progress Foundation

- [x] 1.1 Define typed progress events and a no-op default for service callers
- [x] 1.2 Implement the shared Rich stderr renderer with bounded refresh rate
- [x] 1.3 Add reusable tri-state `--progress/--no-progress` CLI options and
  terminal/silent/machine-output resolution

## 2. Indexing and Extraction

- [x] 2.1 Replace the indexer's direct `tqdm` presentation with source and
  record/byte progress events
- [x] 2.2 Forward applied ingestion progress from its delegated indexing work
- [x] 2.3 Add metadata-type, archive, and candidate-record progress to
  `index-content`, including skipped and failed work

## 3. Export and Analysis

- [x] 3.1 Add selected-record and byte progress to bulk payload export
- [x] 3.2 Add row progress to stored metadata export
- [x] 3.3 Add archive and payload progress to hash analysis
- [x] 3.4 Add archive and record/byte progress to integrity analysis

## 4. CLI Integration and Documentation

- [x] 4.1 Wire the renderer into every covered command without changing result
  schemas or stdout routing
- [x] 4.2 Document default auto behavior, forced/disabled progress, stderr, and
  interactions with silent and JSON modes
- [x] 4.3 Remove `tqdm` if no supported code path still uses it

## 5. Verification

- [x] 5.1 Test monotonic event sequences, exact and unknown totals, skip/failure
  outcomes, and multi-type `index-content` nesting
- [x] 5.2 Test TTY auto-enable and non-TTY auto-disable behavior
- [x] 5.3 Test `--progress`, `--no-progress`, `--silent`, JSON output, and clean
  stdout/stderr separation
- [x] 5.4 Test renderer cleanup after service errors and keyboard interruption
- [x] 5.5 Run the full test suite, Ruff, and MyPy quality gates
