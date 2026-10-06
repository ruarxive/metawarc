---
title: "Indexing collections"
description: "Build and refresh a versioned WARC index workspace"
---
# Indexing collections

Build a resumable index of a WARC collection without copying payloads. Source
archives stay immutable; the DuckDB catalog and Parquet sidecars are the
operational index.

## First index

```bash
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc catalog --dbfile collection.db
metawarc doctor --dbfile collection.db
```

`add`, `update`, `rescan`, and `force` are explicit `index --mode` values.
Default mode is `update`. Changed archives retain their stable catalog ID.

## Incremental ingest

Preview classification before writing:

```bash
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --dry-run
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --resume
```

A moved source is reported as a candidate and requires
`metawarc rebind ARCHIVE_ID NEW_PATH`. Metawarc never silently guesses identity.

## Optional payload hashes at index time

```bash
metawarc index archives --dbfile collection.db --resume --hash-payloads
```

Hashes are cataloged sidecars and can also be computed later with
`analyze hashes`.

## Optional text sidecar for phrase search

```bash
metawarc index-content --dbfile collection.db --text
```

Runs the text-extractor chain (`TextExtractor` for HTML,
`PdfTextExtractor` for PDF, `OoxmlTextExtractor` for OOXML) and writes
the `texts` Parquet sidecar that feeds `metawarc search`,
`GET /records/search`, and the `search_records` MCP tool. Default off so
structured extraction keeps its current cost.

See [`index`](/commands/index-records), [`ingest`](/commands/ingest),
[`index-content`](/commands/index-content), and
[workspace layout](/architecture/workspace).