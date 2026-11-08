# Change: Add authenticated batch-result download

## Why
A remote client can submit a job and read its state, but cannot retrieve
its JSON, CSV, or Parquet bytes without filesystem access. The current
REST responses expose an absolute server-local `result.path`, while the
batch specification incorrectly says that `/jobs/{id}/result` streams a
file. This blocks the submit → wait → download workflow in the product
improvement plan and leaks deployment details that remote clients cannot
use.

## What Changes
- Keep `GET /jobs/{id}/result` as the authenticated metadata endpoint and
  add `GET /jobs/{id}/result/content` as the authenticated download
  endpoint.
- Stream the completed artifact with bounded memory and a format-specific
  media type and safe attachment filename. Do not read the whole export
  into the server process.
- Resolve the expected artifact from the validated job id and registered
  export format, not from the persisted absolute path. Require a regular
  file confined to the owning job directory and reject symlinks or paths
  that resolve outside it.
- **BREAKING:** remove absolute local paths from REST job/result
  responses. Return a relative `download_url` such as
  `/jobs/<id>/result/content` instead.
- Preserve the internal job JSON and the standalone CLI's local
  `result.path`; only the remote representation changes. Document the
  response migration explicitly.
- Return 404 for an unknown job, 409 until the job succeeds, and 404 for
  a missing, invalid, or unsafe result artifact. Apply the existing
  bearer-token and loopback policy to both endpoints.
- Add executable download examples and update the API/specification
  contract without adding retention, deletion, range requests, or new job
  kinds.

## Migration
Remote clients must stop reading `path` from `GET /jobs/{id}`,
`GET /jobs`, and `GET /jobs/{id}/result`. For a succeeded job, read
`download_url` and issue an authenticated GET to that relative URL. CLI
users need no migration: `metawarc jobs get` and `jobs wait` continue to
report the local result path. Existing on-disk jobs and artifacts remain
usable without a schema or file migration.

## Impact
- Affected specs: `remote-batch-job`.
- Affected code: `metawarc/api_server.py`, `metawarc/api_models.py`, and
  result-resolution helpers in the batch-job module.
- Affected tests: REST success/auth/error responses, response privacy,
  traversal/symlink defenses, byte-for-byte JSON/CSV/Parquet downloads,
  and installed-wheel HTTP workflows.
- Compatibility: persisted job files and CLI output remain compatible;
  REST response location fields change as described above.

## Risks and Mitigations
- **Persisted JSON could be malformed or malicious.** Ignore its absolute
  path, use an allowlisted format and deterministic filename, and verify
  resolved containment before serving.
- **Large downloads could exhaust memory.** Use the framework's streaming
  file response and verify download behavior on a built wheel; never load
  the artifact into a response model.
- **Path replacement could break existing clients silently.** Mark the
  REST change as breaking, document exact old/new fields, and test every
  job-list/get/result representation for absence of local paths.
