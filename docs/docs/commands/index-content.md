---
title: "index-content"
description: "metawarc index-content command reference"
---
# `index-content`

Build typed derived metadata indexes from catalog records. Optional source
arguments restrict extraction to matching archives; omit them to process the
whole catalog.

```bash
metawarc index-content --dbfile collection.db --type links --type pdfs
metawarc index-content --dbfile collection.db --type images --type videos --type audio --type fonts
metawarc index-content --dbfile collection.db --type ooxmldocs --rescan
```

**`--type`** (repeatable, default `links`): `links`, `pdfs`, `images`,
`ooxmldocs`, `oledocs`, `videos`, `audio`, `fonts`.

**Options:**

- `--rescan` — rebuild even when a current sidecar exists
- `--batch-size` — default 1,000
- `--silent` / `-s`
- `--progress` / `--no-progress`

Output is JSON: one result object per requested type (`processed`, `skipped`,
`failed`). The command fails if any type reports failures.

Extraction uses MIME, extension, and a short signature probe. ZIP/XML, payload
size, and time limits apply before a derived sidecar is published.

See [metadata and analysis](/use-cases/metadata-and-analysis).
