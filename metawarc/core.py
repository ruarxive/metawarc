"""Metawarc command-line interface."""

from __future__ import annotations

import glob
import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, TypeVar

import click

from . import __version__
from .analysis import STORED_METADATA_TYPES, AnalysisReport, AnalysisService, write_report
from .cmds.dump import Dumper
from .cmds.extractor import ContentIndexer
from .cmds.indexer import Indexer
from .errors import MetawarcError
from .ingestion import IncrementalIngestor
from .progress import ProgressEvent, RichProgressRenderer, resolve_progress
from .query import QueryService, RecordQuery
from .replay import export_cdxj
from .settings import ServerSettings, is_loopback
from .workspace import Workspace, canonical_path

try:  # Hachoir is noisy unless explicitly quieted.
    from hachoir.core import config as HachoirConfig

    HachoirConfig.quiet = True
except ImportError:  # Optional when only the query/API surfaces are installed.
    pass

F = TypeVar("F", bound=Callable[..., Any])


class MetawarcGroup(click.Group):
    """Render expected domain failures as concise CLI errors."""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except (MetawarcError, OSError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc


def workspace_options(function: F) -> F:
    function = click.option(
        "--data-dir",
        type=click.Path(file_okay=False, path_type=str),
        help="Workspace sidecar directory (default: <dbfile stem>.data).",
    )(function)
    function = click.option(
        "--dbfile",
        "-d",
        default="warcindex.db",
        show_default=True,
        type=click.Path(dir_okay=False, path_type=str),
        help="DuckDB workspace catalog.",
    )(function)
    return function


def progress_options(function: F) -> F:
    """Add the shared tri-state progress override to a Click command."""
    return click.option(
        "--progress/--no-progress",
        default=None,
        help="Show or hide progress (default: automatic for interactive stderr).",
    )(function)


def _progress_renderer(
    requested: bool | None,
    *,
    silent: bool = False,
    machine_readable: bool = False,
) -> RichProgressRenderer:
    enabled = resolve_progress(
        requested,
        silent=silent,
        machine_readable=machine_readable,
        stream=click.get_text_stream("stderr"),
    )
    return RichProgressRenderer(enabled=enabled)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, indent=2, sort_keys=True)


