"""``metawarc jobs`` subcommand group — submit, list, get, wait, cancel."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click

from .jobs import (
    EXPORT_DEFAULT_LIMIT,
    EXPORT_FORMATS,
    EXPORT_HARD_LIMIT,
    Job,
    JobKind,
    JobRunner,
    JobStatus,
    JobStore,
)
from .query import RecordQuery


def _jobs_root(ctx: click.Context) -> tuple[str, str]:
    """Resolve (db_path, data_dir) from the parent ``cli`` group context."""
    own_dbfile = ctx.params.get("dbfile")
    own_data_dir = ctx.params.get("data_dir")
    parent_dbfile = ctx.parent.params.get("dbfile") if ctx.parent else None
    parent_data_dir = ctx.parent.params.get("data_dir") if ctx.parent else None
    db_path = own_dbfile or parent_dbfile or "warcindex.db"
    data_dir = own_data_dir or parent_data_dir or str(Path(db_path).with_suffix(".data"))
    return db_path, data_dir


def _build_runner(ctx: click.Context) -> JobRunner:
    db_path, data_dir = _jobs_root(ctx)
    store = JobStore(data_dir)
    settings = _CLIJobSettings(db_path, data_dir)
    return JobRunner(store, settings=settings)


class _CLIJobSettings:
    """Minimal ``ServerSettings``-shaped object for the CLI runner."""

    def __init__(self, db_path: str, data_dir: str) -> None:
        self.db_path = db_path
        self.data_dir = data_dir
        self.job_max_concurrent = 1
        self.request_timeout_seconds = 30


def _print_job(job: Job | None) -> None:
    if job is None:
        click.echo("(no such job)", err=True)
        sys.exit(1)
    click.echo(json.dumps(job.to_dict(), ensure_ascii=False, sort_keys=True, default=str))


@click.group("jobs")
@click.option(
    "--dbfile",
    "-d",
    default="warcindex.db",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=str),
    help="DuckDB workspace catalog.",
)
@click.option(
    "--data-dir",
    type=click.Path(file_okay=False, path_type=str),
    help="Workspace sidecar directory (default: <dbfile stem>.data).",
)
def jobs_group(dbfile: str, data_dir: str | None) -> None:
    """Submit, list, get, wait, and cancel durable batch jobs."""
    del dbfile, data_dir


@jobs_group.command("submit")
@click.option("--kind", default="export-records", show_default=True)
@click.option(
    "--format",
    "format_",
    type=click.Choice(EXPORT_FORMATS),
    default="json",
    show_default=True,
)
@click.option("--limit", default=EXPORT_DEFAULT_LIMIT, show_default=True, type=int)
@click.option("--archive-ids", default=None, help="Comma-separated archive IDs.")
@click.option("--mimes", default=None, help="Comma-separated MIME values.")
@click.option("--exts", default=None, help="Comma-separated extensions.")
@click.option("--url-pattern", default=None)
@click.option("--host-pattern", default=None)
@click.option("--status-min", type=int, default=None)
@click.option("--status-max", type=int, default=None)
@click.option("--size-min", type=int, default=None)
@click.option("--size-max", type=int, default=None)
def jobs_submit(
    kind: str,
    format_: str,
    limit: int,
    archive_ids: str | None,
    mimes: str | None,
    exts: str | None,
    url_pattern: str | None,
    host_pattern: str | None,
    status_min: int | None,
    status_max: int | None,
    size_min: int | None,
    size_max: int | None,
) -> None:
    """Submit a new batch job. Prints the new job id."""
    if limit < 1 or limit > EXPORT_HARD_LIMIT:
        raise click.UsageError(f"limit must be between 1 and {EXPORT_HARD_LIMIT}")
    try:
        kind_enum = JobKind(kind)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    ctx = click.get_current_context()
    runner = _build_runner(ctx)
    filters: dict[str, Any] = {
        "archive_ids": archive_ids,
        "mimes": mimes,
        "exts": exts,
        "url_pattern": url_pattern,
        "host_pattern": host_pattern,
        "status_min": status_min,
        "status_max": status_max,
        "size_min": size_min,
        "size_max": size_max,
    }
    filters = {key: value for key, value in filters.items() if value not in (None, "")}
    job = runner.submit(
        kind_enum,
        {
            "format": format_,
            "limit": limit,
            "filters": filters,
        },
    )
    click.echo(job.id)


@jobs_group.command("list")
@click.option(
    "--status",
    type=click.Choice(JobStatus.values()),
    default=None,
    help="Filter by status.",
)
@click.option("--limit", default=50, show_default=True, type=int)
def jobs_list(status: str | None, limit: int) -> None:
    """List batch jobs, newest first."""
    ctx = click.get_current_context()
    runner = _build_runner(ctx)
    jobs = runner.list_jobs(status=status, limit=limit)
    click.echo(
        json.dumps([job.to_dict() for job in jobs], ensure_ascii=False, sort_keys=True, default=str)
    )


@jobs_group.command("get")
@click.argument("job_id")
def jobs_get(job_id: str) -> None:
    """Show one batch job."""
    ctx = click.get_current_context()
    runner = _build_runner(ctx)
    _print_job(runner.get(job_id))


@jobs_group.command("wait")
@click.argument("job_id")
@click.option("--poll-seconds", default=1.0, show_default=True, type=float)
@click.option("--timeout", default=300, show_default=True, type=int)
def jobs_wait(job_id: str, poll_seconds: float, timeout: int) -> None:
    """Poll until JOB_ID finishes; exit non-zero on failure or cancellation."""
    ctx = click.get_current_context()
    runner = _build_runner(ctx)

    async def _poll() -> Job | None:
        elapsed = 0.0
        while elapsed < timeout:
            job = runner.get(job_id)
            if job is None:
                return None
            if job.status in {
                JobStatus.SUCCEEDED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
            }:
                return job
            await asyncio.sleep(poll_seconds)
            elapsed += poll_seconds
        return runner.get(job_id)

    job = asyncio.run(_poll())
    if job is None:
        click.echo("(no such job)", err=True)
        sys.exit(1)
    if job.status == JobStatus.SUCCEEDED.value:
        _print_job(job)
        return
    if job.status == JobStatus.CANCELLED.value:
        _print_job(job)
        sys.exit(2)
    if job.status == JobStatus.FAILED.value:
        _print_job(job)
        sys.exit(3)
    # Timed out
    _print_job(job)
    sys.exit(124)


@jobs_group.command("cancel")
@click.argument("job_id")
def jobs_cancel(job_id: str) -> None:
    """Cancel a pending or running batch job."""
    ctx = click.get_current_context()
    runner = _build_runner(ctx)
    try:
        job = runner.cancel(job_id)
    except KeyError:
        click.echo("(no such job)", err=True)
        sys.exit(1)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _print_job(job)


__all__ = ["jobs_group", "RecordQuery"]
