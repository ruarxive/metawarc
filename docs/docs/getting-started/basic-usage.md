---
title: "Basic usage"
description: "Workspace flags, filters, progress, and output formats"
---
# Basic usage

The CLI entry point is `metawarc`. Use `metawarc COMMAND --help` for the live
flag list of the installed version.

## Workspace flags

Most commands accept:

| Flag | Purpose |
|------|---------|
| `--dbfile` / `-d` | DuckDB catalog (default: `warcindex.db`) |
| `--data-dir` | Sidecar directory (default: `<dbfile stem>.data`) |

Keep the database and its data directory together. Paths in the catalog are
stored relative to the workspace whenever possible.

## Source arguments

`index` and `ingest` expand globs and recurse into directories for `*.warc` and
`*.warc.gz`:

```bash
metawarc index 'archives/**/*.warc*' --dbfile collection.db
metawarc index ./crawl-2024 --dbfile collection.db --resume
```

## Typed record filters

`list-files` (and related query surfaces) use allowlisted fields with bound
parameters:

```bash
metawarc list-files --dbfile collection.db \
  --mimes application/pdf \
  --exts pdf \
  --host-pattern example.com \
  --url-pattern /reports/ \
  --status-min 200 --status-max 299 \
  --date-from 2020-01-01 --date-to 2024-12-31 \
  --size-min 1024 --limit 50
```

`--sort-by` accepts `archive_id`, `warc_id`, `url`, `host`, `mime`, `ext`,
`status`, `date`, `size`, or `offset`. `--unsafe-where` is a trusted local CLI
escape hatch only; REST and MCP never accept raw SQL.

## Progress reporting

Long-running `index`, applied `ingest`, `index-content`, `dump`,
`dump-metadata`, `analyze hashes`, and deep `analyze integrity` operations show
progress automatically when stderr is an interactive terminal. Progress is
written to stderr; results stay on stdout.

Each covered command accepts `--progress` to force display and `--no-progress`
to disable it. `--silent`, dry-run ingestion, JSON output modes, JSON Lines
metadata written to stdout, and non-interactive auto mode suppress progress.
Unknown totals are shown as open-ended counters; Metawarc does not pre-scan a
WARC merely to calculate a progress total.

## Output formats

Many inspect and analysis commands accept `--output-format`:

| Command | Formats |
|---------|---------|
| `catalog`, `stats` | `table`, `json` |
| `list-files` | `table`, `csv`, `jsonl` |
| `analyze *` | `table`, `json`, `csv`, `parquet` |
| `index`, `ingest` | `human`, `json` |

See also: [CLI reference](/commands/), [performance](/getting-started/performance).
