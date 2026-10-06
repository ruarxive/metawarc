---
title: "metawarc search"
description: "Phrase-search across the indexed texts sidecar"
slug: /commands/search
---
# `metawarc search`

Phrase-search across the indexed `texts` sidecar. Requires the workspace
to have been indexed with text extraction
(`metawarc index-content ... --text`) so the `texts` Parquet sidecar is
populated.

## Synopsis

```bash
metawarc search [--dbfile <path>] [--data-dir <path>] <phrase> [--limit <n>]
```

## Options

- `<phrase>` (positional): the phrase to search for. Must not be empty.
- `--dbfile`, `--data-dir`: workspace options (see [workspace](/architecture/workspace)).
- `--limit` (default `50`): maximum number of matches; capped at the
  configured `METAWARC_MAX_PAGE`.

## Behaviour

The search runs a bounded columnar scan over the active `texts` Parquet
files via DuckDB's `read_parquet`. Phrases are matched with a
case-insensitive `ILIKE '%phrase%'` predicate, so matches can span HTML
markup, PDF/OOXML artefacts, and arbitrary slice boundaries in the
projected text. There is no second FTS index to build or keep in sync.

DuckDB's FTS extension regressed in 1.5.x (its `create_fts_index` pragma
fails to materialise the virtual index). The columnar scan is the
dependable backend until a future DuckDB release fixes the pragma; the
`_ensure_texts_index` helper is a no-op placeholder that retains the
documented contract.

If the workspace has no `texts` sidecar (because the user did not run
`index-content --text` yet), the command prints `(no matches)` and exits
0 — it does not raise.

## Output

Each match prints one tab-separated line:

```
<warc_id>\t<url>\t<snippet>
```

The snippet is the first 256 characters of the matched text.

## Examples

```bash
# populate the texts sidecar
metawarc index-content --text sample.warc

# search for a phrase
metawarc search "Welcome to the museum of modern art"
# <urn:uuid:...>\thttps://example.test/welcome.html\tWelcome to the museum of modern art ...

# limit results
metawarc search "API" --limit 10
```

See also: [`index-content --text`](/commands/index-content),
[`/records/search`](/integrations/rest-api),
and the `search_records` MCP tool in
[Agents and MCP](/use-cases/agents-and-mcp).