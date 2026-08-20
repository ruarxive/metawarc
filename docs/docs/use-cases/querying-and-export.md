---
title: "Querying and export"
description: "Find records with typed filters and export payloads safely"
---
# Querying and export

Find PDFs, hosts, or date ranges in an indexed collection and export selected
payloads with a checksum manifest.

## Inspect the catalog

```bash
metawarc catalog --dbfile collection.db
metawarc stats --dbfile collection.db --mode mimes
metawarc stats --dbfile collection.db --mode exts --output-format json
```

## List records

```bash
metawarc list-files --dbfile collection.db --mimes application/pdf --limit 50
metawarc list-files --dbfile collection.db --host-pattern example.com --date-from 2020-01-01
```

Normal filtering uses allowlisted fields and bound parameters. Raw SQL is
available only through the CLI's `--unsafe-where` option; it is not exposed by
REST or MCP.

## Export payloads

```bash
metawarc dump --dbfile collection.db --exts pdf --limit 100 --output exported
metawarc get '<urn:uuid:...>' --dbfile collection.db --output one.pdf
```

Payload exports sanitize record IDs, avoid overwrites, stream in source order,
enforce record/byte limits, and write a JSONL manifest with SHA-256 checksums.
Exported files remain untrusted content.

See [`list-files`](/commands/list-files), [`dump`](/commands/dump), [`get`](/commands/get),
and the [query model](/architecture/query).
