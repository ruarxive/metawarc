#!/usr/bin/env python
# -*- coding: utf8 -*-
import glob
import logging
import os

import click
import uvicorn
from fastmcp import FastMCP
from hachoir.core import config as HachoirConfig

from metawarc import __version__, settings
from metawarc.cmds.dump import Dumper
from metawarc.cmds.indexer import Indexer
from metawarc.cmds.server import create_app

HachoirConfig.quiet = True


def enable_verbose():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )


@click.group()
@click.version_option(version=__version__)
def cli():
    """WARC indexing, querying, and extraction tool."""


@cli.command(name="index")
@click.argument("inputfile")
@click.option("--tofile", "-o", default="warcindex.db", show_default=True,
              help="Output DuckDB index file.")
@click.option("--update", "-u", is_flag=True, default=True, show_default=True,
              help="Update database index if it exists.")
@click.option("--rescan", "-r", is_flag=True, help="Rebuild/rescan metadata.")
@click.option("--silent", "-s", is_flag=True, help="Suppress progress output.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def warcindex(inputfile, tofile, update, rescan, silent, verbose):
    """Build DuckDB index and Parquet sidecars for WARC files."""
    if verbose:
        enable_verbose()
    if os.path.exists(tofile) and not update:
        print(f'Output database {tofile} already exists. Choose another file or use --update.')
        return
    files = glob.glob(inputfile.strip("'"))
    Indexer().index_records(files, tofile, ['records', 'headers'], rescan=rescan, silent=silent)


@cli.command(name="index-content")
@click.argument("inputfile", required=False, default=None)
@click.option("--tofile", "-o", default="warcindex.db", show_default=True,
              help="DuckDB index file.")
@click.option("--tables", "-t", default="links", show_default=True,
              help="Comma-separated tables: links, pdfs, images, ooxmldocs, oledocs.")
@click.option("--update", "-u", is_flag=True, default=True, show_default=True,
              help="Update database index if it exists.")
@click.option("--rescan", "-r", is_flag=True, help="Rebuild/rescan metadata.")
@click.option("--silent", "-s", is_flag=True, help="Suppress progress output.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def index_content(inputfile, tofile, tables, update, rescan, silent, verbose):
    """Extract typed metadata (links, PDFs, images, Office docs) into Parquet tables."""
    if verbose:
        enable_verbose()
    if os.path.exists(tofile) and not update:
        print(f'Output database {tofile} already exists. Choose another file or use --update.')
        return
    if inputfile:
        files = glob.glob(inputfile.strip("'"))
    else:
        files = None
    indexer = Indexer()
    for table in tables.split(','):
        indexer.index_by_table_type(files, tofile, table_type=table.strip(), rescan=rescan, silent=silent)


@cli.command(name="stats")
@click.option("--mode", "-m", default="mimes", show_default=True,
              help="Analysis mode: mimes or exts.")
@click.option("--dbfile", "-d", default="warcindex.db", show_default=True,
              help="DuckDB index file.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def stats(mode, dbfile, verbose):
    """Print MIME or extension statistics from the index."""
    if verbose:
        enable_verbose()
    Indexer().calc_stats(dbfile, mode)


@cli.command(name="list-files")
@click.option("--warcfileids", "-w", default=None, help="Comma-separated WARC file IDs.")
@click.option("--dbfile", "-d", default="warcindex.db", show_default=True,
              help="DuckDB index file.")
@click.option("--mimes", "-m", default=None, help="Comma-separated MIME types.")
@click.option("--exts", "-e", default=None, help="Comma-separated file extensions.")
@click.option("--query", "-q", default=None, help="SQL WHERE clause fragment.")
@click.option("--output", "-o", default=None, help="Output CSV file.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose output.")
def listfiles(warcfileids, dbfile, mimes, exts, query, output, verbose):
    """List records matching filters."""
    if verbose:
        enable_verbose()
    Dumper().listfiles(
        warcfileids=warcfileids, dbfile=dbfile, mimes=mimes, exts=exts,
        query=query, output=output,
    )


@cli.command(name="dump")
@click.option("--warcfiles", "-w", default=None, help="Comma-separated WARC file IDs.")
@click.option("--dbfile", "-d", default="warcindex.db", show_default=True,
              help="DuckDB index file.")
@click.option("--mimes", "-m", default=None, help="Comma-separated MIME types.")
@click.option("--exts", "-e", default=None, help="Comma-separated file extensions.")
@click.option("--query", "-q", default=None, help="SQL WHERE clause fragment.")
@click.option("--output", "-o", default='dump', show_default=True, help="Output directory.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def dump(warcfiles, dbfile, mimes, exts, query, output, verbose):
    """Dump record payloads to disk."""
    if verbose:
        enable_verbose()
    Dumper().dump(
        warcfiles=warcfiles, dbfile=dbfile, mimes=mimes, exts=exts,
        query=query, output=output,
    )


@cli.command(name="dump-metadata")
@click.option("--inputfiles", "-i", default=None, help="Glob of WARC files to filter.")
@click.option("--dbfile", "-d", default="warcindex.db", show_default=True,
              help="DuckDB index file.")
@click.option("--metadata-type", "-t", default="ooxmldocs", show_default=True,
              help="Metadata type: pdfs, images, ooxmldocs, oledocs, links.")
@click.option("--output", "-o", default=None, help="Output JSONL file (stdout if omitted).")
@click.option("--silent", "-s", is_flag=True, help="Suppress progress output.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def dump_metadata(inputfiles, dbfile, metadata_type, output, silent, verbose):
    """Export indexed metadata as JSON lines."""
    if verbose:
        enable_verbose()
    if not os.path.exists(dbfile):
        print(f'Database {dbfile} not found. Please index WARC files before dumping.')
        return
    files = glob.glob(inputfiles) if inputfiles else None
    Indexer().dump_metadata(files, dbfile, metadata_type=metadata_type, output=output, silent=silent)


@cli.command(name="get")
@click.argument("fileid")
@click.option("--dbfile", "-d", default="warcindex.db", show_default=True,
              help="DuckDB index file.")
@click.option("--output", "-o", default=None, help="Output file (stdout if omitted).")
@click.option("--silent", "-s", is_flag=True, help="Suppress progress output.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def get(fileid, dbfile, output, silent, verbose):
    """Extract a single record by warc_id or URL."""
    if verbose:
        enable_verbose()
    if not os.path.exists(dbfile):
        print(f'Database {dbfile} not found. Please index WARC files before dumping.')
        return
    Dumper().get_file(fileid, dbfile, output=output, silent=silent)


@cli.command(name="serve")
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind address.")
@click.option("--port", "-p", default=None, type=int, help="Port (default: METAWARC_PORT or 8000).")
@click.option("--dbfile", "-d", default=None, help="DuckDB index file (default: METAWARC_DB_PATH).")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def serve(host, port, dbfile, verbose):
    """Run the Metawarc REST API server."""
    if verbose:
        enable_verbose()
    if dbfile:
        settings.DB_PATH = dbfile
    bind_port = port or settings.PORT
    config = uvicorn.Config(
        create_app(),
        host=host,
        port=bind_port,
        log_level="info",
    )
    uvicorn.Server(config).run()


@cli.command(name="mcp")
@click.option("--host", default="0.0.0.0", show_default=True, help="Bind address.")
@click.option("--port", "-p", default=None, type=int, help="Port (default: METAWARC_MCP_PORT or 8191).")
@click.option("--dbfile", "-d", default=None, help="DuckDB index file (default: METAWARC_DB_PATH).")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def mcp(host, port, dbfile, verbose):
    """Run the Metawarc MCP server (wraps the REST API)."""
    if verbose:
        enable_verbose()
    if dbfile:
        settings.DB_PATH = dbfile
    app = create_app()
    bind_port = port or settings.MCP_PORT
    server = FastMCP.from_fastapi(app=app)
    server.run(transport="http", host=host, port=bind_port)
