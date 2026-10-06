---
title: "metawarc search"
description: "Phrase-search across the indexed texts sidecar"
slug: /commands/search
---
# `metawarc search`

Phrase-search across the indexed `texts` sidecar. Requires the workspace
to have been indexed with text extraction (`metawarc content-index ... --text`)
so that the FTS index has a `texts` sidecar to build over.

## Synopsis

```bash
metawarc search [--dbfile <path>] [--data-dir <path>] <phrase> [--limit <n>]
```

## Options

- `<phrase>` (positional): the phrase to search for. Must not be empty.
- `--dbfile`, `--data-dir`: workspace options (see `workspace`).
- `--limit` (default `50`): maximum number of matches; capped at the
  configured `METAWARC_MAX_PAGE`.

## Behaviour

The first invocation of `search` against a workspace lazily installs the
DuckDB FTS extension and creates the `records_text` FTS index over the
`text` column keyed by `warc_id`. The index is reused on subsequent
invocations.

If the workspace has no `texts` sidecar (because the user did not run
`content-index --text` yet), the command prints `(no matches)` and exits
0 — it does not raise.

## Output

Each match prints one tab-separated line:

```
<warc_id>\t<url>\t<snippet>
```

The snippet is the first 256 characters of the matched text.

## Examples

```bash
# index with text extraction enabled
metawarc content-index --text sample.warc

# search for a phrase
metawarc search "Welcome to the museum of modern art"
# WARC-Record-ID <urn:uuid:...> https://example.test/welcome.html Welcome to the museum of modern art ...

# limit results
metawarc search "API" --limit 10
```