---
title: "Best practices"
description: "Practical defaults for indexing, query, export, and servers"
---
# Best practices

## Index and store

- Treat source WARC files as immutable. Never point `--output` at the archive directory.
- Keep `--dbfile` and `--data-dir` together; move them as a pair.
- Prefer `index --resume` and `ingest --dry-run` over `index --mode force`.
- Run `doctor` after migration or a crashed writer.

## Query and export

- Use allowlisted filters (`--mimes`, `--exts`, `--url-pattern`, `--archive-ids`).
- Keep `--unsafe-where` off scripts and never expose it to untrusted input.
- Bound `dump` with `--limit` and `--max-bytes`; treat exported files as untrusted content.
- Do not open exported payloads automatically.

## Extraction and analysis

- Extract only the metadata types you need (`index-content --type pdfs`).
- `analyze metadata` reads stored envelopes; run `index-content` first.
- Hash payloads (`analyze hashes` or `index --hash-payloads`) before `analyze duplicates`.
- Keep extraction limits enabled; isolate untrusted parser workloads where practical.

## Servers

- Bind REST and MCP to loopback unless you have a token or an explicit insecure acknowledgement.
- Set `METAWARC_API_TOKEN` before exposing REST beyond loopback.
- Use `export-cdxj` plus pywb when you need Wombat/JavaScript fidelity.
- Archived scripts may be hostile; local HTML/CSS replay does not rewrite JavaScript.

## Releases and docs

- Keep core verbs (`index`, `catalog`, `list-files`, `dump`) stable in scripts; check `CHANGELOG.md` before pinning flags.
- Documented CLI examples should match the installed version; see [contributing](/development/contributing).
