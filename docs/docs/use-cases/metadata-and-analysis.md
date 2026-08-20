---
title: "Metadata and analysis"
description: "Extract typed metadata and run collection reports"
---
# Metadata and analysis

Extract document and media metadata from indexed records, then run
revision-scoped collection reports.

## Extract derived metadata

```bash
metawarc index-content --dbfile collection.db --type links --type pdfs
metawarc index-content --dbfile collection.db --type images --type videos --type audio --type fonts
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

See [`index-content`](/commands/index-content) and [`analyze`](/commands/analyze).
