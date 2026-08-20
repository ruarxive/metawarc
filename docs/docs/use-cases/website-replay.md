---
title: "Website replay"
description: "Browse archived sites locally or export CDXJ for pywb"
---
# Website replay

Local Wayback-style replay is available through the REST server. JavaScript is
not rewritten. For full Wombat/JS fidelity, export CDXJ and point pywb at the
original WARCs.

## Start local replay

```bash
pip install 'metawarc[replay]'   # or metawarc[api]
metawarc serve --dbfile collection.db
# Home page:  http://127.0.0.1:8000/
# Replay URL: http://127.0.0.1:8000/replay/<YYYYMMDDHHMMSS>mp_/https://example.com/
metawarc replay --dbfile collection.db   # alias of serve
```

| Path | Purpose |
| --- | --- |
| `/` or `/replay` | HTML index of archived hosts with Open links |
| `/replay/sites` | JSON list of hosts, entry URLs, and replay paths |
| `/replay/<stamp>/<url>` | Closest exact-URL capture; HTML/CSS rewritten by default |
| `/replay/<stamp>mp_/<url>` | Explicit rewritten mode |
| `/replay/<stamp>id_/<url>` | Raw identity mode (no rewrite or banner) |

Capture selection uses the DuckDB catalog (exact URL, closest or exact
timestamp). Rewritten HTML/CSS keeps the original charset (UTF-8, windows-1251,
KOI8-R, and related declarations) and re-emits UTF-8 so Cyrillic and other
non-ASCII text render correctly. The home page prefers an `https://host/` 200
response over an `http://` redirect when both exist.

Archived scripts may be hostile; keep the default loopback bind unless you
configure a token or `--allow-insecure`.

## Export CDXJ for pywb

```bash
metawarc export-cdxj --dbfile collection.db -o collection.cdxj --path-index paths.tsv
```

See [`serve`](/commands/serve), [`export-cdxj`](/commands/export-cdxj), and
[replay integration](/integrations/replay).
