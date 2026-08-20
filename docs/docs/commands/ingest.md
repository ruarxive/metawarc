---
title: "ingest"
description: "metawarc ingest command reference"
---
# `ingest`

Plan and apply incremental collection ingestion. Use `--dry-run` to classify
sources without creating or changing the workspace.

```bash
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --dry-run
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc ingest archives --dbfile collection.db --force --output-format json
```

**Options:**

- `--dry-run` — plan only
- `--resume` / `--no-resume` — default on
- `--force` — reindex unchanged sources too
- `--batch-size` — default 10,000
- `--digest-fingerprint`
- `--silent` / `-s`
- `--output-format` — `human` (table) or `json`
- `--progress` / `--no-progress`

Human output prints a table of `action`, `source`, `archive_id`, and `reason`.
A moved source is a candidate that requires [`rebind`](/commands/rebind).

Progress is suppressed for dry-run and JSON modes.

See [indexing collections](/use-cases/indexing-collections).
