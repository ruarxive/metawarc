---
title: "Phrase search"
description: "Find records whose extracted text contains a phrase"
---
# Phrase search

Search the extracted plain-text projection of every indexed HTML, PDF, and
OOXML record. The pipeline writes a `texts` Parquet sidecar; the
backend reads it with a bounded DuckDB columnar scan.

## Pipeline

1. Index the WARC collection as for any other workflow:

   ```bash
   metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume
   ```

2. Populate the `texts` sidecar once with `index-content --text`:

   ```bash
   metawarc index-content --dbfile collection.db --text
   ```

   The text-extractor chain selects `TextExtractor` for HTML,
   `PdfTextExtractor` for PDF, and `OoxmlTextExtractor` for OOXML.
   Each successful write becomes one row in the `texts` Parquet with
   columns `(archive_id, warc_id, source, url, language, text)`.
   `--text` is opt-in so the default structured-extraction cost does
   not change.

3. Search from any surface that exposes the workspace.

### CLI

```bash
metawarc search "Welcome to the museum of modern art" --dbfile collection.db
metawarc search "API" --dbfile collection.db --limit 10
```

Each match prints one tab-separated line:
`<warc_id>\t<url>\t<snippet>`. The snippet is centered on the first
match and normally contains at most 256 characters; it expands when
necessary to include a phrase longer than 256 characters.

### REST

```bash
curl -H "Authorization: Bearer $METAWARC_API_TOKEN" \
     'http://127.0.0.1:8000/records/search?phrase=Welcome&limit=10'
```

`GET /records/search` accepts `phrase` (1–512 characters) and `limit`
(1 – `METAWARC_MAX_PAGE`, default 50). The response carries `phrase`,
`limit`, `total`, `returned`, and `hits`. `total` is the number of matches
in the active sidecar, while `returned` is the number of rows in `hits`.
Each hit contains `archive_id`, `warc_id`, `source`, `url`, and `snippet`.

### MCP

```python
search_records(phrase="Welcome to the museum of modern art", limit=50)
```

Returns the same counts and `hits` structure as the REST endpoint.

## Backend

DuckDB's FTS extension regressed in 1.5.x — its `create_fts_index`
pragma fails to materialise the virtual index. The dependable backend
is therefore a bounded `read_parquet` scan with a case-insensitive
literal contains predicate. `%` and `_` are ordinary phrase characters,
not wildcards. Results are ordered by `archive_id`, `warc_id`, `source`,
and `url`, so repeated limited searches return the same rows. No second
FTS index is created or kept in sync.

## Boundaries

- Empty phrases and `limit` higher than the configured `METAWARC_MAX_PAGE`
  are rejected. REST returns HTTP 422 for an empty query or excessive
  limit, and HTTP 400 for a whitespace-only phrase.
- If no `texts` sidecar exists, the CLI exits 1 with an
  `index-content --text` hint, REST returns HTTP 409, and MCP returns a
  tool error. An existing sidecar with no matches returns an empty `hits`
  list; the CLI prints `(no matches)` and exits 0.
- CLI, REST, and MCP open the workspace read-only while searching.

## Refresh after new WARCs

Re-running `metawarc index` adds them, but the `texts` sidecar is not
automatically rebuilt. Refresh it explicitly with `--rescan`:

```bash
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc index-content --dbfile collection.db --text --rescan
```

See [`search`](/commands/search), [`index-content --text`](/commands/index-content),
[`/records/search`](/integrations/rest-api), and the `search_records`
tool in [Agents and MCP](/use-cases/agents-and-mcp). For the chained
`index` → `search` workflow as a single scenario, see
[Index and search](/use-cases/index-and-search).