---
title: "Support"
description: "Where to get help, response targets, and the compatibility policy"
---
# Support

## Channels

| Channel | Use it for |
|---|---|
| [GitHub Discussions](https://github.com/ruarxive/metawarc/discussions) | Usage questions, workflow recipes, design discussions, cookbook contributions |
| [GitHub Issues](https://github.com/ruarxive/metawarc/issues) | Concrete bugs, reproducible failures, feature requests tied to documented behavior |
| [GitHub Security Advisories](https://github.com/ruarxive/metawarc/security/advisories) | Private vulnerability reports — see [security](/architecture/security) |

## What belongs where

- **"How do I index this WARC?"** → Discussion, or a recipe PR against
  [getting-started/cookbook](/getting-started/cookbook).
- **"Indexing fails with this error message."** → Issue with the smallest
  reproducible fixture.
- **"`unsafe_where` lets a remote caller read files."** → Security
  Advisory (private until disclosed).
- **"The replay home page is broken on Windows."** → Issue with the
  platform, Python version, and the exact failing URL.

## Response targets

The project is maintained by a single committer. Response times are
best-effort:

- Security Advisories: acknowledged within seven days.
- Issues with a reproducer: triaged within thirty days.
- Discussions: addressed as time allows.

## Compatibility policy

Supported releases follow [security](/architecture/security) and the
[release checklist](/development/release-checklist):

- Security fixes target the latest 2.x release.
- Legacy 1.x installations should be upgraded or isolated.

## Repository copies

- [SUPPORT.md](https://github.com/ruarxive/metawarc/blob/master/SUPPORT.md)
- [CODE_OF_CONDUCT.md](https://github.com/ruarxive/metawarc/blob/master/CODE_OF_CONDUCT.md)
- [CONTRIBUTING.md](https://github.com/ruarxive/metawarc/blob/master/CONTRIBUTING.md)