---
title: "When to use metawarc"
description: "metawarc vs pywb, warcio, CDX, and wget"
---
# When to use metawarc vs pywb vs warcio vs CDX

Evaluators often ask which tool to reach for. Short answer: **metawarc is an
operational index and analysis layer over local WARC collections**. Source
payloads stay in the original archives. Use other tools when you want their
specialized strengths.

| Need | Prefer |
|------|--------|
| Index, query, extract metadata, and analyze a local WARC collection | **metawarc** |
| Full Wayback-style replay with Wombat/JavaScript fidelity | **pywb** (export CDXJ from metawarc) |
| Parse or rewrite WARC records in Python | **warcio** (also used inside metawarc) |
| Capture-time CDX lookup without a catalog | **CDX/CDXJ** files |
| Fetch live websites into WARC | **wget --warc-file**, Browsertrix, or similar crawlers |
| Bounded local HTML/CSS replay from an existing index | **metawarc** (`serve` / `replay`) |
| Agent/MCP tooling over indexed metadata | **metawarc** (`mcp`) |

## metawarc strengths

- Versioned DuckDB catalog with Parquet sidecars and stable archive IDs
- Typed, parameterized queries shared by CLI, REST, and MCP
- Bounded metadata extraction (PDF, OOXML, images, video, audio, fonts, links)
- Collection analysis: summary, hashes, duplicates, links, integrity
- Local website replay plus CDXJ export for pywb interop
- Source WARC files remain immutable; interrupted writes do not publish incomplete sidecars

## When another tool wins

- **pywb**: full JS rewriting, Wombat, production Wayback UX
- **warcio**: library-level record iteration inside your own Python code
- **CDX**: capture-time indexes already maintained by a crawler
- **wget / Browsertrix**: creating WARCs, not querying them

## Related docs

- [Quick start](/getting-started/quick-start)
- [Website replay](/use-cases/website-replay)
- [Architecture](/architecture/workspace)
