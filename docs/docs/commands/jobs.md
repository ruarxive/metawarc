---
title: "metawarc jobs"
description: "Submit, observe, cancel, and prune durable batch jobs."
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
metawarc jobs --dbfile collection.db submit [--kind export-records]
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
`JobRequest` body the REST endpoint accepts. Formats, limits, filter names,
and filter ranges are validated before the job is persisted; invalid input
exits with a usage error and does not create a background failure.

## list

```
metawarc jobs --dbfile collection.db list [--status pending|running|succeeded|failed|cancelled]
                   [--limit N]
```

Lists jobs newest-first, bounded by `--limit` (default 50). The
`--status` filter accepts the documented lifecycle states.

## get

```
metawarc jobs --dbfile collection.db get <job_id>
```

Prints the full job document (id, kind, status, input, result,
error, timestamps, and `progress`) as JSON. `progress` is `null` when no
sidecar exists; otherwise it contains `processed_rows`, `total_rows`, and
`updated_at`. The total is the planned export size after offset and limit.
Exits 1 when no such job exists.

## wait

```
metawarc jobs --dbfile collection.db wait <job_id> [--poll-seconds 1] [--timeout 300]
                           [--progress|--no-progress]
```

Polls the local `<data_dir>/jobs/<job_id>.json` until the job
reaches a terminal state. With `--progress`, the shared renderer writes row
counts only to stderr; `--no-progress` disables them. Automatic mode renders
only for interactive stderr. Final job JSON remains on stdout. Exit codes:

| Code | Meaning |
|------|---------|
| 0 | Succeeded |
| 1 | Unknown job id |
| 2 | Cancelled |
| 3 | Failed (error message in `error`) |
| 124 | Timeout (mirrors `timeout(1)`) |

## cancel

```
metawarc jobs --dbfile collection.db cancel <job_id>
```

Marks the job `cancelled` and cancels the running task if a server
process is executing it. Exits 0 on success, 1 when the job id is
unknown, and exits non-zero when the job has already reached a
terminal state.

## metrics

```
metawarc jobs --dbfile collection.db metrics --limit 1000
```

Prints one read-only JSON observation of retained jobs without starting a runner
or scheduling pending work. `limit` selects the newest valid jobs by `created_at`
(job id breaks ties) and accepts 1–10,000 values; the default is 1,000. `total`
counts every valid retained job observed, `included` counts jobs contributing to
aggregates, and `truncated` is true when the limit excludes valid jobs. `invalid`
counts malformed, oversized, unreadable, non-regular, symlink, and structurally
invalid candidates separately from lifecycle statuses.

`counts` always includes `pending`, `running`, `succeeded`, `failed`, and
`cancelled`, and sums to `included`. Queue wait is `started_at - created_at`;
execution time is `ended_at - started_at` for terminal jobs. Each summary reports
`samples`, arithmetic `mean`, and `max` in seconds. Missing, naive, malformed, or
negatively ordered timestamp pairs are excluded only from the affected summary;
empty summaries have zero samples and null statistics. Each candidate read is
bounded to 1 MiB and aggregation memory is bounded by `limit`.

Pruned jobs disappear from later observations. Concurrent lifecycle updates are
not a cross-file transaction, so these are operational observations, not
all-time history, billing data, or audit records.

## prune

```
metawarc jobs --dbfile collection.db prune --retention-days N [--apply]
```

Previews expired terminal jobs by default; `--apply` is required for deletion.
Manual `--retention-days 0` selects every eligible terminal job. The JSON
report includes `dry_run`, `cutoff`, `candidates`, `deleted`, `skipped`, and
`remaining`, with job ids and skip reasons. Only terminal jobs with a valid
timezone-aware `ended_at` strictly older than the cutoff and an available
non-blocking claim are deleted. Negative, NaN, and infinite values are rejected.

Pruning removes only the lifecycle JSON, progress sidecar, known result and
staging files. It never follows persisted result paths or symlinks and leaves
unexpected directories/files untouched. Job and result routes return 404 after
deletion. Automatic cleanup is separately configured with
`METAWARC_JOB_RETENTION_DAYS` (default `0`, disabled); positive values run at
startup and every 60 seconds in batches of at most 50 jobs.