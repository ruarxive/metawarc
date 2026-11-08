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

- `<phrase>` (positional): the literal phrase to search for. Must not be empty.
- `--dbfile`, `--data-dir`: workspace options (see [workspace](/architecture/workspace)).
- `--limit` (default `50`): maximum number of matches; values above the
  configured `METAWARC_MAX_PAGE` are rejected.

## Behaviour

The search runs a bounded columnar scan over the active `texts` Parquet
files via DuckDB's `read_parquet`. Matching is case-insensitive and
literal: `%` and `_` have no wildcard meaning. Results are ordered by
`archive_id`, `warc_id`, `source`, and `url`, making limited searches
reproducible. There is no second FTS index to build or keep in sync.

If the workspace has no `texts` sidecar, the command exits 1 and asks the
user to run `metawarc index-content --text`. If the sidecar exists but the
phrase has no matches, the command prints `(no matches)` and exits 0.

## Output

Each match prints one tab-separated line:

```
<warc_id>\t<url>\t<snippet>
```

The snippet is centered on the first match and normally contains at most
256 characters; it expands when necessary to include a longer phrase.

## Examples

```bash
# populate the texts sidecar
metawarc index-content --dbfile collection.db --text

# search for a phrase
metawarc search "Welcome to the museum of modern art" --dbfile collection.db
# <urn:uuid:...>\thttps://example.test/welcome.html\tWelcome to the museum of modern art ...

# limit results
metawarc search "API" --dbfile collection.db --limit 10
```

See also: [`index-content --text`](/commands/index-content),
[`/records/search`](/integrations/rest-api),
and the `search_records` MCP tool in
[Agents and MCP](/use-cases/agents-and-mcp).