---
title: "list-files"
description: "metawarc list-files command reference"
---
# `list-files`

List indexed records using typed, parameterized filters.

```bash
metawarc list-files --dbfile collection.db --mimes application/pdf --limit 50
metawarc list-files --dbfile collection.db --host-pattern example.com --output-format jsonl
metawarc list-files --dbfile collection.db --sort-by date --descending --limit 20
```

**Filters:** `--archive-ids`, `--mimes` / `-m`, `--exts` / `-e`, `--url-pattern`,
`--host-pattern`, `--status-min` / `--status-max`, `--date-from` / `--date-to`,
`--size-min` / `--size-max`.

**Paging and sort:** `--offset` (default 0), `--limit` (default 100),
`--sort-by` (default `offset`), `--descending`.

**`--sort-by`:** `archive_id`, `warc_id`, `url`, `host`, `mime`, `ext`,
`status`, `date`, `size`, `offset`.

**Output:** `--output` / `-o`, `--output-format` `table` (default), `csv`, or
`jsonl`.

**`--unsafe-where`:** local-only raw SQL WHERE clause. REST and MCP never accept
this option. Never pass untrusted text.

See the [query model](/architecture/query).
