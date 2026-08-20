---
title: "CLI Reference"
description: "Index of metawarc CLI commands"
slug: /commands
---

# CLI Reference

All commands are available as `metawarc <command>`. Use
`metawarc <command> --help` for the live flag list of the installed version.

Shared workspace commands accept `--dbfile` and `--data-dir`. Query values use
bound parameters. Only local `list-files` and `dump` accept the visibly unsafe
`--unsafe-where` escape hatch. Mutating recovery operations preview by default
and require `--apply` where removal is involved.

## Index and ingest

| Command | Page |
|---------|------|
| `index` | [`/commands/index-records`](/commands/index-records) |
| `ingest` | [`/commands/ingest`](/commands/ingest) |
| `index-content` | [`/commands/index-content`](/commands/index-content) |

## Inspect

| Command | Page |
|---------|------|
| `catalog` | [`/commands/catalog`](/commands/catalog) |
| `stats` | [`/commands/stats`](/commands/stats) |
| `list-files` | [`/commands/list-files`](/commands/list-files) |
| `doctor` | [`/commands/doctor`](/commands/doctor) |

## Export

| Command | Page |
|---------|------|
| `dump` | [`/commands/dump`](/commands/dump) |
| `get` | [`/commands/get`](/commands/get) |
| `dump-metadata` | [`/commands/dump-metadata`](/commands/dump-metadata) |
| `export-cdxj` | [`/commands/export-cdxj`](/commands/export-cdxj) |

## Analysis

| Command | Page |
|---------|------|
| `analyze` | [`/commands/analyze`](/commands/analyze) |

## Maintenance

| Command | Page |
|---------|------|
| `rebind` | [`/commands/rebind`](/commands/rebind) |
| `cleanup` | [`/commands/cleanup`](/commands/cleanup) |

## Interfaces

| Command | Extra | Page |
|---------|-------|------|
| `serve` | `api` or `replay` | [`/commands/serve`](/commands/serve) |
| `replay` | `api` or `replay` | [`/commands/replay`](/commands/replay) |
| `mcp` | `mcp` | [`/commands/mcp`](/commands/mcp) |

Global flags: `--verbose` / `-v`, `--version`, `-h` / `--help`.
