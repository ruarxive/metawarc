---
title: "Quick Start"
description: "Task-oriented first success paths for metawarc"
---
# Quick Start

Short task-oriented paths to first success. Not sure where to start? Pick your
role and goal in the [cookbook](/getting-started/cookbook). For the full
reference, see the [CLI index](/commands/).

## Index a collection in 30 seconds

```bash
pip install metawarc
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc catalog --dbfile collection.db
metawarc stats --dbfile collection.db --mode mimes
```

The default sidecar directory for `collection.db` is `collection.data`. Relocate
it with `--data-dir`. Catalog paths are stored relative to that workspace
whenever possible, so moving the database and its data directory together
remains supported.

## Query and export payloads

```bash
metawarc list-files --dbfile collection.db --mimes application/pdf
metawarc dump --dbfile collection.db --exts pdf --limit 100 --output exported
```

Exports write below the requested directory, sanitize names, refuse silent
overwrite, and record SHA-256 checksums in a JSONL manifest.

## Extract metadata, search, and analyze

```bash
metawarc index-content --dbfile collection.db --type links --type pdfs
metawarc index-content --dbfile collection.db --text        # populate texts sidecar
metawarc analyze summary --dbfile collection.db --output summary.json
metawarc analyze metadata --dbfile collection.db --type all --top 20
metawarc search "Welcome to the museum of modern art" --dbfile collection.db
```

`index-content --text` runs the text-extractor chain (`TextExtractor`
for HTML, `PdfTextExtractor` for PDF, `OoxmlTextExtractor` for OOXML) and
writes a `texts` Parquet sidecar that feeds `metawarc search`,
`GET /records/search`, and the `search_records` MCP tool.

## Replay archived websites locally

```bash
pip install 'metawarc[replay]'   # or metawarc[api]
metawarc serve --dbfile collection.db
# Home page:  http://127.0.0.1:8000/
# Replay URL: http://127.0.0.1:8000/replay/<YYYYMMDDHHMMSS>mp_/https://example.com/
```

## Long-running exports as batch jobs

```bash
# submit a job that materialises the filtered result set to CSV
metawarc jobs submit --format csv --limit 50000 --mimes application/pdf
# -> job-7f3a...

# wait for it
metawarc jobs wait job-7f3a...
```

The MVP ships the `export-records` job kind, which produces JSON, CSV,
or Parquet under `<data_dir>/jobs/<job_id>/`. Job state persists across
server restarts; concurrency is bounded by `METAWARC_JOB_MAX_CONCURRENT`
and per-job execution by `METAWARC_JOB_TIMEOUT`. The same workflow is
reachable through `POST /jobs` on `metawarc serve`.

## Incremental operation and recovery

```bash
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --dry-run
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc doctor --dbfile collection.db
```

## Next steps

- [Usage scenarios by role](/getting-started/cookbook)
- [When to use metawarc](/getting-started/when-to-use)
- [Workspace layout](/architecture/workspace)
- [Troubleshooting](/getting-started/troubleshooting)