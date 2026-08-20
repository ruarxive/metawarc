---
title: "doctor"
description: "metawarc doctor command reference"
---
# `doctor`

Validate workspace schema, sources, sidecars, and orphan files.

```bash
metawarc doctor --dbfile collection.db
metawarc doctor --dbfile collection.db --repair
metawarc doctor --dbfile collection.db --repair --apply
```

Prints a JSON report. `--repair` plans safe orphan-sidecar quarantine actions.
`--apply` applies that plan and **requires** `--repair`. The command exits
non-zero when the report is not `ok`.

See [troubleshooting](/getting-started/troubleshooting) and
[workspace](/architecture/workspace).
