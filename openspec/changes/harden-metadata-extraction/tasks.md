## 1. Extraction Contract
- [x] 1.1 Define extractor interface, registry, and selection result
- [x] 1.2 Define normalized MIME parsing and bounded signature probes
- [x] 1.3 Define versioned metadata envelope and stable error codes
- [x] 1.4 Define configurable soft limits and administrator hard limits

## 2. Extractor Migration
- [x] 2.1 Adapt PDF metadata extraction to the registry
- [x] 2.2 Adapt OOXML metadata extraction with safe ZIP/XML parsing
- [x] 2.3 Adapt Hachoir image and OLE extraction
- [x] 2.4 Adapt HTML link extraction or document its separate streaming contract
- [x] 2.5 Preserve raw parser output alongside normalized common fields

## 3. Resource Safety
- [x] 3.1 Prefer bounded streams for parsers that support them
- [x] 3.2 Add managed temporary paths for path-only parsers
- [x] 3.3 Remove temporary files in every normal, error, and interrupt path
- [x] 3.4 Enforce payload byte and extraction duration limits
- [x] 3.5 Enforce ZIP member, expanded-size, compression-ratio, and XML limits
- [x] 3.6 Disable XML external entities and network access

## 4. Persistence and Observability
- [x] 4.1 Define Arrow schema for stable envelope fields
- [x] 4.2 Write extraction results in bounded atomic batches
- [x] 4.3 Record warnings, failures, bytes inspected, and duration in summaries
- [x] 4.4 Version typed metadata sidecars and exports

## 5. Verification
- [x] 5.1 Test supported MIME, extension, and signature combinations
- [x] 5.2 Test mismatched MIME/extension behavior and warnings
- [x] 5.3 Test corrupt PDF, image, OLE, ZIP, and XML payloads
- [x] 5.4 Test ZIP bomb, oversized member, entity, and timeout limits
- [x] 5.5 Assert no temporary files remain after success, failure, or interrupt
- [x] 5.6 Measure bounded memory across multiple metadata batches

