---
title: "Metadata and analysis"
description: "Extract typed metadata, populate the texts sidecar, and run collection reports"
---
# Metadata and analysis

Extract document and media metadata from indexed records, optionally
populate the `texts` sidecar for phrase search, and run revision-scoped
collection reports.

## Extract derived metadata

```bash
metawarc index-content --dbfile collection.db --type links --type pdfs
metawarc index-content --dbfile collection.db --type images --type videos --type audio --type fonts
metawarc index-content --dbfile collection.db --type ooxmldocs --rescan
```

`--type` may be repeated. Valid types: `links`, `pdfs`, `images`, `ooxmldocs`,
`oledocs`, `videos`, `audio`, `fonts`. Extraction uses MIME, extension, and
bounded signature signals. Results include a versioned envelope, normalized
metadata, raw parser output, warnings, stable error codes, inspected bytes, and
duration.

Supported families include Office Open XML documents, templates, macro-enabled
files, binary workbooks, and presentations (including PPSX); PDF; GIF, SVG,
WebP, icons, bitmap, camera, and editing images; common MP4/QuickTime, AVI,
WebM/Matroska, Ogg, MPEG, ASF/WMV, and FLV video; MP3, WAV, AIFF, FLAC,
Ogg/Opus, M4A, WMA, MIDI, and RealAudio; and TTF/OTF, font collections, WOFF,
WOFF2, and EOT fonts.

## Populate the texts sidecar for phrase search

Add `--text` to opt in to the text-extractor chain (`TextExtractor` for HTML,
`PdfTextExtractor` for PDF, `OoxmlTextExtractor` for OOXML). The run
appends a `{kind: "texts", ...}` entry to the JSON output, writes a
`(archive_id, warc_id, source, url, language, text)` Parquet sidecar, and
feeds [`metawarc search`](/commands/search),
[`/records/search`](/integrations/rest-api), and the `search_records` MCP
tool:

```bash
metawarc index-content --dbfile collection.db --text
metawarc search "Welcome to the museum of modern art" --dbfile collection.db
```

## Collection reports

```bash
metawarc analyze summary --dbfile collection.db --output summary.json
metawarc analyze metadata --dbfile collection.db --type all --top 20
metawarc analyze hashes --dbfile collection.db --resume
metawarc analyze duplicates --dbfile collection.db --output duplicates.csv --output-format csv
metawarc analyze links --dbfile collection.db --output links.parquet --output-format parquet
metawarc analyze integrity --dbfile collection.db --deep --max-records 1000
```

`analyze metadata` reads stored extraction envelopes. `--type all` covers PDF,
image, OOXML, OLE, video, audio, and font sidecars; link metadata uses
`analyze links`.

`analyze summary` and `analyze metadata` are also exposed to MCP clients as
`collection_stats` and `metadata_summary`; see
[Agents and MCP](/use-cases/agents-and-mcp).

See [`index-content`](/commands/index-content), [`analyze`](/commands/analyze),
and [`search`](/commands/search).