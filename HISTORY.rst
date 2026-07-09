.. :changelog:

History
=======

1.3.0 (2026-07-09)
------------------
* Fixed schema mismatches (``warcfile`` vs ``wf_id``/``wf_filename``) in dump and metadata export
* Fixed ``calc_stats`` empty output, CLI error messages, and indexer typos
* Added REST API and MCP server with proper HTTP errors and configurable DB path
* Consolidated CLI into a single command group; added ``--dbfile`` to list/dump/serve/mcp
* Added ``pyproject.toml``, complete dependency list, test suite, and GitHub Actions CI
* Fixed silent-mode indexing with current warcio (record offset/length)
* Removed unused legacy modules (SQLAlchemy models, analyzer, standalone MCP stub)
* Updated documentation for ``warcindex.db`` and server usage

1.2.0 (2022-07-26)
------------------
* Completely rewritten with DuckDB and parquet files to store metadata and pre-indexing WARC records


1.0.5 (2022-07-26)
------------------
* Added command headers to dump http headers from WARC records and coomand index to index WARC records


1.0.4 (2022-04-11)
------------------
* Better error handling. Added error messages and error flag. Added zero length file handling



1.0.1 (2020-05-10)
------------------
* First public release on PyPI and updated github code
