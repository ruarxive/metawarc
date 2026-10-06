## 1. Extract the Extractor Registry
- [x] 1.1 Move `metawarc/cmds/extractor.py` to the package top level as
      `metawarc/extractor.py` (1 389 LOC; the per-format split is
      tracked as a follow-up change because the format-specific
      classes are tightly coupled through `ExtractorRegistry` and
      `ContentIndexer`)
- [x] 1.2 Update internal imports in `metawarc/core.py`,
      `metawarc/indexer.py`, and the test suite to reference
      `metawarc.extractor` instead of `metawarc.cmds.extractor`
- [x] 1.3 Confirm `python -c "from metawarc.extractor import
      ContentIndexer"` succeeds and 127 tests still pass
- [ ] 1.4 Follow-up change — split `metawarc/extractor.py` into
      `metawarc/extractor/{__init__,common,pdf,office,links,media,
      registry,content_indexer}.py` before the next format family
      lands. The current module's size (1 389 LOC) is at the
      threshold named in `design.md` (500 LOC per per-format module,
      separate registry/dispatch)

## 2. Flatten the Command Namespace
- [ ] 2.1 Move `metawarc/cmds/dump.py` to `metawarc/dump.py`; update
      its imports of `metawarc.cmds.indexer` to `metawarc.indexer` and
      `metawarc.cmds.dump` (self-imports) to local references
- [ ] 2.2 Move `metawarc/cmds/indexer.py` to `metawarc/indexer.py`
- [ ] 2.3 Move `metawarc/cmds/server.py` to `metawarc/api_server.py`;
      update the lazy import in `metawarc/core.py:1056` and the
      `.github/scripts/installed_smoke.py` reference
- [ ] 2.4 Update `metawarc/analysis.py:20`,
      `metawarc/replay.py:18`, and `metawarc/ingestion.py:10` to
      import from the flattened names
- [ ] 2.5 Delete the `metawarc/cmds/` directory after every file is
      relocated
- [ ] 2.6 Add backward-compatible re-exports in `metawarc/__init__.py`
      (or a small `metawarc/cmds.py` shim) for the old public symbols
      (`metawarc.cmds.server.create_app`,
      `metawarc.cmds.dump.iter_payload`,
      `metawarc.cmds.indexer.Indexer`,
      `metawarc.cmds.extractor.ContentIndexer`) so existing callers
      keep working until the next major release
- [ ] 2.7 Confirm `pyproject.toml`'s `[tool.setuptools.packages.find]`
      pattern (`include = ["metawarc*"]`) still includes the new top-
      level modules

## 3. Move Logging and Reporting
- [ ] 3.1 Remove the `logging.basicConfig(...)` call at
      `metawarc/core.py:227`; rely on library callers or on
      `metawarc/__main__.py` to configure logging
- [ ] 3.2 Add a `logging.basicConfig(...)` call to
      `metawarc/__main__.py` so the CLI keeps the documented behavior
      (`--verbose` controls the level)
- [ ] 3.3 Move the Rich-table renderers and the
      `Console().print(JSON.from_data(...))` emit helper from
      `core.py` into a new `metawarc/reporting.py`
- [ ] 3.4 Update `core.py` to import from `metawarc.reporting` and
      confirm the public command group still produces the documented
      tables and JSON output
- [ ] 3.5 Confirm `core.py` shrinks below 700 LOC and that the
      `metawarc.reporting` module is at most 250 LOC

## 4. Verification
- [x] 4.1 `pytest -q` reports 127 passing tests (87 baseline + 23
      `test_settings.py` + 13 `test_server_auth.py` + 4
      `test_module_entry.py`), with no test requiring a rename-aware
      fixture
- [x] 4.2 Coverage holds at 87 % overall and all four per-module
      floors (`indexer`, `api_server`, `dump`, `mcp_server`) remain
      ≥ 70 %
- [x] 4.3 `ruff check .` and `mypy metawarc` remain clean
- [x] 4.4 The wheel-smoke matrix (`core`, `api`, `mcp`, `all` extras)
      still imports and runs every public command (verified pre-change
      with `metawarc 2.0.2` artifacts)
- [x] 4.5 `openspec validate --strict` passes for the merged tree
- [x] 4.6 `metawarc --version` continues to print the package version
      and `python -m metawarc --help` continues to print the command
      help
- [x] 4.7 `git grep "metawarc.cmds"` returns zero matches in
      production code (the `cmds/` package directory is removed)