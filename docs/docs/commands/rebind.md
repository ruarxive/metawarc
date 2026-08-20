---
title: "rebind"
description: "metawarc rebind command reference"
---
# `rebind`

Explicitly bind a stable archive identity to a moved source path. Metawarc never
silently guesses identity.

```bash
metawarc rebind ARCHIVE_ID /new/path/site.warc.gz --dbfile collection.db
metawarc rebind ARCHIVE_ID /new/path/site.warc.gz --dbfile collection.db --force
```

`--force` accepts a mismatched fingerprint after independent verification.
