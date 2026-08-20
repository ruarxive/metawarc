---
title: "Workspace and schema"
description: "DuckDB catalog, Parquet sidecars, identity, and migration"
---
# Workspace and schema

Metawarc separates immutable WARC sources from a small DuckDB catalog and
versioned Parquet sidecars. The `Workspace` owns schema checks, relative path
resolution, stable archive IDs, source fingerprints, catalog revisions,
single-writer locking, run manifests, checkpoints, and atomic sidecar switches.

## Layout

The default sidecar directory for `collection.db` is `collection.data`. Relocate
it with `--data-dir`. Catalog paths are stored relative to that workspace
whenever possible, so moving the database and its data directory together remains
supported.

A 2.0 workspace uses **schema version 2** and is opened only by compatible code.

The catalog contains `meta`, `catalog_state`, `archives`, `sidecars`, `runs`,
and `checkpoints`. Readers select only active sidecars registered in the
catalog; they never discover data by globbing directories. Writers create
bounded Parquet parts under `staging/`, validate and combine them, atomically
move the completed file into `sidecars/`, and update catalog membership in one
transaction. Old sidecars become retired only after the new files exist.

Archive filenames are not unique collection identifiers; duplicate basenames in
different directories are valid. Identity is a stable catalog ID plus source
fingerprints.

## Migration

Opening a recognized legacy 1.2/1.3 `files`/`tables` catalog in write mode
creates a `.legacy.bak` copy and imports archive/sidecar paths into schema 2.
Unrecognized or newer schemas fail closed with guidance. Run `doctor` after
migration and retain the backup until a full query/export smoke test succeeds.
If a legacy layout cannot be migrated unambiguously, `doctor` reports rebuild
guidance instead of rewriting source archives.

```bash
metawarc doctor --dbfile collection.db
```

See [`doctor`](/commands/doctor), [`rebind`](/commands/rebind), and
[`cleanup`](/commands/cleanup).
