---
title: "index"
description: "metawarc index command reference"
---
# `index`

Build or update the record and header indexes for WARC sources.

```bash
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc index ./crawl --dbfile collection.db --mode update --batch-size 10000
metawarc index archives --dbfile collection.db --resume --hash-payloads --output-format json
```

**Arguments:** one or more files, globs, or directories (`*.warc`, `*.warc.gz`).

**Modes** (`--mode`, default `update`):

| Mode | Behavior |
|------|----------|
| `add` | Index sources that are not yet in the catalog |
| `update` | Reindex sources whose fingerprint changed |
| `rescan` | Re-evaluate sources even when size/mtime look unchanged |
| `force` | Reindex regardless of change detection |

**Options:**

- `--dbfile` / `-d` — DuckDB catalog (default `warcindex.db`)
- `--data-dir` — sidecar directory
- `--resume` / `--no-resume` — continue from checkpoints (default off)
- `--batch-size` — records per Parquet part (default 10,000)
- `--digest-fingerprint` — include source SHA-256 in change detection
- `--hash-payloads` — compute reusable SHA-256 payload hashes after indexing
- `--silent` / `-s`
- `--output-format` — `human` or `json`
- `--progress` / `--no-progress`

Changed archives retain their stable catalog ID. Failed sources make the command
exit non-zero after reporting the run summary.

See [indexing collections](/use-cases/indexing-collections) and [`ingest`](/commands/ingest).
