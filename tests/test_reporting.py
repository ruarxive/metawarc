"""Direct rendering tests for CLI presentation helpers."""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace

from rich.console import Console as RichConsole
from rich.table import Table

from metawarc import reporting


def _capture_console(monkeypatch) -> StringIO:
    output = StringIO()
    monkeypatch.setattr(reporting, "Console", lambda: RichConsole(file=output, width=120))
    return output


def test_render_report_and_json(monkeypatch):
    output = _capture_console(monkeypatch)
    report = SimpleNamespace(
        columns=("name", "value"),
        rows=(("museum", 2),),
        to_dict=lambda: {"name": "museum", "value": 2},
    )

    reporting.render_report(report)
    reporting.render_json(report)

    rendered = output.getvalue()
    assert "museum" in rendered
    assert "value" in rendered
    assert '"value": 2' in rendered


def test_render_table(monkeypatch):
    output = _capture_console(monkeypatch)
    table = Table(title="Records")
    table.add_column("url")
    table.add_row("https://example.test/")

    reporting.render_table(table)

    assert "Records" in output.getvalue()
    assert "https://example.test/" in output.getvalue()


def test_render_catalog(monkeypatch):
    output = _capture_console(monkeypatch)
    archives = [
        {
            "id": "archive-1",
            "filename": "collection.warc.gz",
            "status": "active",
            "num_records": 3,
            "source_path": "archives/collection.warc.gz",
        }
    ]

    reporting.render_catalog(archives, revision=7)

    rendered = output.getvalue()
    assert "revision 7" in rendered
    assert "archive-1" in rendered
    assert "collection.warc.gz" in rendered


def test_render_ingest_plan_with_and_without_summary(monkeypatch, capsys):
    output = _capture_console(monkeypatch)
    plan = SimpleNamespace(
        revision=4,
        actions=[
            SimpleNamespace(
                action="add",
                source="archives/new.warc",
                archive_id=None,
                reason="new source",
            ),
            SimpleNamespace(
                action="skip",
                source="archives/old.warc",
                archive_id="archive-1",
                reason=None,
            ),
        ],
    )
    summary = SimpleNamespace(
        run_id="run-1",
        processed=1,
        skipped=1,
        failed=0,
        duration_ms=25,
        revision=4,
    )

    reporting.render_ingest_plan(plan, summary)
    reporting.render_ingest_plan(plan, None)

    rendered = output.getvalue()
    assert "revision 4" in rendered
    assert "archives/new.warc" in rendered
    assert "archive-1" in rendered
    assert capsys.readouterr().out.count("Run run-1: 1 processed, 1 skipped, 0 failed") == 1
