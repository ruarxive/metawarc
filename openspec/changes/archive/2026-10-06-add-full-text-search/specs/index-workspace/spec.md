## ADDED Requirements

### Requirement: `texts` sidecar
The workspace SHALL recognise a `texts` sidecar kind whose Parquet
schema carries `archive_id`, `warc_id`, `source`, `url`, `language`,
and `text` columns, and SHALL publish it through the existing sidecar
catalog without a new schema migration.

#### Scenario: `texts` sidecar is published
- **WHEN** a `texts` sidecar is written for an archive
- **THEN** `workspace.active_sidecars("texts", [archive_id])`
  returns true and `workspace.active_sidecar_paths("texts", ...)`
  returns the path

### Requirement: FTS index lifecycle
The workspace SHALL lazily create a DuckDB FTS index named
`records_text` over the `text` column keyed by `(archive_id, warc_id)`
when the first search runs, and SHALL keep the index in sync as new
`texts` sidecars are written.

#### Scenario: First search against an empty workspace
- **WHEN** a user runs `metawarc search <phrase>` before any
  `texts` sidecar exists
- **THEN** the workspace reports "no indexable sidecar" rather than
  raising

#### Scenario: Subsequent searches reuse the index
- **WHEN** a second search runs after the first
- **THEN** the FTS index is reused; no rebuild occurs