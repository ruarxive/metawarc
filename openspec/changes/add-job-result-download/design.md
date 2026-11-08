# Design: Authenticated result download

## Contract
The resource splits metadata from content:

- `GET /jobs/{id}/result` returns `job_id`, `status`, `format`, `rows`,
  `size`, and `download_url`;
- `GET /jobs/{id}/result/content` returns the artifact bytes;
- a succeeded job embedded in `GET /jobs/{id}` or `GET /jobs` carries the
  same `download_url` inside its `result` mapping instead of `path`;
- pending/running/failed/cancelled jobs have no downloadable result and
  both result routes return 409 (unknown ids remain 404).

`download_url` is root-relative so responses do not depend on Host header
construction or reverse-proxy configuration. It contains only the already
validated job id and fixed route suffix.

The local CLI deliberately differs in this one representation: it reads
on-disk job JSON and keeps the useful absolute `result.path`. The
specification must no longer claim byte-for-byte identical CLI and REST
result-location fields.

## Artifact resolution
The API must not open `job.result["path"]`. A shared resolver derives the
artifact from:

1. the validated job id;
2. the succeeded job's allowlisted format (`json`, `csv`, `parquet`);
3. the deterministic `result.<ext>` filename returned by `JobStore` under
   `<data_dir>/jobs/<id>/`.

Both the unresolved job directory and final candidate are resolved before
checking containment. The candidate must be a regular file, must remain
inside the owning directory, and must not be a symlink. Missing files,
unknown formats, directories, escaping paths, and symlinks produce the
same 404 error without exposing a filesystem location. The resolver is
used by metadata and content endpoints so metadata cannot advertise an
artifact that the content route would reject.

The persisted `size` is not trusted for HTTP framing. Metadata and the
file response use the validated file's actual size. Persisted `rows` and
`format` remain job metadata, with `format` constrained by the same
allowlist.

## Streaming response
Use the framework's asynchronous file response rather than `read_bytes()`
or an in-memory JSON/CSV/Parquet conversion. It supplies content length
and incrementally sends the file. The explicit mapping is:

- JSON: `application/json`;
- CSV: `text/csv; charset=utf-8`;
- Parquet: `application/vnd.apache.parquet`.

The attachment filename is derived from the validated id and fixed suffix,
for example `metawarc-<job_id>.csv`; no persisted path or user-provided
filename enters `Content-Disposition`. Responses include
`Cache-Control: no-store` because archive exports can be sensitive.

This slice does not add ranges, resumable downloads, compression
negotiation, retention, or deletion. The existing request/authentication
middleware and trace IDs apply normally.

## Compatibility
On-disk job JSON remains the source of local state and retains `path` for
CLI use. REST adapters project a sanitized copy and never mutate the
stored object. Old succeeded jobs already use the deterministic artifact
layout, so they can be downloaded without rewriting state.

Removing `path` from REST responses is intentionally breaking rather than
leaving a misleading empty or repurposed field. API documentation,
OpenAPI models, examples, and changelog must show `download_url` and the
additional authenticated request.

## Verification
Tests cover:

- exact bytes and media types for all three formats, including parsing
  downloaded Parquet without touching the source path;
- 401 for missing/wrong tokens and successful authorized downloads;
- 404 unknown job/artifact, 409 for every non-succeeded state;
- no `path` or absolute local location in list/get/metadata responses;
- absolute external path injection, `..` traversal, wrong suffix,
  directory, and symlink rejection without serving external content;
- completed old-format persisted jobs without rewriting JSON;
- CLI output compatibility and all existing job lifecycle tests;
- a real installed-wheel server workflow from submit through download,
  including a 50 000-row artifact and bounded streaming behavior.
