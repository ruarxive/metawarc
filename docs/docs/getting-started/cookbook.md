---
title: "Cookbook"
description: "Pick a role and goal, then follow verified metawarc commands"
---
# Cookbook

metawarc covers indexing, query, extraction, analysis, and replay. This page is a
task-oriented index: find the row that sounds like you, then follow the linked
reference. If you are completely new, do the
[quick start](/getting-started/quick-start) first.

| You are a… | You want to… | Start with |
|------------|--------------|------------|
| [Web archivist](/use-cases/indexing-collections) | Build a resumable index of a WARC collection without copying payloads | `index`, `ingest`, `catalog`, `doctor` |
| [Researcher / journalist](/use-cases/querying-and-export) | Find PDFs, hosts, or date ranges and export selected payloads | `stats`, `list-files`, `dump`, `get` |
| [Preservation engineer](/use-cases/metadata-and-analysis) | Extract document metadata, hashes, duplicates, and integrity evidence | `index-content`, `analyze` |
| [Replay operator](/use-cases/website-replay) | Browse archived sites locally or feed pywb | `serve`, `replay`, `export-cdxj` |
| [Application developer](/integrations/rest-api) | Expose a read-only typed API over an index | `serve`, REST `/records/list` |
| [AI / automation builder](/use-cases/agents-and-mcp) | Give agents controlled metadata tools | `mcp` |

## Detailed walkthroughs

- [Indexing collections](/use-cases/indexing-collections)
- [Querying and export](/use-cases/querying-and-export)
- [Metadata and analysis](/use-cases/metadata-and-analysis)
- [Website replay](/use-cases/website-replay)
- [Agents and MCP](/use-cases/agents-and-mcp)
