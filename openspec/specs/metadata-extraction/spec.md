# metadata-extraction Specification

## Purpose
Extracts metadata from PDF, image, OOXML, OLE, video, audio, font, and link
families through a registry whose entries declare supported MIME values,
extensions, signature probes, and a versioned envelope. Extraction is
bounded by per-record byte, time, and format-specific expansion limits and
records warnings rather than aborting the archive on partial failure.
## Requirements
### Requirement: Extractor registry
The system SHALL select metadata extractors through a registry whose
entries declare supported MIME values, extensions, signature probes, and
schema version, and SHALL organize the registry as a small package of
per-format modules plus a single dispatch module.

#### Scenario: New extractor is registered
- **WHEN** an extractor implements the registry contract
- **THEN** it can be selected without adding format-specific branches to
  the WARC scanning service, and its implementation lives in a dedicated
  per-format file

### Requirement: Multi-signal content detection
Extractor selection SHALL normalize MIME parameters and case and SHALL combine
declared MIME, URL extension, and bounded signature detection according to a
documented precedence.

#### Scenario: MIME includes a charset parameter
- **WHEN** a supported MIME value includes parameters and mixed case
- **THEN** it is normalized and matched to the same extractor as its base MIME

#### Scenario: MIME and extension conflict
- **WHEN** MIME and extension indicate different supported formats
- **THEN** the documented precedence selects an extractor and the result records
  a mismatch warning

### Requirement: Versioned metadata envelope
Every extraction attempt SHALL return a versioned envelope containing
provenance, detected type, extractor identity, normalized metadata, raw metadata,
warnings, stable error state, bytes inspected, and duration.

#### Scenario: Parser returns no metadata
- **WHEN** a parser recognizes a format but finds no metadata
- **THEN** the envelope distinguishes an empty result from parser failure

### Requirement: Extraction resource limits
The extraction service SHALL enforce configured limits for payload bytes,
duration, temporary storage, and format-specific expansion before committing a
result.

#### Scenario: Payload exceeds byte limit
- **WHEN** a selected payload is larger than the configured extractor limit
- **THEN** parsing is skipped and the envelope records a stable limit-exceeded
  error without reading the complete payload

### Requirement: Safe archive and XML parsing
Container and XML extractors SHALL reject unsafe member paths, excessive member
counts or expansion, external entities, and network resolution.

#### Scenario: OOXML archive has excessive expansion
- **WHEN** declared or observed expanded content exceeds the configured limit
- **THEN** extraction stops before full expansion and records a container-limit
  error

### Requirement: Temporary resource cleanup
Temporary files and directories SHALL be removed after every extraction attempt
unless explicit debug retention is enabled.

#### Scenario: Parser raises an exception
- **WHEN** a path-based parser fails after a temporary file is created
- **THEN** the temporary file is removed before the error result is returned

### Requirement: Per-record failure isolation
An extraction failure SHALL NOT abort processing of unrelated records in the
same WARC when the archive reader can continue safely.

#### Scenario: Corrupt document is followed by a valid image
- **WHEN** document extraction fails and the next record is readable
- **THEN** the failure is recorded and image extraction still runs

### Requirement: Bounded metadata persistence
Extraction envelopes SHALL be written in bounded batches using stable base
columns and versioned handling for variable raw metadata.

#### Scenario: Archive contains many supported documents
- **WHEN** extraction spans multiple configured batches
- **THEN** completed batches are released and peak buffered result count remains
  within the documented bound

### Requirement: Expanded OOXML packages
The extraction service SHALL extract bounded core and application properties
from supported OOXML document, template, macro-enabled, binary-workbook,
presentation-show, and theme packages.

#### Scenario: PPSX is served as generic binary data
- **WHEN** a valid PPSX package has an `application/octet-stream` MIME value and
  a `.ppsx` extension
- **THEN** the OOXML extractor validates the package and returns its core and
  application properties in an `ooxmldocs` envelope

#### Scenario: Arbitrary ZIP uses an OOXML-like extension
- **WHEN** a ZIP payload lacks required OPC package markers
- **THEN** the OOXML extractor records a format error instead of treating the
  archive as a valid Office document

### Requirement: Expanded image metadata
The extraction service SHALL extract metadata from the declared raster, vector,
icon, camera, and editing image formats using bounded family-specific adapters.

#### Scenario: GIF image is indexed
- **WHEN** a valid GIF payload is selected by MIME, extension, or GIF signature
- **THEN** its dimensions, color and compression properties, format version,
  and available descriptive metadata are stored in an `images` envelope

#### Scenario: SVG metadata is indexed safely
- **WHEN** a valid SVG payload is within the configured XML limits
- **THEN** its dimensions, view box, title, description, language, embedded
  metadata, and reference counts are extracted without resolving entities or
  external resources

### Requirement: Video metadata extraction
The extraction service SHALL provide a `videos` metadata group for supported
MP4/QuickTime, AVI, WebM/Matroska, Ogg, MPEG, transport-stream, ASF/WMV, FLV,
and RealMedia variants and aliases.

#### Scenario: Archived MP4 is indexed
- **WHEN** a valid MP4 payload is selected
- **THEN** available duration, dimensions, frame rate, bit rate, codecs,
  stream details, producer, and embedded dates are stored in a versioned
  `videos` envelope

### Requirement: Audio metadata extraction
The extraction service SHALL provide an `audio` metadata group for supported
MP3, WAV, AIFF, AU, FLAC, Ogg/Opus, MP4 audio, WMA, MIDI, and RealAudio variants
and aliases.

