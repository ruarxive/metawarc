from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rich.console import Console

from metawarc.analysis import AnalysisService
from metawarc.cmds.extractor import ContentIndexer
from metawarc.cmds.indexer import Indexer
from metawarc.core import cli
from metawarc.progress import ProgressEvent, RichProgressRenderer, resolve_progress
from metawarc.workspace import Workspace


class InteractiveBuffer(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_progress_mode_resolution() -> None:
    interactive = InteractiveBuffer()
    redirected = io.StringIO()

    assert resolve_progress(None, stream=interactive)
    assert not resolve_progress(None, stream=redirected)
    assert resolve_progress(True, stream=redirected)
    assert not resolve_progress(False, stream=interactive)
    assert not resolve_progress(True, silent=True, stream=interactive)
    assert not resolve_progress(True, machine_readable=True, stream=interactive)


@pytest.mark.parametrize("exception", [RuntimeError("failed"), KeyboardInterrupt()])
def test_renderer_closes_after_failure_or_interrupt(exception: BaseException) -> None:
    output = io.StringIO()
    renderer = RichProgressRenderer(
        enabled=True,
        console=Console(file=output, force_terminal=False, width=120),
    )

    with pytest.raises(type(exception)), renderer:
        renderer(
            ProgressEvent(
                operation="test",
                phase="records",
                task_id="archive",
                label="Scan archive",
                unit="record",
                completed=1,
            )
        )
        raise exception

    assert not renderer.active
    assert "Scan archive" in output.getvalue()


def test_index_and_content_services_emit_monotonic_events(warc_factory, tmp_path: Path) -> None:
    source = warc_factory()
    database = tmp_path / "progress.db"
    index_events: list[ProgressEvent] = []

    summary = Indexer(batch_size=1).index_records(
        [source],
        str(database),
        silent=True,
        progress=index_events.append,
    )

    assert summary.records == 2
    assert index_events[-1].scope == "overall"
    assert index_events[-1].status == "complete"
    record_events = [event for event in index_events if event.phase == "records"]
    assert record_events
    assert all(event.total is None for event in record_events)
    assert [event.completed for event in record_events] == sorted(
        event.completed for event in record_events
    )

    content_events: list[ProgressEvent] = []
    result = ContentIndexer(batch_size=1).index_by_table_type(
        None,
        str(database),
        "links",
        rescan=True,
        silent=True,
        progress=content_events.append,
    )

    assert result["processed"] == 1
    candidates = [event for event in content_events if event.phase == "candidates"]
    assert candidates[-1].status == "complete"
    assert candidates[-1].completed == candidates[-1].total == 1
    assert content_events[-1].scope == "overall"
    assert content_events[-1].status == "complete"


def test_cli_progress_is_forced_to_stderr_and_stdout_stays_json(
    warc_factory, tmp_path: Path
) -> None:
    source = warc_factory()
    database = tmp_path / "cli-progress.db"
    runner = CliRunner()
    indexed = runner.invoke(
        cli,
        ["index", str(source), "--dbfile", str(database), "--silent", "--output-format", "json"],
    )
    assert indexed.exit_code == 0, indexed.output

    result = runner.invoke(
        cli,
        [
            "index-content",
            "--dbfile",
            str(database),
            "--type",
            "links",
            "--type",
            "pdfs",
            "--rescan",
            "--progress",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(json.loads(result.stdout)) == 2
    assert "Index content" in result.stderr
    assert "pdfs" in result.stderr

    exported = runner.invoke(
        cli,
        [
            "dump",
            "--dbfile",
            str(database),
            "--limit",
            "1",
            "--output",
            str(tmp_path / "export"),
            "--progress",
        ],
    )
    assert exported.exit_code == 0, exported.output
    assert json.loads(exported.stdout)["completed"] == 1
    assert "Export payloads" in exported.stderr


def test_cli_progress_suppression_rules(warc_factory, tmp_path: Path) -> None:
    source = warc_factory()
    runner = CliRunner()

    json_result = runner.invoke(
        cli,
        [
            "index",
            str(source),
            "--dbfile",
            str(tmp_path / "json.db"),
            "--output-format",
            "json",
            "--progress",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    assert json.loads(json_result.stdout)["records"] == 2
    assert json_result.stderr == ""

    silent_result = runner.invoke(
        cli,
        [
            "index",
            str(source),
            "--dbfile",
            str(tmp_path / "silent.db"),
            "--silent",
            "--progress",
        ],
    )
    assert silent_result.exit_code == 0, silent_result.output
    assert silent_result.stdout == ""
    assert silent_result.stderr == ""

    automatic_result = runner.invoke(
        cli,
        ["index", str(source), "--dbfile", str(tmp_path / "automatic.db")],
    )
    assert automatic_result.exit_code == 0, automatic_result.output
    assert automatic_result.stderr == ""

    disabled_result = runner.invoke(
        cli,
        [
            "index",
            str(source),
            "--dbfile",
            str(tmp_path / "disabled.db"),
            "--no-progress",
        ],
    )
    assert disabled_result.exit_code == 0, disabled_result.output
    assert disabled_result.stderr == ""


def test_hash_and_integrity_emit_archive_and_record_progress(indexed_workspace) -> None:
    database, _source = indexed_workspace
    hash_events: list[ProgressEvent] = []
    integrity_events: list[ProgressEvent] = []

    with Workspace(str(database), create=False) as workspace:
        hashes = AnalysisService(workspace).hash_payloads(
            force=True,
            batch_size=1,
            progress=hash_events.append,
        )
        integrity = AnalysisService(workspace).integrity(
            deep=True,
            force=True,
            max_records=2,
            batch_size=1,
            progress=integrity_events.append,
        )

    assert not hashes.failures
    assert not integrity.failures
    for events in (hash_events, integrity_events):
        assert {event.scope for event in events} == {"overall", "current"}
        final = [event for event in events if event.scope == "overall"][-1]
        assert final.status == "complete"
        record_events = [event for event in events if event.phase == "records"]
        by_task: dict[str, list[int]] = {}
        for event in record_events:
            by_task.setdefault(event.task_id, []).append(event.completed)
        assert all(values == sorted(values) for values in by_task.values())
