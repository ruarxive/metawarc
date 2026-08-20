---
title: "cleanup"
description: "metawarc cleanup command reference"
---
# `cleanup`

Preview or purge expired retired sidecars and interrupted staging files.

```bash
metawarc cleanup --dbfile collection.db
metawarc cleanup --dbfile collection.db --retention-days 7 --apply
```

Default is a dry-run preview. `--apply` removes the previewed candidates.
`--retention-days` defaults to 7.
