## ADDED Requirements

### Requirement: Command module layout
Every CLI command module SHALL live at the package top level
(`metawarc/<command>.py`) rather than under a sub-package
(`metawarc/cmds/`).

#### Scenario: A new CLI command is added
- **WHEN** a contributor adds a new CLI command
- **THEN** the command module is added at the package top level, and the
  command group wiring in `metawarc/core.py` imports the command from
  that top-level path

#### Scenario: A pre-flattening command module exists
- **WHEN** a third-party script imports
  `from metawarc.cmds.<command> import <symbol>` after the flatten
- **THEN** the import resolves to the new top-level module and the call
  site behaves identically

### Requirement: Separated reporting and command wiring
Report rendering helpers (Rich tables, JSON emitters) SHALL live in a
dedicated `metawarc/reporting.py` module, separate from the command
group wiring in `metawarc/core.py`.

#### Scenario: A command emits a JSON report
- **WHEN** a command runs with `--format json`
- **THEN** the rendering is performed by `metawarc.reporting` and the
  command wiring in `metawarc.core` only orchestrates the call

### Requirement: Library-friendly logging configuration
The package SHALL NOT configure logging on import; CLI invocations
through `metawarc/__main__.py` SHALL configure logging only when the
`--verbose` flag is honored or when no logging configuration exists
in the calling process.

#### Scenario: A library consumer imports `metawarc`
- **WHEN** a script imports `metawarc` without using the CLI entry
  point
- **THEN** no `logging.basicConfig` is called and the caller's logging
  configuration is preserved

#### Scenario: A user runs `metawarc --verbose`
- **WHEN** a user runs the CLI with `--verbose`
- **THEN** `metawarc/__main__.py` configures `logging.basicConfig` with
  the `INFO` level for the `metawarc` logger hierarchy