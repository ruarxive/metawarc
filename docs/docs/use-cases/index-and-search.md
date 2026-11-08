---
title: "Index and search"
description: "End-to-end workflow from WARC archives to phrase search"
---
# Index and search

The `index`, `index-content`, and `search` commands form one pipeline.
`index` builds the catalog, `index-content --text` projects extracted text
into the `texts` Parquet sidecar, and `search` answers phrase queries
against that sidecar. This use case shows the chained workflow as a single
coherent scenario.

## Single-archive scenario

The fastest path from a local WARC to a phrase-search result:

```bash
# 1. Build the record and header indexes
metawarc index collection.warc.gz --dbfile collection.db --resume

# 2. Read the WARCs and project plain text into the 'texts' sidecar
metawarc index-content --dbfile collection.db --text

# 3. Phrase-search the sidecar
metawarc search "Welcome to the museum of modern art" --dbfile collection.db
```

Step 1 is mandatory. Step 2 is opt-in: structured extraction
(`--type pdfs`, `--type images`, and the rest) keeps its current cost
unless you pass `--text`. Step 3 reads only the active `texts` sidecar;
it does not join results back to the record catalog.

Step 3 accepts a positional phrase and a `--limit` flag:

```bash
# bound the number of matches
metawarc search "API" --dbfile collection.db --limit 10

# combine with workspace flags (--dbfile, --data-dir) — same as index
metawarc search "data breach" --dbfile /srv/collections/main.db --limit 25
```

Each match prints one tab-separated line
`<warc_id>\t<url>\t<snippet>`. The snippet is centered on the first match
and normally contains at most 256 characters; it expands when necessary
to include a longer phrase.

## Multi-archive scenario

When the corpus is a directory tree of independent crawls, the same
chain runs once per workflow:

```bash
# A. initial bulk indexing (resume-friendly, idempotent on re-runs)
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume

# B. populate the texts sidecar for the whole catalog
metawarc index-content --dbfile collection.db --text

# C. run repeatable, bounded searches
metawarc search "press release" --dbfile collection.db --limit 50
```

Both `index` and `index-content --text` read source WARCs. Subsequent
`search` calls read only the Parquet sidecar, not the original payloads.
They are bounded scans, not ranked full-text queries; no corpus-scale
latency is implied.

## Remote search

Search currently accepts only `phrase` and `limit`, plus workspace options
on the CLI. Record filters such as `--archive-ids` belong to `list-files`
and are not search options.

```bash
# REST: bearer-token protected
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     'http://127.0.0.1:8000/records/search?phrase=press%20release&limit=25'

# MCP: read-only tool
search_records(phrase="press release", limit=25)
```

`/records/search` and `search_records` reject empty phrases and limits
above `METAWARC_MAX_PAGE`. Their `total` field reports all matches,
`returned` reports the number of hits returned, and `limit` is the
requested bound.

## Operational checklist

| Concern | What to do |
|---------|------------|
| New WARCs arrive | `metawarc index … --resume` (updates the catalog), then `metawarc index-content --text --rescan` (rebuilds the texts sidecar) |
| Same archive returned, no search hits | The `texts` sidecar may be empty or stale; rerun `index-content --text` |
| Multi-language content | The `texts` sidecar carries a `language` column populated by the extractors; literal matching is case-insensitive and language-agnostic |
| Bounded exports from search results | `search` returns row IDs; pipe the result into `metawarc get '<warc_id>' --dbfile collection.db --output result.html` for a single payload, or `metawarc dump --dbfile collection.db --url-pattern …` for a filtered set |

## Incremental refresh

`index` and `index-content --text` open the source WARCs; `search` does
not. After a fresh batch is added, the workflow is:

```bash
# 1. add the new WARCs to the catalog
metawarc index 'archives/new-batch/**/*.warc*' --dbfile collection.db --resume

# 2. refresh the texts sidecar for the whole catalog with --rescan
metawarc index-content --dbfile collection.db --text --rescan
```

Pass `--rescan` on `index-content` so the existing `texts` sidecar is
rebuilt even when `ContentIndexer` would otherwise skip it. The catalog
identity of the existing archives is preserved, so search matches
continue to use the same `archive_id` values.

## When something does not match

- If no `texts` sidecar exists, `search` exits 1 with an
  `index-content --text` hint and REST returns HTTP 409. If the sidecar
  exists but has no matches, the CLI prints `(no matches)` and exits 0.
- An empty phrase is rejected with `click.UsageError` on the CLI. REST
  returns HTTP 422 for an empty query or excessive limit, and HTTP 400
  for a whitespace-only phrase.
- The text extractor is bounded by `ExtractionLimits`; payloads larger
  than the budget are returned with `truncated=true`. Search snippets
  still include the matched phrase with deterministic surrounding context.

See [`index`](/commands/index-records),
[`index-content --text`](/commands/index-content),
[`search`](/commands/search),
[`/records/search`](/integrations/rest-api), and the `search_records`
tool in [Agents and MCP](/use-cases/agents-and-mcp).