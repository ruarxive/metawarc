"""Report rendering helpers for the Metawarc CLI.

The command-group wiring in :mod:`metawarc.core` delegates all Rich-table
and JSON rendering to this module so that ``core.py`` can grow command
definitions and option plumbing without mixing presentation code into the
control flow.

Library callers that import :mod:`metawarc` without going through the CLI
do not trigger any rendering side effects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from .analysis import AnalysisReport


def render_report(report: AnalysisReport) -> None:
    """Print an :class:`AnalysisReport` as a Rich table."""
    Console().print(_report_table(report))


def render_json(report: AnalysisReport) -> None:
    """Print an :class:`AnalysisReport` as Rich-formatted JSON."""
    from rich.json import JSON

    Console().print(JSON.from_data(report.to_dict(), default=str))


def render_table(table: Table) -> None:
    """Print an already-built Rich table."""
    Console().print(table)


def render_ingest_plan(plan: Any, summary: Any | None) -> None:
    """Print an incremental-ingest plan as a Rich table.

    The plan object must expose ``revision`` and ``actions`` (iterable of
    objects with ``action``, ``source``, ``archive_id``, ``reason``).
    The summary, when provided, is printed after the table as a single
    run-summary line.
    """
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
    if summary is not None:
        from click import echo

        echo(
            f"Run {summary.run_id}: {summary.processed} processed, "
            f"{summary.skipped} skipped, {summary.failed} failed "
            f"in {summary.duration_ms} ms (revision {summary.revision})"
        )


def render_catalog(archives: list[dict[str, Any]], revision: int) -> None:
    """Print a catalog summary as a five-column Rich table."""
    columns = ("id", "filename", "status", "num_records", "source_path")
    table = Table(title=f"Metawarc catalog (revision {revision})")
    for column in columns:
        table.add_column(column, overflow="fold")
    for archive in archives:
        table.add_row(*(str(archive.get(column, "")) for column in columns))
    Console().print(table)


def _report_table(report: AnalysisReport) -> Table:
    """Build the standard Rich table for an :class:`AnalysisReport`."""
    table = Table(show_header=True, header_style="bold")
    for column in getattr(report, "columns", ()):
        table.add_column(column)
    for row in getattr(report, "rows", ()):
        table.add_row(*(str(cell) for cell in row))
    return table


__all__ = [
    "render_catalog",
    "render_ingest_plan",
    "render_json",
    "render_report",
    "render_table",
]
