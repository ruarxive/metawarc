---
title: "dump-metadata"
description: "metawarc dump-metadata command reference"
---
# `dump-metadata`

Export a derived metadata index as JSON Lines.

```bash
metawarc dump-metadata --dbfile collection.db --type links --output links.jsonl
metawarc dump-metadata --dbfile collection.db --type pdfs -o pdfs.jsonl
```

**`--type`:** `links`, `pdfs`, `images`, `ooxmldocs`, `oledocs`, `videos`,
`audio`, `fonts` (default `ooxmldocs`). Optional source arguments restrict
archives. `--output` / `-o` writes to a file; omitting it writes JSON Lines to
stdout (progress is then suppressed).

See [`index-content`](/commands/index-content).
