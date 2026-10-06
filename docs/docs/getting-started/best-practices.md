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
- For phrase search, populate the `texts` sidecar once
  (`metawarc index-content --text`) and refresh with `--rescan` after
  new WARCs are added. The search backend is a bounded DuckDB columnar
  scan over the `texts` Parquet sidecar — DuckDB's FTS extension
  regressed in 1.5.x.

## Extraction and analysis

- Extract only the metadata types you need (`index-content --type pdfs`).
- `analyze metadata` reads stored envelopes; run `index-content` first.
- Hash payloads (`analyze hashes` or `index --hash-payloads`) before `analyze duplicates`.
- Keep extraction limits enabled; isolate untrusted parser workloads where practical.
- `index-content --text` writes the projection that powers `search`.
  Run it once after indexing; rerun with `--rescan` to refresh.

## Servers

- Bind REST and MCP to loopback unless you have a token or an explicit insecure acknowledgement.
- Set `METAWARC_API_TOKEN` before exposing REST beyond loopback.
- Use `export-cdxj` plus pywb when you need Wombat/JavaScript fidelity.
- Archived scripts may be hostile; local HTML/CSS replay does not rewrite JavaScript.

## Batch jobs

- For exports that exceed `METAWARC_REQUEST_TIMEOUT_SECONDS` (default 30 s),
  submit a `metawarc jobs submit` job instead of polling
  `GET /records/list`. The MVP kind is `export-records`; the result
  lands in `<data_dir>/jobs/<job_id>/`.
- The runner is shared between `POST /jobs` (HTTP) and `metawarc jobs
  submit` (CLI). Submitting from the CLI writes the file immediately;
  execution waits for `metawarc serve` to be running.
- Job state is plain JSON in `<data_dir>/jobs/`. Treat it like a local
  cache: monitor `doctor` and `cleanup` if you let jobs accumulate.
- Use `metawarc jobs wait` for scripts that should block until a job
  finishes; exit codes 0/1/2/3/124 match `succeeded` / unknown /
  cancelled / failed / timeout.

## Releases and docs

- Keep core verbs (`index`, `catalog`, `list-files`, `dump`) stable in scripts; check `CHANGELOG.md` before pinning flags.
- Documented CLI examples should match the installed version; see [contributing](/development/contributing).