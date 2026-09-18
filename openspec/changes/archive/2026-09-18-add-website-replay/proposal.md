# Change: Add website replay for indexed WARC collections

## Why
Metawarc can index, query, and stream payloads, but researchers still need a
browser-facing way to open archived URLs at a chosen time. Without replay, users
export individual records or leave the workspace for a separate Wayback stack,
breaking the DuckDB catalog as the source of truth.

## What Changes
- Add a read-only local replay capability over the existing workspace catalog
- Resolve captures by exact URL and closest or exact timestamp (SURT deferred)
- Mount replay routes on `metawarc serve` (shared app, auth, and limits)
- Serve payloads as navigable HTTP responses (not download attachments)
- Follow archived redirects and rewrite HTML/CSS URLs for same-collection hops
- Export CDXJ (and optional path index) in the same first milestone so
  full-fidelity pywb can consume the same WARCs when JS/Wombat is required
- Keep an optional later pywb bridge; do **not** replace metawarc's catalog
  with pywb's index
- Keep replay behind an optional extra; core CLI remains usable without it

## Impact
- Affected specs: `website-replay` (new), `record-query`, `remote-interfaces`
- Affected code: new replay service/rewriter modules, query timestamp
  selection, CLI `replay` command, optional FastAPI routes, CDXJ exporter,
  packaging extras, docs
- Dependencies: `stabilize-index-workspace`, `secure-query-export-interfaces`
- Related deferred item: F4.10 web exploration UI remains separate (catalog
  dashboard, not page replay)
