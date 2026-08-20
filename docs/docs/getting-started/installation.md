---
title: "Installation"
description: "Install metawarc with pip, extras, or from source"
---
# Installation

Python 3.10 or newer is required.

### Using pip

```bash
pip install metawarc              # core CLI
```

### Optional extras

Some features require optional dependencies, installed as extras. This is the
canonical list; feature sections elsewhere in the docs link back here.

| Extra | Enables |
|-------|---------|
| `api` | REST API (`metawarc serve`, FastAPI + uvicorn). Includes website replay routes. |
| `replay` | Same dependencies as `api`; documents replay intent. |
| `mcp` | MCP server (`metawarc mcp`, FastMCP) |
| `all` | REST API, replay, and MCP |
| `dev` | Contributor tools (pytest, ruff, mypy, build) |

```bash
pip install 'metawarc[api]'       # REST API (includes website replay routes)
pip install 'metawarc[replay]'    # same as api; documents replay intent
pip install 'metawarc[mcp]'       # MCP server
pip install 'metawarc[all]'       # all runtime interfaces
pip install -e '.[all,dev]'       # contributor checkout
```

After installation the `metawarc` command is available:

```bash
metawarc --version
metawarc --help
```

### Requirements

- Python 3.10 or greater
- Local WARC or WARC.GZ files; no network service is required for core indexing
  and querying

### Install from source

```bash
git clone https://github.com/ruarxive/metawarc.git
cd metawarc
python -m pip install --upgrade pip
python -m pip install -e '.[all,dev]'
```

## Next steps

- [Quick start](/getting-started/quick-start)
- [When to use metawarc](/getting-started/when-to-use)
- [Cookbook](/getting-started/cookbook)
