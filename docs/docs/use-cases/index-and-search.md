---
title: "Index and search"
description: "End-to-end workflow from WARC archives to phrase search"
---
# Index and search

The `index` and `search` commands are two ends of the same pipeline.
`index` builds the catalog and the `texts` Parquet sidecar that powers
`search`; `search` answers phrase queries against that sidecar. This
use case shows the chained workflow as a single coherent scenario.

## Single-archive scenario

The fastest path from a local WARC to a phrase-search result:

```bash
# 1. Build the record and header indexes
metawarc index collection.warc.gz --dbfile collection.db --resume

# 2. Project the extracted plain text into the 'texts' sidecar
metawarc index-content --dbfile collection.db --text

# 3. Phrase-search the sidecar
metawarc search "Welcome to the museum of modern art" --dbfile collection.db
```

Step 1 is mandatory: `search` reads `archive_id`, `warc_id`, `source`,
`url`, and `text` from the `texts` sidecar, but those rows are joined to
the catalog so the result references real catalog archives. Step 2 is
opt-in: structured extraction (`--type pdfs`, `--type images`, and the
rest) keeps its current cost unless you pass `--text`.

Step 3 accepts a positional phrase and a `--limit` flag:

```bash
# bound the number of matches
metawarc search "API" --dbfile collection.db --limit 10

# combine with workspace flags (--dbfile, --data-dir) — same as index
metawarc search "data breach" --dbfile /srv/collections/main.db --limit 25
```

Each match prints one tab-separated line
`<warc_id>\t<url>\t<snippet>`. The snippet is the first 256 characters
of the matched text.

## Multi-archive scenario

When the corpus is a directory tree of independent crawls, the same
chain runs once per workflow:

```bash
# A. initial bulk indexing (resume-friendly, idempotent on re-runs)
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume

# B. populate the texts sidecar for the whole catalog
metawarc index-content --dbfile collection.db --text

# C. iterate searches, possibly across different filters
metawarc search "press release" --dbfile collection.db --limit 50
metawarc search "press release" --dbfile collection.db --archive-ids crawl-2023,crawl-2024 --limit 50
```

`index` is the only step that touches the source WARCs. After step B,
the workspace is fully searchable without re-reading the original
payloads, and subsequent `search` calls are bounded Parquet scans
that take seconds even on multi-million-record catalogs.

## Restricted dataset search

Combine `metawarc search` with the standard `Workspace` filters that
the index/query paths already use. The CLI surface reuses the same
allowlist; the REST and MCP surfaces apply the same allowlist at the
transport boundary.

```bash
# REST: bearer-token protected
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     'http://127.0.0.1:8000/records/search?phrase=press%20release&limit=25'

# MCP: read-only tool
search_records(phrase="press release", limit=25)
```

`/records/search` and `search_records` both reject empty phrases and
clamps `limit` to `1..METAWARC_MAX_PAGE`.

## Operational checklist

| Concern | What to do |
|---------|------------|
| New WARCs arrive | `metawarc index … --resume` (updates the catalog), then `metawarc index-content --text --rescan` (rebuilds the texts sidecar) |
| Same archive returned, no search hits | The `texts` sidecar may be empty or stale; rerun `index-content --text` |
| Multi-language content | The `texts` sidecar carries a `language` column populated by the extractors; search matching is `ILIKE`, language-agnostic |
| Bounded exports from search results | `search` returns row IDs; pipe the result into `metawarc get '<warc_id>' --dbfile collection.db --output result.html` for a single payload, or `metawarc dump --dbfile collection.db --url-pattern …` for a filtered set |

## Incremental refresh

`index` is the only command that opens the source WARCs. After a fresh
batch is added, the workflow is:

```bash
# 1. add the new WARCs to the catalog
metawarc index 'archives/new-batch/**/*.warc*' --dbfile collection.db --resume

# 2. refresh the texts sidecar for the affected archives only,
# or for the whole catalog with --rescan
metawarc index-content --dbfile collection.db --text --rescan
```

Pass `--rescan` on `index-content` so the existing `texts` sidecar is
rebuilt even when `ContentIndexer` would otherwise skip it. The catalog
identity of the existing archives is preserved, so search matches
continue to use the same `archive_id` values.

## When something does not match

- `search` prints `(no matches)` and exits 0 when the workspace has no
  `texts` sidecar yet, or when the phrase is not in any extracted row.
  This is by contract — see [`search`](/commands/search).
- An empty phrase is rejected with `click.UsageError` on the CLI and
  HTTP 400 on REST. An over-limit `--limit` is rejected the same way.
- The text extractor is bounded by `ExtractionLimits`; payloads larger
  than the budget are returned with `truncated=true`. Search matches
  inside a truncated payload still surface a 256-character snippet.

See [`index`](/commands/index-records),
[`index-content --text`](/commands/index-content),
[`search`](/commands/search),
[`/records/search`](/integrations/rest-api), and the `search_records`
tool in [Agents and MCP](/use-cases/agents-and-mcp).