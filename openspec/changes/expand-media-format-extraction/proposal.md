# Change: Expand document and media metadata formats

## Why
Archived websites contain substantial metadata outside the currently supported
PDF, core OOXML, legacy Office, and limited image families. The Rosstat sample
contains valid PPSX presentations, GIF and SVG images, MP4 and AVI video, MP3
audio, and web fonts that are currently omitted from typed metadata sidecars.

## What Changes
- Extend OOXML extraction to presentation shows, templates, macro-enabled files,
  and the corresponding Word and spreadsheet package variants
- Extend image extraction to common raster, vector, icon, camera, and editing
  formats, including GIF, SVG, BMP, WebP, ICO, PSD, and XCF
- Add typed `videos`, `audio`, and `fonts` metadata groups with common web-format
  MIME aliases, extensions, and bounded signature probes
- Add a safe SVG metadata adapter and a font-specific adapter while reusing
  Hachoir for supported binary image, audio, and video containers
- Preserve the existing extraction envelope, limits, atomic sidecars, error
  isolation, and metadata-analysis behavior for every new group
- Add representative format fixtures, conflict/signature tests, CLI coverage,
  and user documentation

## Impact
- Affected specs: `metadata-extraction`, `collection-analysis`
- Affected code: MIME constants, extractor registry and adapters, content
  indexer, metadata analysis type selection, CLI choices, dependencies, tests,
  and documentation
- New dependency: FontTools with web-font support
- Existing workspaces remain compatible; users create the new sidecars by
  running content indexing for the added metadata groups
