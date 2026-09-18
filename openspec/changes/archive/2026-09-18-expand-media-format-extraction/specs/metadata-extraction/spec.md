## ADDED Requirements

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