def _expand_sources(values: Sequence[str]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for raw in values:
        matches = glob.glob(raw.strip("'\""), recursive=True)
        if not matches:
            matches = [raw]
        expanded: list[Path] = []
        for match in matches:
            path = canonical_path(match)
            if path.is_dir():
                expanded.extend(path.rglob("*.warc"))
                expanded.extend(path.rglob("*.warc.gz"))
            else:
                expanded.append(path)
        for path in sorted(expanded):
            value = str(path)
            if value not in seen:
                seen.add(value)
                resolved.append(value)
    return resolved


def _archive_ids(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _emit_report(
    report: AnalysisReport,
    *,
    output: str | None,
    output_format: str,
) -> None:
    if output_format == "table":
        from rich.console import Console
        from rich.json import JSON

        Console().print(JSON.from_data(report.to_dict(), default=str))
        return
    if output:
        write_report(report, output, output_format)
        click.echo(f"Wrote {report.kind} report to {canonical_path(output)}")
    else:
        click.echo(_json(report.to_dict()))


def _record_query(
    *,
    archive_ids: str | None,
    mimes: str | None,
    exts: str | None,
    url_pattern: str | None,
    host_pattern: str | None,
    status_min: int | None,
    status_max: int | None,
    date_from: str | None,
    date_to: str | None,
    size_min: int | None,
    size_max: int | None,
    sort_by: str,
    descending: bool,
    offset: int,
    limit: int,
    unsafe_where: str | None,
) -> RecordQuery:
    return RecordQuery.from_values(
        archive_ids=archive_ids,
        mimes=mimes,
        exts=exts,
        url_pattern=url_pattern,
        host_pattern=host_pattern,
        status_min=status_min,
        status_max=status_max,
        date_from=date_from,
        date_to=date_to,
        size_min=size_min,
        size_max=size_max,
        sort_by=sort_by,
        descending=descending,
        offset=offset,
        limit=limit,
        unsafe_where=unsafe_where,
    )


def record_filter_options(function: F) -> F:
    options = [
        click.option("--unsafe-where", help="Local-only raw SQL WHERE clause; explicitly unsafe."),
        click.option("--limit", default=100, show_default=True, type=click.IntRange(min=1)),
        click.option("--offset", default=0, show_default=True, type=click.IntRange(min=0)),
        click.option("--descending", is_flag=True, help="Reverse the selected sort order."),
        click.option(
            "--sort-by",
            type=click.Choice(
                [
                    "archive_id",
                    "warc_id",
                    "url",
                    "host",
                    "mime",
                    "ext",
                    "status",
                    "date",
                    "size",
                    "offset",
                ]
            ),
            default="offset",
            show_default=True,
        ),
        click.option("--size-max", type=click.IntRange(min=0)),
        click.option("--size-min", type=click.IntRange(min=0)),
        click.option("--date-to", help="Maximum record date (ISO-8601)."),
        click.option("--date-from", help="Minimum record date (ISO-8601)."),
        click.option("--status-max", type=click.IntRange(min=0, max=999)),
        click.option("--status-min", type=click.IntRange(min=0, max=999)),
        click.option("--host-pattern", help="Case-insensitive host substring."),
        click.option("--url-pattern", help="Case-insensitive URL substring."),
        click.option("--exts", "-e", help="Comma-separated extensions."),
        click.option("--mimes", "-m", help="Comma-separated MIME types."),
        click.option("--archive-ids", help="Comma-separated catalog archive IDs."),
    ]
    for option in options:
        function = option(function)
    return function


@click.group(cls=MetawarcGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable informational logs.")
def cli(verbose: bool) -> None:
    """Index, query, export, and analyze WARC collections."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO if verbose else logging.WARNING,
    )


@cli.command("index")
@click.argument("sources", nargs=-1, required=True)
@workspace_options
@click.option(
    "--mode",
    type=click.Choice(["add", "update", "rescan", "force"]),
    default="update",
    show_default=True,
)
@click.option("--resume/--no-resume", default=False, show_default=True)
@click.option("--batch-size", default=10_000, show_default=True, type=click.IntRange(min=1))
@click.option(
    "--digest-fingerprint", is_flag=True, help="Include source SHA-256 in change detection."
)
@click.option(
    "--hash-payloads", is_flag=True, help="Compute reusable SHA-256 payload hashes after indexing."
)
@click.option("--silent", "-s", is_flag=True)
@click.option("--output-format", type=click.Choice(["human", "json"]), default="human")
@progress_options
def index_command(
    sources: tuple[str, ...],
    dbfile: str,
    data_dir: str | None,
    mode: str,
    resume: bool,
    batch_size: int,
    digest_fingerprint: bool,
    hash_payloads: bool,
    silent: bool,
    output_format: str,
    progress: bool | None,
) -> None:
    """Build or update the record and header indexes for SOURCES."""
    with _progress_renderer(
        progress, silent=silent, machine_readable=output_format == "json"
    ) as renderer:
        summary = Indexer(batch_size=batch_size).index_records(
            _expand_sources(sources),
            dbfile,
            data_dir=data_dir,
            mode=mode,
            resume=resume,
            silent=silent,
            digest_fingerprint=digest_fingerprint,
            progress=renderer.callback,
        )
        if hash_payloads and not summary.failed:
            archive_ids = [
                outcome["archive_id"]
                for outcome in summary.outcomes
                if outcome["status"] in {"complete", "skipped"}
            ]
            with Workspace(dbfile, data_dir=data_dir, create=False) as workspace:
                report = AnalysisService(workspace).hash_payloads(
                    archive_ids=archive_ids, progress=renderer.callback
                )
                summary.analysis = report.to_dict()
                with workspace.writer_lock("index-manifest"):
                    workspace.annotate_run(
                        summary.run_id,
                        operation="index",
                        request={
                            "sources": list(sources),
                            "mode": mode,
                            "resume": resume,
                            "hash_payloads": True,
                        },
                        summary=summary.to_dict(),
                    )
    if output_format == "json":
        click.echo(_json(summary.to_dict()))
    elif not silent:
        click.echo(
            f"Run {summary.run_id}: {summary.processed} processed, "
            f"{summary.skipped} skipped, {summary.failed} failed, "
            f"{summary.records} records (revision {summary.revision})"
        )
    if summary.failed:
        raise click.ClickException(
            f"{summary.failed} source(s) failed; inspect the JSON summary or run catalog"
        )


@cli.command("ingest")
@click.argument("sources", nargs=-1, required=True)
@workspace_options
@click.option("--dry-run", is_flag=True, help="Plan without creating or changing the workspace.")
@click.option("--resume/--no-resume", default=True, show_default=True)
@click.option("--force", is_flag=True, help="Reindex unchanged sources too.")
@click.option("--batch-size", default=10_000, show_default=True, type=click.IntRange(min=1))
@click.option("--digest-fingerprint", is_flag=True)
@click.option("--silent", "-s", is_flag=True)
@click.option("--output-format", type=click.Choice(["human", "json"]), default="human")
@progress_options
def ingest_command(
    sources: tuple[str, ...],
    dbfile: str,
    data_dir: str | None,
    dry_run: bool,
    resume: bool,
    force: bool,
    batch_size: int,
    digest_fingerprint: bool,
    silent: bool,
    output_format: str,
    progress: bool | None,
) -> None:
    """Plan and apply incremental collection ingestion."""
    with _progress_renderer(
        progress, silent=silent, machine_readable=output_format == "json" or dry_run
    ) as renderer:
        plan, summary = IncrementalIngestor(batch_size=batch_size).ingest(
            _expand_sources(sources),
            dbfile=dbfile,
            data_dir=data_dir,
            dry_run=dry_run,
            resume=resume,
            force=force,
            silent=silent,
            digest_fingerprint=digest_fingerprint,
            progress=renderer.callback,
        )
    result = plan.to_dict()
    result["result"] = summary.to_dict() if summary else None
    if output_format == "json":
        click.echo(_json(result))
    else:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=f"Incremental ingestion plan (revision {plan.revision})")
        for column in ("action", "source", "archive_id", "reason"):
            table.add_column(column, overflow="fold")
        for action in plan.actions:
            table.add_row(
                action.action,
                action.source,
                action.archive_id or "",
                action.reason or "",
            )
        Console().print(table)
        if summary:
            click.echo(
                f"Run {summary.run_id}: {summary.processed} processed, "
                f"{summary.skipped} skipped, {summary.failed} failed "
                f"in {summary.duration_ms} ms (revision {summary.revision})"
            )
    if summary and summary.failed:
        raise click.ClickException(f"{summary.failed} source(s) failed")


@cli.command("index-content")
@click.argument("sources", nargs=-1)
@workspace_options
@click.option(
    "--type",
    "metadata_types",
    multiple=True,
    type=click.Choice(sorted(ContentIndexer.VALID_TYPES)),
    default=("links",),
    show_default=True,
)
@click.option("--rescan", is_flag=True)
@click.option("--batch-size", default=1_000, show_default=True, type=click.IntRange(min=1))
@click.option("--silent", "-s", is_flag=True)
@progress_options
def index_content_command(
    sources: tuple[str, ...],
    dbfile: str,
    data_dir: str | None,
    metadata_types: tuple[str, ...],
    rescan: bool,
    batch_size: int,
    silent: bool,
    progress: bool | None,
) -> None:
    """Build typed derived metadata indexes from catalog records."""
    selected = _expand_sources(sources) if sources else None
    extractor = ContentIndexer(batch_size=batch_size)
    results = []
    content_counts = {"processed": 0, "skipped": 0, "failed": 0}
    with _progress_renderer(progress, silent=silent) as renderer:
        for type_position, metadata_type in enumerate(metadata_types):

            def content_progress(
                event: ProgressEvent,
                *,
                current_position: int = type_position,
                current_type: str = metadata_type,
            ) -> None:
                if renderer.callback is None:
                    return
                if event.scope == "overall" and event.total is not None:
                    combined_total = event.total * len(metadata_types)
                    combined_completed = current_position * event.total + event.completed
                    combined_counters = {
                        name: content_counts[name] + int(event.counters.get(name, 0))
                        for name in content_counts
                    }
                    final = (
                        current_position == len(metadata_types) - 1
                        and event.completed == event.total
                    )
                    event = replace(
                        event,
                        task_id="type-archives",
                        label=f"Index content ({current_type})",
                        completed=combined_completed,
                        total=combined_total,
                        status=(
                            "failed"
                            if final and combined_counters["failed"]
                            else "complete"
                            if final
                            else "running"
                        ),
                        counters=combined_counters,
                    )
                renderer(event)

            result = extractor.index_by_table_type(
                selected,
                dbfile,
                metadata_type,
                rescan=rescan,
                silent=silent,
                data_dir=data_dir,
                progress=content_progress if renderer.callback is not None else None,
            )
            results.append(result)
            for name in content_counts:
                content_counts[name] += int(result[name])
    click.echo(_json(results))
    if any(result["failed"] for result in results):
        raise click.ClickException("One or more content-indexing operations failed")


@cli.command("catalog")
@workspace_options
@click.option("--output-format", type=click.Choice(["table", "json"]), default="table")
def catalog_command(dbfile: str, data_dir: str | None, output_format: str) -> None:
    """List catalog archives, identities, source paths, and status."""
    with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
        archives = QueryService(workspace).list_archives()
        revision = workspace.revision()
    if output_format == "json":
        click.echo(_json({"revision": revision, "archives": archives}))
        return
    from rich.console import Console
    from rich.table import Table

    table = Table(title=f"Metawarc catalog (revision {revision})")
    for column in ("id", "filename", "status", "num_records", "source_path"):
        table.add_column(column, overflow="fold")
    for archive in archives:
        table.add_row(
            *(
                str(archive.get(column, ""))
                for column in ("id", "filename", "status", "num_records", "source_path")
            )
        )
    Console().print(table)


@cli.command("stats")
@workspace_options
@click.option(
    "--mode", "-m", type=click.Choice(["mimes", "exts"]), default="mimes", show_default=True
)
@click.option("--output-format", type=click.Choice(["table", "json"]), default="table")
def stats_command(dbfile: str, data_dir: str | None, mode: str, output_format: str) -> None:
    """Summarize records by MIME type or extension."""
    if output_format == "table":
        Indexer().calc_stats(dbfile, mode, data_dir=data_dir)
        return
    dimension = "c_type" if mode == "mimes" else "ext"
    with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
        click.echo(_json(QueryService(workspace).aggregate(dimension)))


@cli.command("list-files")
@workspace_options
@record_filter_options
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=str))
@click.option("--output-format", type=click.Choice(["table", "csv", "jsonl"]), default="table")
def list_files_command(
    dbfile: str,
    data_dir: str | None,
    output: str | None,
    output_format: str,
    **filters: Any,
) -> None:
    """List indexed records using typed, parameterized filters."""
    unsafe_where = filters.pop("unsafe_where")
    selected = _record_query(unsafe_where=unsafe_where, **filters)
    Dumper().listfiles(
        warcfileids=selected.archive_ids,
        dbfile=dbfile,
        mimes=selected.mimes,
        exts=selected.exts,
        query=selected.unsafe_where,
        start=selected.offset,
        limit=selected.limit,
        output=output,
        data_dir=data_dir,
        url_pattern=selected.url_pattern,
        output_format=output_format,
        allow_unsafe=unsafe_where is not None,
        record_query=selected,
    )


@cli.command("dump")
@workspace_options
@click.option("--archive-ids")
@click.option("--mimes", "-m")
@click.option("--exts", "-e")
@click.option("--url-pattern")
@click.option("--unsafe-where")
@click.option("--offset", default=0, show_default=True, type=click.IntRange(min=0))
@click.option("--limit", default=1_000, show_default=True, type=click.IntRange(min=1, max=100_000))
@click.option("--max-bytes", type=click.IntRange(min=1))
@click.option(
    "--output",
    "-o",
    default="dump",
    show_default=True,
    type=click.Path(file_okay=False, path_type=str),
)
@click.option("--silent", "-s", is_flag=True)
@progress_options
def dump_command(
    dbfile: str,
    data_dir: str | None,
    archive_ids: str | None,
    mimes: str | None,
    exts: str | None,
    url_pattern: str | None,
    unsafe_where: str | None,
    offset: int,
    limit: int,
    max_bytes: int | None,
    output: str,
    silent: bool,
    progress: bool | None,
) -> None:
    """Safely export selected payloads with a JSONL manifest."""
    with _progress_renderer(progress, silent=silent) as renderer:
        result = Dumper().dump(
            warcfiles=archive_ids,
            dbfile=dbfile,
            mimes=mimes,
            exts=exts,
            query=unsafe_where,
            start=offset,
            limit=limit,
            output=output,
            silent=silent,
            data_dir=data_dir,
            url_pattern=url_pattern,
            max_bytes=max_bytes,
            allow_unsafe=unsafe_where is not None,
            progress=renderer.callback,
        )
    click.echo(_json(result))
    if result["failed"]:
        raise click.ClickException(f"{result['failed']} record export(s) failed")


@cli.command("get")
@click.argument("record_id")
@workspace_options
@click.option("--archive-id", help="Disambiguate a repeated WARC record ID.")
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=str))
@click.option("--max-bytes", type=click.IntRange(min=1))
@click.option("--silent", "-s", is_flag=True)
def get_command(
    record_id: str,
    dbfile: str,
    data_dir: str | None,
    archive_id: str | None,
    output: str | None,
    max_bytes: int | None,
    silent: bool,
) -> None:
    """Export one payload by WARC record ID."""
    result = Dumper().get_file(
        record_id,
        dbfile,
        output=output,
        silent=silent,
        data_dir=data_dir,
        archive_id=archive_id,
        max_bytes=max_bytes,
    )
    if result is None:
        raise click.ClickException("Record not found")


@cli.command("dump-metadata")
@click.argument("sources", nargs=-1)
@workspace_options
@click.option(
    "--type",
    "metadata_type",
    type=click.Choice(sorted(ContentIndexer.VALID_TYPES)),
    default="ooxmldocs",
    show_default=True,
)
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=str))
@click.option("--silent", "-s", is_flag=True)
@progress_options
def dump_metadata_command(
    sources: tuple[str, ...],
    dbfile: str,
    data_dir: str | None,
    metadata_type: str,
    output: str | None,
    silent: bool,
    progress: bool | None,
) -> None:
    """Export a derived metadata index as JSON Lines."""
    with _progress_renderer(progress, silent=silent, machine_readable=output is None) as renderer:
        count = ContentIndexer().dump_metadata(
            _expand_sources(sources) if sources else None,
            dbfile,
            metadata_type=metadata_type,
            output=output,
            silent=silent,
            data_dir=data_dir,
            progress=renderer.callback,
        )
    if output and not silent:
        click.echo(f"Exported {count} rows")


@cli.command("doctor")
@workspace_options
@click.option("--repair", is_flag=True, help="Plan safe orphan-sidecar quarantine actions.")
@click.option(
    "--apply", "apply_repairs", is_flag=True, help="Apply planned repairs; requires --repair."
)
def doctor_command(
    dbfile: str,
    data_dir: str | None,
    repair: bool,
    apply_repairs: bool,
) -> None:
    """Validate workspace schema, sources, sidecars, and orphan files."""
    if apply_repairs and not repair:
        raise click.UsageError("--apply requires --repair")
    with Workspace(
        dbfile, data_dir=data_dir, read_only=not apply_repairs, create=False
    ) as workspace:
        report = workspace.doctor(repair=repair, dry_run=not apply_repairs)
    click.echo(_json(report.to_dict()))
    if not report.ok:
        raise click.ClickException("Workspace diagnostics found errors")


@cli.command("rebind")
@click.argument("archive_id")
@click.argument("source", type=click.Path(dir_okay=False, path_type=Path))
@workspace_options
@click.option(
    "--force", is_flag=True, help="Accept a mismatched fingerprint after independent verification."
)
def rebind_command(
    archive_id: str,
    source: Path,
    dbfile: str,
    data_dir: str | None,
    force: bool,
) -> None:
    """Explicitly bind a stable archive identity to a moved source path."""
    with (
        Workspace(dbfile, data_dir=data_dir, create=False) as workspace,
        workspace.writer_lock("rebind"),
    ):
        workspace.rebind_archive(archive_id, source, force=force)
    click.echo(f"Rebound archive {archive_id} to {canonical_path(source)}")


@cli.command("cleanup")
@workspace_options
@click.option("--retention-days", default=7.0, show_default=True, type=click.FloatRange(min=0))
@click.option("--apply", "apply_cleanup", is_flag=True, help="Remove the previewed candidates.")
def cleanup_command(
    dbfile: str,
    data_dir: str | None,
    retention_days: float,
    apply_cleanup: bool,
) -> None:
    """Preview or purge expired retired sidecars and interrupted staging files."""
    with Workspace(
        dbfile, data_dir=data_dir, read_only=not apply_cleanup, create=False
    ) as workspace:
        if apply_cleanup:
            with workspace.writer_lock("cleanup"):
                report = workspace.cleanup_retired(retention_days=retention_days, dry_run=False)
        else:
            report = workspace.cleanup_retired(retention_days=retention_days, dry_run=True)
    click.echo(_json(report))


@cli.group("analyze", cls=MetawarcGroup)
def analyze_group() -> None:
    """Run revision-scoped collection analysis."""


def analysis_output_options(function: F) -> F:
    function = click.option(
        "--output-format",
        type=click.Choice(["table", "json", "csv", "parquet"]),
        default="json",
    )(function)
    function = click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=str))(
        function
    )
    function = click.option("--archive-ids", help="Comma-separated catalog archive IDs.")(function)
    function = workspace_options(function)
    return function


@analyze_group.command("summary")
@analysis_output_options
@click.option(
    "--dimension",
    "dimensions",
    multiple=True,
    type=click.Choice(["mime", "ext", "status", "host", "date", "size_bucket"]),
)
@click.option("--top", type=click.IntRange(min=1, max=100_000))
def analyze_summary(
    dbfile: str,
    data_dir: str | None,
    archive_ids: str | None,
    output: str | None,
    output_format: str,
    dimensions: tuple[str, ...],
    top: int | None,
) -> None:
    """Aggregate MIME, extension, status, host, date, and size dimensions."""
    with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
        query = RecordQuery(archive_ids=tuple(_archive_ids(archive_ids) or ()), limit=1)
        report = AnalysisService(workspace).summary(
            dimensions or ("mime", "ext", "status", "host", "date", "size_bucket"),
            query=query,
            top=top,
        )
    _emit_report(report, output=output, output_format=output_format)


@analyze_group.command("metadata")
@analysis_output_options
@click.option(
    "--type",
    "metadata_types",
    multiple=True,
    type=click.Choice([*STORED_METADATA_TYPES, "all"]),
    help="Stored metadata type; repeat for multiple types (default: all).",
)
@click.option("--top", default=10, show_default=True, type=click.IntRange(min=1, max=100_000))
def analyze_metadata(
    dbfile: str,
    data_dir: str | None,
    archive_ids: str | None,
    output: str | None,
    output_format: str,
    metadata_types: tuple[str, ...],
    top: int,
) -> None:
    """Analyze stored document, image, video, audio, and font metadata envelopes."""
    with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
        report = AnalysisService(workspace).stored_metadata(
            metadata_types=metadata_types,
            archive_ids=_archive_ids(archive_ids),
            top=top,
        )
    _emit_report(report, output=output, output_format=output_format)


@analyze_group.command("hashes")
@analysis_output_options
@click.option("--force", is_flag=True)
@click.option("--resume/--no-resume", default=True, show_default=True)
@click.option("--batch-size", default=1_000, show_default=True, type=click.IntRange(min=1))
@progress_options
def analyze_hashes(
    dbfile: str,
    data_dir: str | None,
    archive_ids: str | None,
    output: str | None,
    output_format: str,
    force: bool,
    resume: bool,
    batch_size: int,
    progress: bool | None,
) -> None:
    """Compute reusable streaming SHA-256 payload hashes."""
    with (
        _progress_renderer(progress, machine_readable=output_format != "table") as renderer,
        Workspace(dbfile, data_dir=data_dir, create=False) as workspace,
    ):
        report = AnalysisService(workspace).hash_payloads(
            archive_ids=_archive_ids(archive_ids),
            force=force,
            resume=resume,
            batch_size=batch_size,
            progress=renderer.callback,
        )
    _emit_report(report, output=output, output_format=output_format)
    if report.failures:
        raise click.ClickException("One or more archive hash runs failed")


@analyze_group.command("duplicates")
@analysis_output_options
def analyze_duplicates(
    dbfile: str,
    data_dir: str | None,
    archive_ids: str | None,
    output: str | None,
    output_format: str,
) -> None:
    """Group records with identical stored payload hashes."""
    with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
        report = AnalysisService(workspace).duplicates(archive_ids=_archive_ids(archive_ids))
    _emit_report(report, output=output, output_format=output_format)


@analyze_group.command("links")
@analysis_output_options
def analyze_links(
    dbfile: str,
    data_dir: str | None,
    archive_ids: str | None,
    output: str | None,
    output_format: str,
) -> None:
    """Build normalized internal/external host-level link edges."""
    with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
        report = AnalysisService(workspace).link_graph(archive_ids=_archive_ids(archive_ids))
    _emit_report(report, output=output, output_format=output_format)


@analyze_group.command("integrity")
@analysis_output_options
@click.option("--deep", is_flag=True, help="Read payloads and verify length/digest values.")
@click.option("--max-records", default=10_000, show_default=True, type=click.IntRange(min=1))
@click.option("--resume/--no-resume", default=True, show_default=True)
@click.option("--force", is_flag=True, help="Recompute an existing current integrity sidecar.")
@click.option("--batch-size", default=500, show_default=True, type=click.IntRange(min=1))
@progress_options
def analyze_integrity(
    dbfile: str,
    data_dir: str | None,
    archive_ids: str | None,
    output: str | None,
    output_format: str,
    deep: bool,
    max_records: int,
    resume: bool,
    force: bool,
    batch_size: int,
    progress: bool | None,
) -> None:
    """Run fast workspace checks or bounded deep payload verification."""
    with (
        _progress_renderer(
            progress, machine_readable=output_format != "table" or not deep
        ) as renderer,
        Workspace(dbfile, data_dir=data_dir, read_only=not deep, create=False) as workspace,
    ):
        report = AnalysisService(workspace).integrity(
            archive_ids=_archive_ids(archive_ids),
            deep=deep,
            max_records=max_records,
            resume=resume,
            force=force,
            batch_size=batch_size,
            progress=renderer.callback,
        )
    _emit_report(report, output=output, output_format=output_format)


@cli.command("export-cdxj")
@workspace_options
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(dir_okay=False, path_type=str),
    help="CDXJ output path.",
)
@click.option(
    "--path-index",
    type=click.Path(dir_okay=False, path_type=str),
    help="Optional filename-to-absolute-path TSV for pywb archive_paths.",
)
@click.option("--archive-ids", help="Comma-separated archive IDs.")
@click.option("--output-format", type=click.Choice(["human", "json"]), default="human")
def export_cdxj_command(
    dbfile: str,
    data_dir: str | None,
    output: str,
    path_index: str | None,
    archive_ids: str | None,
    output_format: str,
) -> None:
    """Export CDXJ from the workspace catalog for external replay engines."""
    with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
        result = export_cdxj(
            workspace,
            output,
            path_index=path_index,
            archive_ids=_archive_ids(archive_ids),
        )
    if output_format == "json":
        click.echo(_json(result))
    else:
        click.echo(
            f"Wrote {result['records']} CDXJ records to {result['cdxj']}"
            + (f" and path index {result['path_index']}" if result["path_index"] else "")
        )


@cli.command("serve")
@workspace_options
@click.option("--host", default=None, help="Bind host (default: environment or 127.0.0.1).")
@click.option("--port", type=click.IntRange(min=1, max=65535))
@click.option(
    "--token", envvar="METAWARC_API_TOKEN", help="Bearer token (prefer environment variable)."
)
@click.option(
    "--allow-insecure", is_flag=True, help="Acknowledge unauthenticated non-loopback binding."
)
def serve_command(
    dbfile: str,
    data_dir: str | None,
    host: str | None,
    port: int | None,
    token: str | None,
    allow_insecure: bool,
) -> None:
    """Serve the bounded, authenticated, read-only REST API (includes /replay)."""
    _run_serve(
        dbfile=dbfile,
        data_dir=data_dir,
        host=host,
        port=port,
        token=token,
        allow_insecure=allow_insecure,
    )


@cli.command("replay")
@workspace_options
@click.option("--host", default=None, help="Bind host (default: environment or 127.0.0.1).")
@click.option("--port", type=click.IntRange(min=1, max=65535))
@click.option(
    "--token", envvar="METAWARC_API_TOKEN", help="Bearer token (prefer environment variable)."
)
@click.option(
    "--allow-insecure", is_flag=True, help="Acknowledge unauthenticated non-loopback binding."
)
def replay_command(
    dbfile: str,
    data_dir: str | None,
    host: str | None,
    port: int | None,
    token: str | None,
    allow_insecure: bool,
) -> None:
    """Alias for serve; website replay is available under /replay/<stamp>/<url>."""
    click.echo(
        "Starting metawarc serve with website replay at "
        "/replay/<YYYYMMDDHHMMSS[mp_|id_]>/<url>",
        err=True,
    )
    _run_serve(
        dbfile=dbfile,
        data_dir=data_dir,
        host=host,
        port=port,
        token=token,
        allow_insecure=allow_insecure,
    )


def _run_serve(
    *,
    dbfile: str,
    data_dir: str | None,
    host: str | None,
    port: int | None,
    token: str | None,
    allow_insecure: bool,
) -> None:
    defaults = ServerSettings.from_env()
    selected_host = host or defaults.host
    if not is_loopback(selected_host) and not token and not allow_insecure:
        raise click.UsageError(
            "Non-loopback API binding requires --token/METAWARC_API_TOKEN or --allow-insecure"
        )
    settings = ServerSettings(
        db_path=dbfile,
        data_dir=data_dir,
        host=selected_host,
        port=port or defaults.port,
        mcp_port=defaults.mcp_port,
        token=token,
        max_page=defaults.max_page,
        max_payload_bytes=defaults.max_payload_bytes,
        request_timeout_seconds=defaults.request_timeout_seconds,
        max_concurrency=defaults.max_concurrency,
    )
    try:
        import uvicorn
    except ImportError as exc:
        raise click.ClickException(
            "API/replay support requires `pip install metawarc[api]` or `metawarc[replay]`"
        ) from exc
    from .cmds.server import create_app

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


@cli.command("mcp")
@workspace_options
@click.option(
    "--transport", type=click.Choice(["stdio", "http", "sse"]), default="stdio", show_default=True
)
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8191, show_default=True, type=click.IntRange(min=1, max=65535))
@click.option(
    "--allow-insecure",
    is_flag=True,
    help="Acknowledge an unauthenticated non-loopback MCP binding.",
)
def mcp_command(
    dbfile: str,
    data_dir: str | None,
    transport: str,
    host: str,
    port: int,
    allow_insecure: bool,
) -> None:
    """Run the explicit read-only MCP tool surface."""
    if transport != "stdio" and not is_loopback(host) and not allow_insecure:
        raise click.UsageError("Non-loopback MCP binding requires --allow-insecure")
    from .mcp_server import create_mcp

    server = create_mcp(dbfile, data_dir)
    kwargs = {} if transport == "stdio" else {"host": host, "port": port}
    server.run(transport=transport, **kwargs)


__all__ = ["cli"]