#### Scenario: MP3 uses a nonstandard MIME alias
- **WHEN** a valid MP3 payload is declared as `audio/x-mp3`
- **THEN** available tags, duration, channels, sample rate, bit rate, compression,
  and format version are stored in a versioned `audio` envelope

### Requirement: Font metadata extraction
The extraction service SHALL provide a `fonts` metadata group for TTF, OTF,
TrueType/OpenType collections, WOFF, WOFF2, and EOT fonts.

#### Scenario: Web font is indexed
- **WHEN** a valid WOFF or WOFF2 payload is selected
- **THEN** available family, subfamily, names, version, vendor, copyright,
  license, metrics, glyph count, and collection information are stored in a
  versioned `fonts` envelope

### Requirement: Family-specific signature validation
Binary media and font extractors SHALL use bounded signatures specific to their
format family and SHALL record conflicting MIME, extension, and signature
signals.

#### Scenario: Image URL returns HTML
- **WHEN** an image extension is paired with a payload whose bounded prefix is
  recognizable HTML and whose declared MIME is `text/html`
- **THEN** the system does not parse the payload as an image and records the
  conflict in the extraction evidence

### Requirement: Extractor package layout
The metadata extraction service SHALL be organized as a small registry
package plus per-format modules so that no single extractor module
exceeds a documented size budget.

#### Scenario: A new format family is added
- **WHEN** a contributor adds a new format family
- **THEN** the new extractor lives in its own per-format module under
  `metawarc/extractor/`, and the registry module grows by no more than
  the size of the registration entry

#### Scenario: An extractor module grows too large
- **WHEN** an extractor module under `metawarc/extractor/` exceeds
  500 lines of Python
- **THEN** the contributor splits the module before adding new
  functionality

### Requirement: Backward-compatible extractor imports
The pre-rename public symbols `metawarc.cmds.extractor.ContentIndexer`
and related entry points SHALL remain importable from their original
paths for one release cycle after the registry package is introduced.

#### Scenario: A downstream caller imports `metawarc.cmds.extractor`
- **WHEN** a third-party script imports
  `from metawarc.cmds.extractor import ContentIndexer` after the rename
- **THEN** the import resolves to the new `metawarc.extractor`
  implementation and the call site behaves identically

### Requirement: Plain-text sidecar
The metadata-extraction service SHALL extract a script-free, tag-free text
projection of HTML responses into a `texts` Parquet sidecar when the
caller opts in.

#### Scenario: HTML indexing with text extraction enabled
- **WHEN** a user runs `metawarc content-index ... --text`
- **THEN** the workspace produces a `texts` sidecar whose rows match
  the HTML responses and carry `archive_id`, `warc_id`, `source`,
  `url`, `language`, and `text` columns

#### Scenario: HTML indexing with text extraction disabled
- **WHEN** a user runs `metawarc content-index ...` without the flag
- **THEN** no `texts` sidecar is written and the existing
  `links` sidecar is unaffected

### Requirement: Plain-text projection for PDF and OOXML
The metadata-extraction service SHALL project a bounded plain-text blob
for PDF and OOXML payloads, alongside the existing HTML projection,
into the shared `texts` sidecar.

#### Scenario: PDF payload with extractable content
- **WHEN** a user runs `metawarc content-index --text` over an archive
  containing a PDF record
- **THEN** the `texts` sidecar carries the concatenated page text
  truncated at `ExtractionLimits.max_payload_bytes`

#### Scenario: OOXML payload with extractable content
- **WHEN** a user runs `metawarc content-index --text` over an archive
  containing an OOXML record
- **THEN** the `texts` sidecar carries the joined paragraph text from
  `word/document.xml`, truncated at `ExtractionLimits.max_payload_bytes`

#### Scenario: PDF payload with no extractable text
- **WHEN** a PDF contains only image scans
- **THEN** the `texts` sidecar carries an empty `text` field for that
  record and indexing continues for the other records

### Requirement: Text sidecar population
The metadata-extraction service SHALL populate the `texts` sidecar when
the caller opts in via the `metawarc content-index --text` flag, by
running the text-extractor chain (`TextExtractor`, `PdfTextExtractor`,
`OoxmlTextExtractor`) and writing one row per record.

#### Scenario: HTML archive indexed with `--text`
- **WHEN** a user runs `metawarc content-index --text sample.warc`
- **THEN** the workspace produces a `texts` sidecar whose rows carry
  `archive_id`, `warc_id`, `source`, `url`, `language`, and `text`
  for every HTML response record

#### Scenario: PDF archive indexed with `--text`
- **WHEN** a user runs `metawarc content-index --text` over an archive
  containing a PDF record
- **THEN** the `texts` sidecar carries the concatenated page text for
  that record

#### Scenario: Default indexing without `--text`
- **WHEN** a user runs `metawarc content-index` without the flag
- **THEN** no `texts` sidecar is written; existing structured-metadata
  sidecars are unchanged

### Requirement: Per-record text budget
The text extractor SHALL respect the existing
`ExtractionLimits.max_payload_bytes` ceiling and SHALL emit an empty
`text` field for payloads that exceed the limit rather than aborting
the archive.

#### Scenario: HTML payload exceeds the budget
- **WHEN** a single HTML response is larger than the configured
  per-record byte limit
- **THEN** the row is still written with an empty `text` field and a
  warning, and indexing continues for the remaining records

