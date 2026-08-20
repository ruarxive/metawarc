---
title: "Website replay"
description: "Local HTML/CSS replay routes on metawarc serve"
---
# Website replay

Website replay mounts on `metawarc serve` (and the `replay` alias). Capture
selection is exact-URL closest or exact timestamp. HTML/CSS rewriting is local;
CDXJ export is the interop contract for external pywb.

Requires `metawarc[api]` or `metawarc[replay]`.

```bash
pip install 'metawarc[replay]'
metawarc serve --dbfile collection.db
```

| Path | Behavior |
| --- | --- |
| `/` or `/replay` | HTML home listing archived hosts with replay links |
| `/replay/sites` | JSON list of hosts, entry URLs, and replay paths |
| `/replay/<YYYYMMDDHHMMSS>/<url>` | Closest exact-URL capture; HTML/CSS rewritten |
| `/replay/<YYYYMMDDHHMMSS>mp_/<url>` | Explicit rewritten mode |
| `/replay/<YYYYMMDDHHMMSS>id_/<url>` | Raw identity mode (no rewrite/banner) |

Redirects rewrite `Location` into the replay URL space. Scripts are not
rewritten. Charset-aware rewriting keeps UTF-8, windows-1251, KOI8-R, and
related declarations and re-emits UTF-8.

For full JS fidelity:

```bash
metawarc export-cdxj --dbfile collection.db -o collection.cdxj --path-index paths.tsv
```

See the [website replay use case](/use-cases/website-replay) and
[`export-cdxj`](/commands/export-cdxj).
