## Context

The current registry has one OOXML adapter, two broadly configured Hachoir
adapters, and a fixed set of five persisted metadata groups. Hachoir already
parses many binary image, audio, and video formats, but the registry neither
routes those formats nor distinguishes their signatures by group. SVG requires
safe XML parsing, and modern web-font containers require a font-aware parser.

The initial format matrix is:

- OOXML: `docx`, `docm`, `dotx`, `dotm`, `xlsx`, `xlsm`, `xltx`, `xltm`,
  `xlsb`, `pptx`, `pptm`, `ppsx`, `ppsm`, `potx`, `potm`, and `thmx`;
- images: `jpg`, `jpeg`, `jpe`, `png`, `gif`, `tif`, `tiff`, `jp2`, `j2k`,
  `bmp`, `dib`, `ico`, `cur`, `webp`, `svg`, `psd`, `xcf`, `pcx`, `tga`,
  `cr2`, `wmf`, and `emf`;
- video: `mp4`, `m4v`, `mov`, `3gp`, `3g2`, `avi`, `webm`, `mkv`, `ogv`,
  `mpeg`, `mpg`, `mpe`, `vob`, `ts`, `m2ts`, `mts`, `wmv`, `asf`, `flv`,
  `f4v`, `rm`, and `rmvb`;
- audio: `mp3`, `wav`, `wave`, `aif`, `aiff`, `aifc`, `au`, `snd`, `flac`,
  `ogg`, `oga`, `opus`, `m4a`, `wma`, `mid`, `midi`, `ra`, and `ram`;
- fonts: `ttf`, `otf`, `ttc`, `otc`, `woff`, `woff2`, and `eot`.

## Goals / Non-Goals

- Goals:
  - route common archived web media through explicit typed metadata groups;
  - extract format-native descriptive and technical metadata;
  - reject MIME/extension false positives through bounded family signatures;
  - retain the current stable envelope and resource-safety properties;
  - make the format matrix declarative and straightforward to extend.
- Non-Goals:
  - transcribe speech, recognize images, or extract full document/media content;
  - decode or transcode media;
  - guarantee metadata from malformed or encrypted payloads;
  - add archive-container recursion in this change.

## Decisions

### Decision: Persist three new metadata groups

Video, audio, and font results use `videos`, `audio`, and `fonts` sidecars.
Expanded OOXML and image formats remain in `ooxmldocs` and `images`. All groups
use the existing stable metadata envelope and are included by `--type all` in
content indexing and stored-metadata analysis.

### Decision: Use format-family adapters with explicit probes

Hachoir remains the primary adapter for binary image, audio, and video formats
it supports. Registry entries receive group-specific bounded signature probes
instead of sharing the current image/OLE probe. MIME and extension aliases are
declarative, but a recognized conflicting payload signature produces a warning
or rejection rather than silently parsing an HTML error response as media.

### Decision: Parse SVG as hostile XML

The SVG adapter uses the existing non-networked `lxml` configuration, rejects
DTD and entity declarations, applies the configured XML byte limit, and
extracts bounded root dimensions, `viewBox`, title, description, language,
creator/date metadata, and external-reference counts. It does not render SVG or
resolve referenced resources.

### Decision: Reuse OPC properties across OOXML variants

All supported OOXML extensions share the existing bounded ZIP validation and
`docProps/core.xml` / `docProps/app.xml` extraction. Package markers such as
`[Content_Types].xml` are checked so an arbitrary ZIP file is not classified as
OOXML solely because it begins with a ZIP signature.

### Decision: Add a font-aware adapter

FontTools reads SFNT, TrueType/OpenType collections, WOFF, and WOFF2 name and
header tables. The adapter normalizes family, subfamily, full name, PostScript
name, version, manufacturer, designer, copyright, trademark, license, units per
em, glyph count, and collection face count. EOT headers receive bounded
format-specific parsing when FontTools cannot open the container.

### Decision: Keep raw parser detail and normalize common fields

Raw Hachoir, SVG, and FontTools results remain in `metadata_json`. Existing
normalization maps common title, creator, producer, creation/modification date,
duration, dimensions, codecs, font identity, and copyright fields into
`normalized_json` without discarding parser-specific values.

## Risks / Trade-offs

- Broad extension support can select error pages or mislabeled payloads.
  Mitigation: use group-specific signatures and treat recognizable HTML as a
  conflicting signal.
- Media files can be large and malformed. Mitigation: retain payload,
  temporary-file, and duration limits and isolate every parser failure.
- Font decompression may consume disproportionate resources. Mitigation: keep
  the same temporary-byte and deadline limits and rely on bounded WOFF/WOFF2
  decompression in FontTools.
- Some uncommon formats accepted by Hachoir may expose sparse metadata.
  Mitigation: record empty recognized results distinctly from failures and test
  the primary formats in each family.

## Migration Plan

1. Add declarative MIME/extension/signature families and adapters.
2. Register `videos`, `audio`, and `fonts` as content-index and analysis types.
3. Add the FontTools dependency and update package-lock data.
4. Add fixtures, integration tests, and documentation.
5. Existing workspaces opt in by running `index-content` for the new or expanded
   types; no base record or catalog migration is required.

## Open Questions

- None. The format matrix above defines the initial compatibility boundary.
