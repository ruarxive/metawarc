# Change: Enrich the MCP read-only tool surface

## Why
The MCP server currently exposes `list_archives`, `list_records`,
`get_record_metadata`, `get_record_headers`, and `search_records`. Every
one of them is an inventory or lookup call: there is no way for an MCP
client to ask "what kinds of records does this collection hold, and how
many of each?" or "what stored metadata does the workspace currently
have for PDFs, images, OOXML, and the rest of the supported families?"
The user must either drop back to the REST API or run the local CLI to
get those summaries.

The underlying services already exist and are stable: `AnalysisService.summary()`
(`metawarc/analysis.py:185`) returns counts by `mime`, `ext`, `status`,
`host`, `date`, and `size_bucket`; `AnalysisService.stored_metadata()`
(`metawarc/analysis.py:203`) returns per-type extraction rollups
without re-reading the source payloads. Both are read-only and already
bound by the same `ServerSettings` limits as the remote surfaces. They
just lack MCP glue.

This change closes that gap with two new MCP tools, keeping the
allowlist, no-mutation, and no-arbitrary-SQL contracts intact. It does
not add a REST endpoint (the underlying reports are already reachable
via the local CLI for users who prefer REST-equivalent exports).

## What Changes
- Add a `collection_stats(archive_ids=None, dimensions=("mime","ext","status","host","date","size_bucket"), top=10)`
  MCP tool that wraps `AnalysisService.summary()` and returns the
  report as a serialisable mapping
- Add a `metadata_summary(metadata_types="all", archive_ids=None, top=10)`
  MCP tool that wraps `AnalysisService.stored_metadata()` and returns
  the per-type rollups
- Both tools enforce the same input contract as the underlying services:
  `top >= 1`, an optional `archive_ids` allowlist, and the existing
  `metadata_types` enum (`pdfs`, `images`, `ooxmldocs`, `oledocs`,
  `videos`, `audio`, `fonts`, `all`)
- Both tools honour the existing `ServerSettings.max_page` and
  `request_timeout_seconds` limits inherited from the FastAPI app that
  wraps the same services
- No new SQL surface; no new filesystem path argument; no new
  mutation path; no new dependency
- Tests: synthetic workspace, populated with one or two record types,
  asserts the new tools round-trip the same numbers as the local CLI

## Impact
- Affected specs: `remote-interfaces`
- Affected code: `metawarc/mcp_server.py` (two new tool handlers),
  `tests/test_mcp_server.py` (new cases)
- Dependencies: none
- Backward compatibility: the existing 5 tools (`list_archives`,
  `list_records`, `get_record_metadata`, `get_record_headers`,
  `search_records`) keep their signatures

## Risk
- `collection_stats()` triggers `QueryService.aggregate()` on every
  dimension listed. Mitigation: the dimensions list is fixed at the
  tool-default, the `top` knob is bounded by the same
  `ServerSettings.max_page` already enforced elsewhere, and the
  request still runs under the FastAPI semaphore + timeout inherited
  from the underlying service.
- `metadata_summary()` reads every active sidecar Parquet under the
  selected archive scope, like the local `analyze stored-metadata`
  command. Mitigation: that command is already covered by the existing
  progress-reporting and `STORED_METADATA_TYPES` allowlist; the new
  tool reuses both.