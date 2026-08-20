---
title: "Troubleshooting"
description: "Common errors, workspace diagnostics, and extras"
---
# Troubleshooting

metawarc renders expected domain failures as concise CLI errors instead of raw
Python tracebacks. Use `metawarc doctor --dbfile collection.db` as the first
diagnostic for workspace problems.

## Common issues

### Missing optional extra

**Error:**
```
API/replay support requires `pip install metawarc[api]` or `metawarc[replay]`
MCP support requires `pip install metawarc[mcp]`
```

**Fix:** install the extra listed in [Installation](/getting-started/installation).
Core indexing and querying do not need `api` or `mcp`.

### Unsupported or unrecognized schema

A 2.0 workspace uses schema version 2. Newer schemas fail closed. Legacy 1.2/1.3
`files`/`tables` catalogs are detected on write: a `.legacy.bak` copy is made
and paths are imported when the layout is unambiguous. If migration cannot
proceed safely, `doctor` reports rebuild guidance instead of rewriting source
archives.

```bash
metawarc doctor --dbfile collection.db
```

### Moved WARC source

Archive identity is stable. Metawarc never silently guesses that a new path is
the same file. Rebind explicitly after independent verification:

```bash
metawarc rebind ARCHIVE_ID /new/path/site.warc.gz --dbfile collection.db
```

Use `--force` only after you have confirmed the fingerprint mismatch is expected.

### Non-loopback bind rejected

REST and MCP bind to loopback by default. Non-loopback REST requires
`METAWARC_API_TOKEN` / `--token` or `--allow-insecure`. Non-loopback MCP
requires `--allow-insecure`.

```bash
METAWARC_API_TOKEN='replace-me' metawarc serve --dbfile collection.db --host 0.0.0.0
```

### `--unsafe-where` is local CLI only

Raw SQL is available only on trusted local `list-files` and `dump`. REST and MCP
reject it. Never pass untrusted text to `--unsafe-where`.

### Export refused overwrite or path traversal

`dump` and `get` sanitize record IDs, write below the requested directory, and
refuse silent overwrite. Choose a new `--output` path or remove the existing
files after you have verified they are disposable.

### Doctor reports errors

```bash
metawarc doctor --dbfile collection.db
metawarc doctor --dbfile collection.db --repair          # dry-run repair plan
metawarc doctor --dbfile collection.db --repair --apply  # apply planned repairs
```

`--apply` requires `--repair`. Mutating recovery operations preview by default.

### Cleanup candidates

```bash
metawarc cleanup --dbfile collection.db                  # preview
metawarc cleanup --dbfile collection.db --apply          # remove previewed files
```

## Next steps

- [Doctor](/commands/doctor)
- [Workspace](/architecture/workspace)
- [Security](/architecture/security)
