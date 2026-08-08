# Contributing

Use Python 3.10 or newer and install `pip install -e '.[all,dev]'`. Keep changes
scoped, add generated WARC fixtures rather than binary test archives, and do not
commit local databases, sidecars, credentials, or extracted payloads.

Before opening a pull request, run:

```bash
ruff format --check .
ruff check .
mypy metawarc
pytest --cov=metawarc --cov-report=term-missing
python -m build
```

Behavior changes require an OpenSpec change under `openspec/changes/`.
Implementation tasks may be checked only after code, tests, and documentation
are complete. Source WARC files are immutable inputs; tests must assert that
index, export, and analysis do not alter them.
