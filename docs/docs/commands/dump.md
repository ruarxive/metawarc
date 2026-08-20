---
title: "dump"
description: "metawarc dump command reference"
---
# `dump`

Safely export selected payloads with a JSONL manifest.

```bash
metawarc dump --dbfile collection.db --exts pdf --limit 100 --output exported
metawarc dump --dbfile collection.db --mimes application/pdf --max-bytes 104857600 --output pdfs
```

**Selection:** `--archive-ids`, `--mimes` / `-m`, `--exts` / `-e`,
`--url-pattern`, `--unsafe-where` (local CLI only).

**Bounds:** `--offset` (default 0), `--limit` (default 1,000, max 100,000),
`--max-bytes`.

**Output:** `--output` / `-o` (directory, default `dump`). Names are sanitized;
silent overwrite is refused. The JSON summary includes counts of exported and
failed records plus the manifest path.

`--silent` / `-s` and `--progress` / `--no-progress` are available.

See [querying and export](/use-cases/querying-and-export).
