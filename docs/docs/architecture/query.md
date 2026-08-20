---
title: "Query model"
description: "Typed filters, allowlists, and the shared QueryService"
---
# Query model

`QueryService` is the common read boundary. It resolves archive selection
through the catalog, compiles typed filters with bound values, allowlists sort
and aggregate expressions, and applies deterministic pagination. CLI stats,
listing/export, REST, MCP, analysis, and website replay use this service. Only
the trusted local CLI may opt into raw SQL.

## Allowlisted filters

Record queries accept:

- `--archive-ids`
- `--mimes` / `--exts`
- `--url-pattern` / `--host-pattern` (case-insensitive substrings)
- `--status-min` / `--status-max`
- `--date-from` / `--date-to` (ISO-8601)
- `--size-min` / `--size-max`
- `--sort-by` (`archive_id`, `warc_id`, `url`, `host`, `mime`, `ext`, `status`, `date`, `size`, `offset`)
- `--descending`, `--offset`, `--limit`

## Unsafe SQL

`--unsafe-where` is a visibly named local CLI escape hatch on `list-files` and
`dump`. REST and MCP never accept it. Never pass untrusted text to this option.

## Analysis scope

Analysis reports include catalog revision, analysis version, filters, limits,
timestamps, and partial failures. Hashes and other derived products are
cataloged sidecars and are retired when record sidecars are replaced.

See [`list-files`](/commands/list-files) and the [REST API](/integrations/rest-api).
