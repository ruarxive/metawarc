---
title: "stats"
description: "metawarc stats command reference"
---
# `stats`

Summarize indexed records by MIME type or extension.

```bash
metawarc stats --dbfile collection.db --mode mimes
metawarc stats --dbfile collection.db --mode exts --output-format json
```

**`--mode` / `-m`:** `mimes` (default) or `exts`.
**`--output-format`:** `table` or `json`.
