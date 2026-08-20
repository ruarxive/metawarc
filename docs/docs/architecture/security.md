---
title: "Security"
description: "Threat model, loopback defaults, and export safety"
---
# Security

Report vulnerabilities privately through GitHub Security Advisories for
`datacoon/metawarc`. Do not include credentials or private archive contents in
an issue. See also [`SECURITY.md`](https://github.com/datacoon/metawarc/blob/master/SECURITY.md)
in the repository.

## Threat model

Inputs may contain malicious record IDs, URLs, headers, compressed containers,
XML, parser payloads, and declared lengths. Callers may submit hostile query
values or disconnect during streaming. Controls include parameter binding,
allowlists, path sanitization, exclusive temporary files, bounded streaming,
parser limits, disabled XML entities/network access, authentication, loopback
defaults, request time/concurrency/page/byte limits, and deterministic cleanup.

MIME headers, URL extensions, and payload signatures can disagree. Extraction
combines those signals and applies payload, time, archive-member, expansion,
compression-ratio, XML, and network safety rules before a derived sidecar is
published.

## Runtime defaults

- Run with least filesystem privilege.
- Keep extraction limits enabled; isolate untrusted parser workloads where practical.
- API and MCP bind to loopback by default.
- Configure `METAWARC_API_TOKEN` before exposing REST beyond loopback.
- MCP currently requires explicit `--allow-insecure` for a non-loopback transport.
- Raw SQL is a trusted local CLI feature only.
- Exports write below the requested directory, sanitize names, refuse silent overwrite, and record checksums.
- Exported files remain untrusted content and must not be opened automatically.
- Website replay does not rewrite JavaScript; archived scripts may be hostile.

Supported security fixes target the latest 2.x release. Legacy 1.x installations
should be upgraded or isolated.
