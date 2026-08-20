---
title: "export-cdxj"
description: "metawarc export-cdxj command reference"
---
# `export-cdxj`

Export CDXJ from the workspace catalog for external replay engines such as pywb.

```bash
metawarc export-cdxj --dbfile collection.db -o collection.cdxj --path-index paths.tsv
metawarc export-cdxj --dbfile collection.db -o collection.cdxj --archive-ids id1,id2 --output-format json
```

**`--output` / `-o`** is required. **`--path-index`** writes an optional
filename-to-absolute-path TSV for pywb `archive_paths`. **`--archive-ids`**
restricts the export.

See [website replay](/use-cases/website-replay).
