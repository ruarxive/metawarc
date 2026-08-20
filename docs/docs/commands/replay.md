---
title: "replay"
description: "metawarc replay command reference"
---
# `replay`

Alias for [`serve`](/commands/serve). Opens the same API with website replay
routes under `/replay/<YYYYMMDDHHMMSS[mp_|id_]>/<url>`.

```bash
pip install 'metawarc[replay]'
metawarc replay --dbfile collection.db
```

Options match `serve`: `--host`, `--port`, `--token` / `METAWARC_API_TOKEN`,
`--allow-insecure`.

See [website replay](/use-cases/website-replay).
