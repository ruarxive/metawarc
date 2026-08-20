---
title: "Release checklist"
description: "Steps required before tagging a metawarc release"
---
# Release checklist

1. Confirm every shipped behavior has approved OpenSpec tasks and tests.
2. Run Ruff format/check, mypy, pytest with coverage, dependency audit, and SBOM generation.
3. Build wheel and source distribution from a clean checkout.
4. Install core, `api`, `mcp`, and `all` variants from the built wheel in isolated environments.
5. Run version/help, index/query/export, API startup, and MCP schema smoke tests.
6. Confirm package metadata, `metawarc.__version__`, changelog, and tag use the same version.
7. Review generated artifacts for workspace data, credentials, caches, and unrelated files.
8. Merge through review, tag the release as `vMAJOR.MINOR.PATCH`, sign the tag, and publish artifacts.
9. Verify the published artifact records the intended source commit and repeat smoke tests.

Release tags, version metadata, changelog, documentation, and artifacts must
originate from the same commit.
