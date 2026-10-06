## 1. Spec delta
- [x] 1.1 Add an `## ADDED Requirements` block to
      `openspec/specs/remote-interfaces/spec.md` describing the new
      `collection_stats` and `metadata_summary` MCP tools, both
      inheriting the existing allowlist, no-mutation, no-SQL, and
      `ServerSettings.max_page` discipline

## 2. MCP tools
- [x] 2.1 In `metawarc/mcp_server.py`, add `collection_stats(...)`
      that opens a read-only `Workspace` and returns
      `AnalysisService(workspace).summary(...).to_dict()`
- [x] 2.2 Add `metadata_summary(...)` that returns
      `AnalysisService(workspace).stored_metadata(...).to_dict()`
- [x] 2.3 Both tools reuse the existing `_serializable` helper and
      the same `Workspace(dbfile, data_dir, read_only=True, ...)`
      context manager pattern as the other read-only tools
- [x] 2.4 Confirm both tools appear in the MCP tool list and remain
      read-only (no `con.execute(...)` calls accepting arbitrary SQL)

## 3. Tests
- [x] 3.1 Add `tests/test_mcp_server_stats.py` covering:
      - `collection_stats` returns a `data` dict whose dimensions are
        the requested ones
      - `collection_stats` rejects `top=0` with a tool error
      - `metadata_summary` returns one row per selected type plus the
        documented `not-indexed` rows when a type has no sidecar
      - `metadata_summary` accepts the `all` shorthand
- [x] 3.2 Verify the existing `test_mcp_inventory_is_minimal_and_read_only`
      still passes (the inventory contract is intact) — updated to
      list the two new tool names

## 4. Verification
- [x] 4.1 `pytest -q` reports 159 + 7 new tests passing
- [x] 4.2 `metawarc.mcp_server` coverage holds at 100 %
- [x] 4.3 `ruff format --check`, `ruff check`, and `mypy metawarc`
      remain clean
- [x] 4.4 `openspec validate enrich-mcp-readonly-surface --strict`
      passes