---
title: "catalog"
description: "metawarc catalog command reference"
---
# `catalog`

List catalog archives, identities, source paths, and status.

```bash
metawarc catalog --dbfile collection.db
metawarc catalog --dbfile collection.db --output-format json
```

Table columns: `id`, `filename`, `status`, `num_records`, `source_path`. JSON
includes `revision` and `archives`.
