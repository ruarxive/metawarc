---
title: "analyze"
description: "metawarc analyze command group reference"
---
# `analyze`

Run revision-scoped collection analysis. Shared options on every subcommand:
`--dbfile`, `--data-dir`, `--archive-ids`, `--output` / `-o`,
`--output-format` (`table`, `json` default, `csv`, `parquet`).

## `analyze summary`

Aggregate MIME, extension, status, host, date, and size dimensions.

```bash
metawarc analyze summary --dbfile collection.db --output summary.json
metawarc analyze summary --dbfile collection.db --dimension mime --dimension host --top 20
```

`--dimension` may be repeated: `mime`, `ext`, `status`, `host`, `date`,
`size_bucket`. Default is all six.

## `analyze metadata`

Analyze stored document, image, video, audio, and font metadata envelopes.
Run [`index-content`](/commands/index-content) first. Does not reopen source
WARC payloads.

```bash
metawarc analyze metadata --dbfile collection.db --type all
metawarc analyze metadata --dbfile collection.db --type pdfs --type images --top 20
```

`--type` may be repeated: `pdfs`, `images`, `ooxmldocs`, `oledocs`, `videos`,
`audio`, `fonts`, or `all`. Omitting `--type` or passing `--type all` covers
those seven types; `all` cannot be combined with an explicit type. Link sidecars
remain available through `analyze links`.

Each type reports extraction successes and errors, warning rows and occurrences,
raw and normalized metadata coverage, inspected bytes, duration, normalized
field coverage, and top title, creator, created, modified, and application
values.

## `analyze hashes`

Compute reusable streaming SHA-256 payload hashes.

```bash
metawarc analyze hashes --dbfile collection.db --resume
metawarc analyze hashes --dbfile collection.db --force --batch-size 1000
```

`--resume` defaults on. `--force` recomputes. `--progress` / `--no-progress`
are available.

## `analyze duplicates`

Group records with identical stored payload hashes. Run `analyze hashes` (or
`index --hash-payloads`) first.

```bash
metawarc analyze duplicates --dbfile collection.db --output duplicates.csv --output-format csv
```

## `analyze links`

Build normalized internal/external host-level link edges from stored link
sidecars.

```bash
metawarc analyze links --dbfile collection.db --output links.parquet --output-format parquet
```

## `analyze integrity`

Run fast workspace checks or bounded deep payload verification.

```bash
metawarc analyze integrity --dbfile collection.db
metawarc analyze integrity --dbfile collection.db --deep --max-records 1000
```

`--deep` reads payloads and verifies length/digest values. `--max-records`
defaults to 10,000. `--resume` defaults on. `--force` recomputes an existing
current integrity sidecar.

See [metadata and analysis](/use-cases/metadata-and-analysis).
