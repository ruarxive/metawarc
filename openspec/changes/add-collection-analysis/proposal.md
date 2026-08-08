# Change: Add collection analysis and preservation reports

## Why
Current statistics only group by MIME or extension. Archive users need broader
collection summaries, duplicate detection, link relationships, and integrity
evidence to understand a crawl and prioritize preservation work.

## What Changes
- Add collection summaries by MIME, extension, status, host/domain, date, and size
- Optionally compute payload SHA-256 values during indexing or a later analysis
- Report duplicate groups without deleting or rewriting source records
- Normalize and resolve extracted links into an internal/external domain graph
- Add WARC/header/payload integrity checks and digest verification when present
- Export analysis as terminal tables, JSON, CSV, and Parquet
- Record analysis version, source catalog revision, limits, and partial failures

## Impact
- Affected specs: `collection-analysis`
- Affected code: analysis service, query layer, optional index hashing, link
  normalization, integrity validators, CLI commands, exports
- Dependencies: `stabilize-index-workspace`, `secure-query-export-interfaces`,
  `harden-metadata-extraction`

