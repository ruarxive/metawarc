# Security policy

Report vulnerabilities privately through GitHub Security Advisories for
`ruarxive/metawarc`. Do not include credentials or private archive contents in
an issue.

Metawarc processes attacker-controlled archive metadata and payloads. Run it
with least filesystem privilege, keep extraction limits enabled, and isolate
untrusted parser workloads where practical. The API and MCP transports bind to
loopback by default. Configure `METAWARC_API_TOKEN` before exposing REST beyond
loopback; MCP currently requires explicit insecure acknowledgement for a
non-loopback transport.

Raw SQL is a trusted local CLI feature only. Never pass untrusted text to
`--unsafe-where`. Exports write below the requested directory, sanitize names,
refuse silent overwrite, and record checksums, but exported files remain
untrusted content and must not be opened automatically.

Supported security fixes target the latest 2.x release. Legacy 1.x installations
should be upgraded or isolated.
