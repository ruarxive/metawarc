# Metawarc

Metawarc indexes WARC collections into a versioned DuckDB catalog with Parquet
sidecars, then provides bounded tools for querying, exporting payloads,
extracting metadata, and analyzing collections. Source archives are always
treated as immutable.

The 2.0 implementation replaces filename-derived tables and whole-archive
buffers with stable archive IDs, explicit workspace metadata, batched writes,
atomic publication, and typed queries shared by the CLI, REST API, and MCP
server.

## Documentation

The full documentation site (Docusaurus) lives in [`docs/`](docs/) and is
published at **[datacoon.github.io/metawarc](https://datacoon.github.io/metawarc/)**.

| Section | What it covers |
|---------|----------------|
| [Getting started](https://datacoon.github.io/metawarc/getting-started/installation) | Install, quick start, positioning |
| [Cookbook](https://datacoon.github.io/metawarc/getting-started/cookbook) | Task index by role |
| [CLI reference](https://datacoon.github.io/metawarc/commands/) | Every command |
| [Architecture](https://datacoon.github.io/metawarc/architecture/workspace) | Workspace schema, query model, security |
| [REST / replay / MCP](https://datacoon.github.io/metawarc/integrations/rest-api) | Optional interfaces |
| [Troubleshooting](https://datacoon.github.io/metawarc/getting-started/troubleshooting) | Diagnostics and common errors |

Source pages: [`docs/docs/`](docs/docs/). Changelog: [`CHANGELOG.md`](CHANGELOG.md).
Contributor workflow: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Install

Python 3.10 or newer is required.

```bash
pip install metawarc              # core CLI
pip install 'metawarc[api]'       # REST API (includes website replay routes)
pip install 'metawarc[replay]'    # same as api; documents replay intent
pip install 'metawarc[mcp]'       # MCP server
pip install 'metawarc[all]'       # all runtime interfaces
pip install -e '.[all,dev]'       # contributor checkout
```

## Quick start

```bash
metawarc index 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc catalog --dbfile collection.db
metawarc stats --dbfile collection.db --mode mimes
metawarc list-files --dbfile collection.db --mimes application/pdf
metawarc dump --dbfile collection.db --exts pdf --limit 100 --output exported
```

The default sidecar directory for `collection.db` is `collection.data`. It may
be relocated with `--data-dir`. Catalog paths are stored relative to that
workspace whenever possible, so moving the database and its data directory
together remains supported.

## Website replay

Local Wayback-style replay is available through the REST server:

```bash
pip install 'metawarc[replay]'   # or metawarc[api]
metawarc serve --dbfile collection.db
# Home page:  http://127.0.0.1:8000/
# Replay URL: http://127.0.0.1:8000/replay/<YYYYMMDDHHMMSS>mp_/https://example.com/
metawarc replay --dbfile collection.db   # alias of serve
metawarc export-cdxj --dbfile collection.db -o collection.cdxj --path-index paths.tsv
```

| Path | Purpose |
| --- | --- |
| `/` or `/replay` | HTML index of archived hosts with Open links |
| `/replay/sites` | JSON list of hosts, entry URLs, and replay paths |
| `/replay/<stamp>/<url>` | Closest exact-URL capture; HTML/CSS rewritten by default |
| `/replay/<stamp>mp_/<url>` | Explicit rewritten mode |
| `/replay/<stamp>id_/<url>` | Raw identity mode (no rewrite or banner) |

Capture selection uses the DuckDB catalog (exact URL, closest or exact
timestamp). Rewritten HTML/CSS keeps the original charset (UTF-8, windows-1251,
KOI8-R, and related declarations) and re-emits UTF-8 so Cyrillic and other
non-ASCII text render correctly. The home page prefers an `https://host/` 200
response over an `http://` redirect when both exist.

JavaScript is not rewritten. For full Wombat/JS fidelity, export CDXJ and point
pywb at the original WARCs. Archived scripts may be hostile; keep the default
loopback bind unless you configure a token or `--allow-insecure`.

## Incremental operation and recovery

```bash
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --dry-run
metawarc ingest 'archives/**/*.warc*' --dbfile collection.db --resume
metawarc doctor --dbfile collection.db
metawarc doctor --dbfile collection.db --repair       # dry-run repair plan
metawarc doctor --dbfile collection.db --repair --apply
```

`add`, `update`, `rescan`, and `force` are explicit `index --mode` values.
Changed archives retain their stable catalog ID. A moved source is reported as
a candidate and requires `metawarc rebind ARCHIVE_ID NEW_PATH`; Metawarc never
silently guesses identity.

## Metadata and analysis

```bash
metawarc index-content --dbfile collection.db --type links --type pdfs
metawarc analyze summary --dbfile collection.db --output summary.json
metawarc analyze metadata --dbfile collection.db --type all --top 20
metawarc analyze hashes --dbfile collection.db --resume
metawarc analyze duplicates --dbfile collection.db --output duplicates.csv --output-format csv
metawarc analyze links --dbfile collection.db --output links.parquet --output-format parquet
metawarc analyze integrity --dbfile collection.db --deep --max-records 1000
```

Extraction uses MIME, extension, and bounded signature signals. Results include
a versioned envelope, normalized metadata, raw parser output, warnings, stable
error codes, inspected bytes, and duration. ZIP/XML, payload-size, and time
limits are applied before a derived sidecar is published.

Supported content families include Office Open XML documents, templates,
macro-enabled files, binary workbooks, and presentations (including PPSX); PDF;
GIF, SVG, WebP, icons, bitmap, camera, and editing images; common MP4/QuickTime,
AVI, WebM/Matroska, Ogg, MPEG, ASF/WMV, and FLV video; MP3, WAV, AIFF, FLAC,
Ogg/Opus, M4A, WMA, MIDI, and RealAudio; and TTF/OTF, font collections, WOFF,
WOFF2, and EOT fonts.

`analyze metadata` reads the stored extraction envelopes for PDF, image, OOXML,
OLE, video, audio, and font sidecars. `--type all` covers those seven types;
link metadata continues to use the dedicated `analyze links` report.

## Query and export safety

Normal filtering uses allowlisted fields and bound parameters. Raw SQL is
available only through the CLI's visibly named `--unsafe-where` option; it is
not exposed by REST or MCP. Payload exports sanitize record IDs, avoid
overwrites, stream in source order, enforce record/byte limits, and write a
JSONL manifest with SHA-256 checksums.

## REST API and MCP

```bash
METAWARC_API_TOKEN='replace-me' metawarc serve --dbfile collection.db
metawarc mcp --dbfile collection.db                    # stdio
metawarc mcp --dbfile collection.db --transport http  # loopback only by default
```

`serve` exposes the typed record API and the website replay routes described
above. Both network services bind to loopback by default. Non-loopback REST
binding requires a bearer token or an explicit `--allow-insecure`
acknowledgement. The MCP surface is read-only and contains no raw SQL,
filesystem-path, payload, or mutation tool. Non-loopback MCP transport requires
explicit acknowledgement.

See the [documentation site](https://datacoon.github.io/metawarc/) for
architecture, CLI reference, replay, and release guidance. Repository copies:
[security](SECURITY.md), [changelog](CHANGELOG.md), and
[contributing](CONTRIBUTING.md).

## Compatibility

- A 2.0 workspace uses schema version 2 and is opened only by compatible code.
- Legacy 1.2/1.3 catalogs with `files`/`tables` are detected. A backup is made
  before their paths are migrated into the versioned catalog.
- If a legacy layout cannot be migrated unambiguously, `doctor` reports rebuild
  guidance instead of rewriting source archives.

The canonical repository is <https://github.com/datacoon/metawarc>; `master` is
the release branch and feature work is integrated through reviewed pull
requests. Releases use signed `vMAJOR.MINOR.PATCH` tags.

## License

MIT. See [LICENSE](LICENSE).
