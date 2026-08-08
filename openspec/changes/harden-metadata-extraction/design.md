## Context

The current `processWarcRecord` function selects several parser families in one
method, writes payloads with `NamedTemporaryFile(delete=False)`, and never
removes them. PDF, OOXML, Hachoir, and link results have different structures.
The typed content indexer filters primarily by MIME and accumulates results for a
whole archive before writing Parquet.

## Goals / Non-Goals

- Goals:
  - make extractor selection predictable and extensible;
  - treat every WARC payload as untrusted input;
  - bound bytes, time, decompression, and memory;
  - preserve useful error and provenance information;
  - provide stable metadata fields while retaining extractor-specific detail.
- Non-Goals:
  - extract full document text or build a full-text index;
  - guarantee successful parsing of every malformed legacy format;
  - sandbox native parser libraries at the operating-system level in the first
    implementation.

## Decisions

### Decision: Registry-based extractor selection

Each extractor declares supported normalized MIME values, extensions, optional
signature probes, required input mode, and a result schema version. Selection
uses normalized MIME first, then extension, then bounded magic-byte probing when
enabled. Conflicts and mismatches are included as warnings.

### Decision: Stable result envelope

Every result contains archive ID, record ID, source URL, detected type, declared
MIME, extension, extractor name/version, metadata schema version, raw metadata,
normalized common fields, warnings, stable error code/message, bytes inspected,
and duration.

### Decision: Limits are checked before and during parsing

Global defaults can be overridden per extractor within hard administrator
limits. OOXML processing validates compressed/uncompressed sizes, member count,
member names, and XML size before parsing. XML parsing disables external entity
resolution and network access.

### Decision: Temporary files are scoped resources

Extractors use streams when supported. A parser that needs a path receives a
managed temporary path that is removed in `finally` after success, failure, or
interruption. Debug retention requires an explicit option and records the path.

### Decision: Metadata writes use bounded normalized batches

Stable envelope fields use fixed Arrow columns. Variable extractor output is
stored in a versioned JSON-compatible field or extractor-specific table. Batches
are published using the workspace atomic writer.

## Risks / Trade-offs

- Strict limits can skip unusually large valid documents. Mitigation: expose
  clear limit errors and controlled configuration.
- Magic-byte detection costs additional reads. Mitigation: keep probes small and
  configurable, and use them only when MIME/extension is missing or conflicting.
- Normalization can lose parser detail. Mitigation: retain raw metadata beside
  normalized fields.
- In-process timeouts cannot stop every native parser safely. Mitigation: design
  the interface so risky extractors can later move to isolated worker processes.

## Migration Plan

1. Define the envelope and stable error vocabulary.
2. Add registry adapters around current PDF, OOXML, Hachoir/image/OLE, and link
   implementations without changing output selection.
3. Add managed temporary resources and size/time limits.
4. Add safe OOXML ZIP/XML handling.
5. Switch typed indexing to bounded envelope batches.
6. Version new metadata sidecars and document legacy export compatibility.

## Open Questions

- Which normalized document fields are mandatory across formats?
- Should raw metadata be JSON text, Arrow struct, or extractor-specific tables?
- Which extractors require process isolation in a later security hardening change?
- Should link extraction share this registry or remain a streaming HTML pipeline?

