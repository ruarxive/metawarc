# Change: Harden and modularize metadata extraction

## Why
Metadata extraction currently creates permanent temporary files, reads complete
payloads without limits, uses broad exception handling, and parses OOXML ZIP/XML
content without decompression safeguards. Extractor selection also relies on
inconsistent MIME and extension handling and returns heterogeneous metadata
without a versioned envelope.

## What Changes
- Introduce an extractor registry with one interface per content group
- Normalize MIME values and combine MIME, extension, and optional magic bytes
- Return a versioned metadata envelope with warnings, metrics, and stable errors
- Enforce payload, decompression, member-count, XML, and duration limits
- Guarantee temporary-resource cleanup on every exit path
- Write typed metadata in bounded batches with stable base fields
- Isolate parser failures to individual records and preserve error evidence

## Impact
- Affected specs: `metadata-extraction`
- Affected code: extractor, content indexer, MIME constants, Parquet schemas,
  temporary-file helpers, logging, configuration
- Dependencies: `stabilize-index-workspace`

