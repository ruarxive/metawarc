---
title: "get"
description: "metawarc get command reference"
---
# `get`

Export one payload by WARC record ID.

```bash
metawarc get '<urn:uuid:...>' --dbfile collection.db --output one.pdf
metawarc get '<urn:uuid:...>' --dbfile collection.db --archive-id ARCHIVE_ID
```

**Options:** `--archive-id` (disambiguate a repeated WARC record ID),
`--output` / `-o`, `--max-bytes`, `--silent` / `-s`.

Exits with an error if the record is not found. Paths are sanitized the same way
as [`dump`](/commands/dump).
