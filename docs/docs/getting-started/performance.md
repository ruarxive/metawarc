---
title: "Performance"
description: "Bounded batches, large collections, and progress"
---
# Performance and large collections

metawarc is designed so indexing memory stays bounded as record count grows.
Source WARC files are never loaded whole into memory. Writers create bounded
Parquet parts under `staging/`, validate them, then publish atomically.

## Recommended flags

```bash
# Resume interrupted indexing; skip unchanged sources in update mode
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume

# Smaller record batches if memory is tight (default 10_000)
metawarc index archives --dbfile collection.db --batch-size 2000 --resume

# Preview incremental work before writing
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --dry-run

# Bound payload export volume
metawarc dump --dbfile collection.db --exts pdf --limit 1000 --max-bytes 104857600 --output exported
```

## Notes

- Indexing uses `--batch-size` (default 10,000 records) for Parquet parts.
- Content extraction uses a smaller default batch (1,000) because parsers are heavier.
- Interrupted writes stay in `staging/` and are not registered as complete sidecars.
- `doctor` reports orphans; `cleanup` previews retired/staging files (requires `--apply` to remove).
- Progress is automatic on interactive stderr; `--no-progress` or `--silent` disables it.
- Website replay streams payloads with a configured byte cap; it is not a bulk export path.

## Performance tips

1. **Index once, query many times**: the catalog is the expensive step; `list-files` and `stats` are cheap.
2. **Resume**: pass `--resume` so a crashed run continues from checkpoints.
3. **Incremental ingest**: use `ingest --dry-run` then `ingest --resume` instead of `index --mode force`.
4. **Filter early**: restrict `--mimes`, `--exts`, `--archive-ids`, and `--limit` before `dump`.
5. **Extract only needed types**: `index-content --type pdfs` is cheaper than extracting every family.
6. **Keep workspace local**: DuckDB and Parquet sidecars should live on fast local disk next to the catalog.
7. **Do not pre-scan for progress**: unknown totals are shown as counters; Metawarc will not read a WARC twice just to compute a percentage.

See also: [Indexing collections](/use-cases/indexing-collections), [Workspace](/architecture/workspace).
