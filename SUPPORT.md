# Support

Thank you for using Metawarc. This document explains where to get help,
how to report problems, and how the project is maintained.

## Where to get help

| Channel | Use it for |
|---|---|
| [GitHub Discussions](https://github.com/ruarxive/metawarc/discussions) | Usage questions, workflow recipes, design discussions, cookbook contributions |
| [GitHub Issues](https://github.com/ruarxive/metawarc/issues) | Concrete bugs, reproducible failures, feature requests tied to a documented behavior |
| [GitHub Security Advisories](https://github.com/ruarxive/metawarc/security/advisories) | Private vulnerability reports — see [`SECURITY.md`](SECURITY.md) |

## What belongs where

- **"How do I index this WARC?"** → Discussion or a recipe PR.
- **"Indexing fails with this error message."** → Issue with the smallest
  reproducible fixture.
- **"Reading `metawarc.unsafe_where` lets a remote caller read files."** →
  Security Advisory (private until disclosed).
- **"The replay home page is broken on Windows."** → Issue with the
  platform, Python version, and exact failing URL.

## Response targets

The project is maintained by a single committer listed in
[`AUTHORS.md`](AUTHORS.md). Response times are best-effort:

- Security Advisories: acknowledged within seven days.
- Issues with a reproducer: triaged within thirty days.
- Discussions: addressed as time allows.

## Compatibility policy

Supported releases follow the rules in
[`SECURITY.md`](SECURITY.md) and
[`docs/development/release-checklist.md`](docs/development/release-checklist.md):

- Security fixes target the latest 2.x release.
- Legacy 1.x installations should be upgraded or isolated.

## Commercial support

The project does not currently offer a paid support tier. For commercial
preservation engagements, contact <ivan@begtin.tech>.

## Code of Conduct

All community spaces follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
Reports of unacceptable behavior go to <ivan@begtin.tech>.