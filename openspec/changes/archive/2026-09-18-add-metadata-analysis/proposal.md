# Change: Add stored metadata analysis

## Why
Metawarc persists normalized extraction envelopes for PDF, image, OOXML, and
OLE records, but users can currently only dump those rows. They need a
revision-scoped summary of extraction quality and useful normalized values
without re-reading source WARC payloads.

## What Changes
- Add an `analyze metadata` command over registered metadata sidecars
- Allow repeatable `--type` selection for `pdfs`, `images`, `ooxmldocs`, and
  `oledocs`
- Add `--type all` as an exclusive shorthand for all four metadata types
- Report extraction totals, errors, warnings, stored metadata coverage, bytes
  inspected, and extraction duration for each selected type
- Report normalized field coverage and top values for title, creator, created,
  modified, and application fields
- Preserve archive filters, revision provenance, partial-failure reporting, and
  JSON, CSV, Parquet, and terminal output conventions

`links` is not included in `--type all` because link sidecars use a distinct
schema and are already analyzed by `analyze links`.

## Impact
- Affected specs: `collection-analysis`
- Affected code: analysis service, `analyze` CLI group, report rendering,
  documentation, and tests
- Data migration: none; analysis reads existing registered Parquet sidecars

