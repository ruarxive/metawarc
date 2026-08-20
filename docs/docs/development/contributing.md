---
title: "Contributing"
description: "Development setup, tests, documentation, and OpenSpec"
---
# Contributing

Thank you for your interest in contributing to metawarc. Keep changes scoped,
add generated WARC fixtures rather than binary test archives, and do not commit
local databases, sidecars, credentials, or extracted payloads.

## Development setup

### Prerequisites

- Python 3.10 or higher
- Git
- Node.js 18+ (only if you are editing the documentation site)

### Installation

```bash
git clone https://github.com/ruarxive/metawarc.git
cd metawarc
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e '.[all,dev]'
```

## Code style

Before opening a pull request, run:

```bash
ruff format --check .
ruff check .
mypy metawarc
pytest --cov=metawarc --cov-report=term-missing
python -m build
```

Python code uses four-space indentation, LF endings, and UTF-8. New public
functions and service boundaries require type annotations.

## Tests

Use pytest with generated real `.warc` and `.warc.gz` fixtures. Cover unit,
integration, CLI, API/MCP security, packaging, migration, and bounded-memory
performance behavior. Every documented CLI example should be tested directly or
by an equivalent scenario. Source WARC files are immutable inputs; tests must
assert that index, export, and analysis do not alter them.

## Documentation

Edit markdown in `docs/docs/`. Follow existing frontmatter (`title`,
`description`). Preview with `cd docs && npm start`. Confirm `npm run build`
succeeds; broken links fail the build.

## OpenSpec

Behavior changes require an OpenSpec change under `openspec/changes/`.
Implementation tasks may be checked only after code, tests, and documentation
are complete. See `openspec/AGENTS.md`.
