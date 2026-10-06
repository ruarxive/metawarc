---
title: "Querying and export"
description: "Find records with typed filters, search full text, and export payloads safely"
---
# Querying and export

Find PDFs, hosts, or date ranges in an indexed collection, search extracted
text, and export selected payloads with a checksum manifest.

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

## Phrase-search extracted text

```bash
# one-off: populate the texts sidecar
metawarc index-content --dbfile collection.db --text

# then search
metawarc search "Welcome to the museum" --dbfile collection.db --limit 25
```

The same workflow is reachable through MCP
(`search_records(phrase="...", limit=50)`) and the REST API
(`GET /records/search?phrase=<text>&limit=<n>`). Search runs a bounded
DuckDB columnar scan over the `texts` Parquet sidecar; DuckDB's FTS
extension regressed in 1.5.x so a columnar scan is the dependable backend.

## Export payloads

```bash
metawarc dump --dbfile collection.db --exts pdf --limit 100 --output exported
metawarc get '<urn:uuid:...>' --dbfile collection.db --output one.pdf
```

Payload exports sanitize record IDs, avoid overwrites, stream in source order,
enforce record/byte limits, and write a JSONL manifest with SHA-256 checksums.
Exported files remain untrusted content.

## Long-running exports as batch jobs

Exports that exceed a single HTTP timeout become durable batch jobs. The
MVP ships the `export-records` kind, which materialises the result of
`QueryService.list_records` to JSON, CSV, or Parquet under
`<data_dir>/jobs/<job_id>/`:

```bash
metawarc jobs submit --format csv --limit 50000 --mimes application/pdf
# -> job-XXXXXXXXXXXXXXXX
metawarc jobs wait job-XXXXXXXXXXXXXXXX
```

See [`list-files`](/commands/list-files), [`dump`](/commands/dump),
[`get`](/commands/get), [`search`](/commands/search),
[`jobs`](/commands/jobs), and the [query model](/architecture/query).