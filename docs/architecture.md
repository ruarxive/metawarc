# Architecture and workspace schema

Metawarc separates immutable WARC sources from a small DuckDB catalog and
versioned Parquet sidecars. The `Workspace` owns schema checks, relative path
resolution, stable archive IDs, source fingerprints, catalog revisions,
single-writer locking, run manifests, checkpoints, and atomic sidecar switches.

The catalog contains `meta`, `catalog_state`, `archives`, `sidecars`, `runs`,
and `checkpoints`. Readers select only active sidecars registered in the
catalog; they never discover data by globbing directories. Writers create
bounded Parquet parts under `staging/`, validate and combine them, atomically
move the completed file into `sidecars/`, and update catalog membership in one
transaction. Old sidecars become retired only after the new files exist.

`QueryService` is the common read boundary. It resolves archive selection
through the catalog, compiles typed filters with bound values, allowlists sort
and aggregate expressions, and applies deterministic pagination. CLI stats,
listing/export, REST, MCP, analysis, and website replay use this service. Only
the trusted local CLI may opt into raw SQL.

Website replay mounts on `metawarc serve` under `/replay/<stamp>/<url>`. Capture
selection is exact-URL closest or exact timestamp. HTML/CSS rewriting is local;
CDXJ export (`metawarc export-cdxj`) is the interop contract for external pywb.

Metadata extraction uses a registry of bounded adapters. Selection combines
normalized MIME, extension, and a short signature probe. All outputs use a
stable envelope and Arrow schema. PDF, OOXML, image/OLE, and link adapters apply
payload, time, archive-member, expansion, compression-ratio, XML, and network
safety rules.

Analysis reports include catalog revision, analysis version, filters, limits,
timestamps, and partial failures. Hashes and other derived products are
cataloged sidecars and are retired when record sidecars are replaced.

## Migration

Opening a recognized legacy 1.2/1.3 `files`/`tables` catalog in write mode
creates a `.legacy.bak` copy and imports archive/sidecar paths into schema 2.
Unrecognized or newer schemas fail closed with guidance. Run `doctor` after
migration and retain the backup until a full query/export smoke test succeeds.

## Threat model

Inputs may contain malicious record IDs, URLs, headers, compressed containers,
XML, parser payloads, and declared lengths. Callers may submit hostile query
values or disconnect during streaming. Controls include parameter binding,
allowlists, path sanitization, exclusive temporary files, bounded streaming,
parser limits, disabled XML entities/network access, authentication, loopback
defaults, request time/concurrency/page/byte limits, and deterministic cleanup.
