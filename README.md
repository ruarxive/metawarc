# metawarc

A command-line tool and API for indexing, querying, and extracting metadata from WARC (Web ARChive) files.

metawarc (pronounced *me-ta-warc*) makes it easy to work with archived web content without manually parsing WARC files. Index once into DuckDB + Parquet sidecars, then list, filter, dump, or serve records through the CLI or REST API.

## Main features

- WARC indexing with DuckDB catalog and Parquet sidecars
- Metadata extraction for PDFs, Office documents, images, and HTML links
- Filter records by MIME type, extension, URL pattern, or SQL fragment
- REST API with ReDoc documentation and MCP server for agent integrations
- Low memory footprint and resumable re-indexing

## Supported file formats

| Category | Extensions |
|----------|------------|
| MS Office OLE | `.doc`, `.xls`, `.ppt` |
| MS Office XML | `.docx`, `.xlsx`, `.pptx` |
| Adobe PDF | `.pdf` |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.jp2` |
| HTML (links) | `.html`, and other HTML MIME types |

## Installation

```bash
pip install --upgrade pip setuptools
pip install --upgrade metawarc
```

For local development:

```bash
git clone https://github.com/ruarxive/metawarc.git
cd metawarc
pip install -e ".[dev]"
```

**Requirements:** Python 3.9+

## How it works

1. **`index`** — scan WARC files and build `warcindex.db` plus `data/*_records.parquet` and `data/*_headers.parquet`
2. **`index-content`** (optional) — extract typed metadata into additional Parquet tables (`_links`, `_pdfs`, `_images`, …)
3. **Query** — use `list-files`, `stats`, `dump`, `get`, or the HTTP API to explore and export data

```
sample.warc.gz  ──index──►  warcindex.db
                    └──►  data/<uuid>_records.parquet
                    └──►  data/<uuid>_headers.parquet
```

## Quickstart

Index a WARC file, inspect stats, and list PDFs:

```bash
# 1. Build the index
metawarc index sample.warc.gz

# 2. See what is in the archive
metawarc stats -m exts

# 3. List PDF records
metawarc list-files -e pdf

# 4. Export one file by URL
metawarc get "http://example.com/report.pdf" -o report.pdf
```

Index a whole directory of archives:

```bash
metawarc index 'archives/**/*.warc.gz' -o warcindex.db
```

## Usage examples

### Indexing

Index a single file to a custom database path:

```bash
metawarc index crawl-2024.warc.gz -o /data/crawl.db
```

Re-scan and overwrite existing Parquet sidecars:

```bash
metawarc index sample.warc.gz --rescan
```

Index quietly (no progress bars):

```bash
metawarc index '*.warc.gz' --silent
```

### Content metadata extraction

Extract links from all indexed WARC files:

```bash
metawarc index-content -t links
```

Extract PDF and image metadata for one archive:

```bash
metawarc index-content crawl-2024.warc.gz -t pdfs,images
```

Re-extract Office document metadata after a schema change:

```bash
metawarc index-content -t ooxmldocs,oledocs --rescan
```

### Statistics

MIME type breakdown:

```bash
metawarc stats -m mimes -d warcindex.db
```

Extension breakdown:

```bash
metawarc stats -m exts
```

### Listing records

All HTML pages:

```bash
metawarc list-files -m text/html
```

Spreadsheets by extension:

```bash
metawarc list-files -e xls,xlsx,csv
```

Large PDFs (SQL WHERE fragment):

```bash
metawarc list-files -q "ext = 'pdf' and content_length > 5000000"
```

Export the listing to CSV:

```bash
metawarc list-files -e pdf -o pdf_records.csv
```

Limit to specific WARC file IDs (from the `files` table in DuckDB):

```bash
metawarc list-files -w abc123def456 -m application/pdf
```

### Dumping payloads

Dump all ZIP files:

```bash
metawarc dump -m application/zip -o exports/zip
```

Dump images:

```bash
metawarc dump -e png,jpg,jpeg -o exports/images
```

Dump large PDFs:

```bash
metawarc dump -q "ext = 'pdf' and content_length > 10000000" -o exports/bigpdf
```

Each dump directory also contains `records.csv` with offsets, URLs, and WARC IDs.

### Exporting extracted metadata

PDF metadata as JSON Lines:

```bash
metawarc dump-metadata -t pdfs -o pdfs.jsonl
```

Image metadata for one WARC file:

```bash
metawarc dump-metadata -i 'crawl-2024.warc.gz' -t images -o images.jsonl
```

Print link metadata to stdout:

```bash
metawarc dump-metadata -t links
```

### Fetching a single record

By URL:

```bash
metawarc get "http://example.com/page.html" -o page.html
```

By WARC record ID:

```bash
metawarc get "<urn:uuid:...>" -o record.bin
```

## REST API

Start the server (default port **8000**):

```bash
metawarc serve --dbfile warcindex.db
# or
METAWARC_DB_PATH=warcindex.db metawarc serve --port 8000
```

Open [http://localhost:8000/](http://localhost:8000/) for interactive ReDoc documentation.

### API examples

List indexed WARC files:

```bash
curl http://localhost:8000/warcs/list
```

List HTML records (paginated):

```bash
curl 'http://localhost:8000/records/list?exts=html&limit=50'
```

Filter by URL substring:

```bash
curl 'http://localhost:8000/records/list?url_pattern=example.com&limit=10'
```

Get record metadata:

```bash
curl http://localhost:8000/records/get/<wf_id>/record/<record_id>
```

Get HTTP headers as JSON dict:

```bash
curl 'http://localhost:8000/records/get/<wf_id>/headers/<record_id>?mode=dict'
```

Download record payload:

```bash
curl -OJ http://localhost:8000/records/get/<wf_id>/data/<record_id>
```

## MCP server

Expose the API to MCP-compatible agents (default port **8191**):

```bash
metawarc mcp --dbfile warcindex.db --port 8191
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `METAWARC_DB_PATH` | `warcindex.db` | DuckDB index file for API/MCP |
| `METAWARC_PORT` | `8000` | REST API port |
| `METAWARC_MCP_PORT` | `8191` | MCP server port |
| `METAWARC_DEBUG` | `true` | Enable debug logging |
| `METAWARC_LOG_JSON` | `true` | Emit structured JSON logs |
| `METAWARC_TITLE` | `Metawarc API` | OpenAPI title |

## Command reference

| Command | Description |
|---------|-------------|
| `index` | Build DuckDB index and Parquet sidecars |
| `index-content` | Extract links, PDF, image, or Office metadata |
| `stats` | Print MIME or extension statistics |
| `list-files` | List matching records |
| `dump` | Export record payloads to disk |
| `dump-metadata` | Export extracted metadata as JSONL |
| `get` | Fetch a single record by URL or WARC ID |
| `serve` | Run the REST API server |
| `mcp` | Run the MCP server |

Run `metawarc <command> --help` for all flags.

## Development

```bash
pip install -e ".[dev]"
pytest
flake8 metawarc tests
```

## License

MIT — see [LICENSE](LICENSE).
