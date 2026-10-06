---
title: "index-content"
description: "metawarc index-content command reference"
---
# `index-content`

Build typed derived metadata indexes from catalog records. Optional source
arguments restrict extraction to matching archives; omit them to process the
whole catalog.

```bash
metawarc index-content --dbfile collection.db --type links --type pdfs
metawarc index-content --dbfile collection.db --type images --type videos --type audio --type fonts
metawarc index-content --dbfile collection.db --type ooxmldocs --rescan
# Populate the 'texts' sidecar for phrase search
metawarc index-content --dbfile collection.db --text
```

**`--type`** (repeatable, default `links`): `links`, `pdfs`, `images`,
`ooxmldocs`, `oledocs`, `videos`, `audio`, `fonts`.

**`--text`** (flag): also runs the text-extractor chain
(`TextExtractor` for HTML, `PdfTextExtractor` for PDF, `OoxmlTextExtractor`
for OOXML) and writes a `texts` Parquet sidecar with the
`(archive_id, warc_id, source, url, language, text)` schema. The
sidecar feeds [`search`](/commands/search),
[`/records/search`](/integrations/rest-api), and the
`search_records` MCP tool. Default off so structured extraction keeps
its current cost; pass `--text` to opt in.

**Options:**

- `--rescan` — rebuild even when a current sidecar exists
- `--batch-size` — default 1,000
- `--silent` / `-s`
- `--progress` / `--no-progress`

Output is JSON: one result object per requested type (`processed`, `skipped`,
`failed`), plus a `{kind: "texts", ...}` object when `--text` is set. The
command fails if any type or text run reports failures.

Extraction uses MIME, extension, and a short signature probe. ZIP/XML, payload
size, and time limits apply before a derived sidecar is published.

See [metadata and analysis](/use-cases/metadata-and-analysis) and
[Querying and export](/use-cases/querying-and-export) for the matching
workflows.