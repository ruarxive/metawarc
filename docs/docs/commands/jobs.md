---
title: "metawarc jobs"
description: "Submit, list, get, wait, and cancel durable batch jobs."
slug: /commands/jobs
---

# metawarc jobs

The `jobs` subcommand group is the local CLI mirror of the
authenticated `POST /jobs` REST endpoint. Job state lives in
`<data_dir>/jobs/<job_id>.json`; result files live in
`<data_dir>/jobs/<job_id>/result.<ext>`.

The `jobs` group shares the workspace's `--dbfile` and `--data-dir`
flags. Submitting a job writes the file immediately but does not
start execution; the `metawarc serve` process is what actually
consumes the queue. The `wait` subcommand polls the local file
system, so it works whether or not a server is running.

## submit

Submit a new batch job. Prints the new job id.

```
metawarc jobs submit [--kind export-records]
                     [--format json|csv|parquet]
                     [--limit N]
                     [--archive-ids <csv>] [--mimes <csv>] [--exts <csv>]
                     [--url-pattern <re>] [--host-pattern <re>]
                     [--status-min <n>] [--status-max <n>]
                     [--size-min <n>] [--size-max <n>]
```

The MVP registers a single `kind`: `export-records`, which
materialises the result of `metawarc list-files` to a JSON, CSV, or
Parquet file under `<data_dir>/jobs/<job_id>/`. The `format`,
`limit`, and `filters` flags map directly to the
`JobRequest` body the REST endpoint accepts.

## list

```
metawarc jobs list [--status pending|running|succeeded|failed|cancelled]
                   [--limit N]
```

Lists jobs newest-first, bounded by `--limit` (default 50). The
`--status` filter accepts the documented lifecycle states.

## get

```
metawarc jobs get <job_id>
```

Prints the full job document (id, kind, status, input, result,
error, timestamps) as JSON. Exits 1 when no such job exists.

## wait

```
metawarc jobs wait <job_id> [--poll-seconds 1] [--timeout 300]
```

Polls the local `<data_dir>/jobs/<job_id>.json` until the job
reaches a terminal state. Exit codes:

| Code | Meaning |
|------|---------|
| 0 | Succeeded |
| 1 | Unknown job id |
| 2 | Cancelled |
| 3 | Failed (error message in `error`) |
| 124 | Timeout (mirrors `timeout(1)`) |

## cancel

```
metawarc jobs cancel <job_id>
```

Marks the job `cancelled` and cancels the running task if a server
process is executing it. Exits 0 on success, 1 when the job id is
unknown, and exits non-zero when the job has already reached a
terminal state.