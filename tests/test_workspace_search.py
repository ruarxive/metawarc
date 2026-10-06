"""Tests for :meth:`Workspace.search_text` and the ``texts`` sidecar path."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from metawarc.extractor import TEXT_SCHEMA
from metawarc.workspace import Workspace


def _publish_texts_sidecar(workspace: Workspace, archive_id: str, rows: list[dict]) -> Path:
    """Publish a synthetic ``texts`` sidecar directly to the workspace."""
    table = pa.Table.from_pylist(rows, schema=TEXT_SCHEMA)
    destination = workspace.new_sidecar_path(archive_id, "synthetic", "texts")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, destination, compression="zstd")
    workspace.publish_sidecar(
        archive_id=archive_id,
        kind="texts",
        path=destination,
        num_items=table.num_rows,
        run_id="synthetic",
    )
    return destination


@pytest.fixture
def workspace_with_texts(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(str(database), read_only=False, create=False) as workspace:
        archives = workspace.list_archives()
        archive_id = archives[0]["id"]
        rows = [
            {
                "archive_id": archive_id,
                "warc_id": "WARC-1",
                "source": "sample.warc",
                "url": "https://example.test/welcome",
                "language": "en",
                "text": "Welcome to the museum of modern art",
            },
            {
                "archive_id": archive_id,
                "warc_id": "WARC-2",
                "source": "sample.warc",
                "url": "https://example.test/about",
                "language": "en",
                "text": "About our opening hours and ticket prices",
            },
            {
                "archive_id": archive_id,
                "warc_id": "WARC-3",
                "source": "sample.warc",
                "url": "https://example.test/contact",
                "language": "en",
                "text": "Contact the curator by email or phone",
            },
        ]
        _publish_texts_sidecar(workspace, archive_id, rows)
    return database


def test_search_text_returns_matches(workspace_with_texts: Path) -> None:
    with Workspace(str(workspace_with_texts), read_only=False, create=False) as workspace:
        results = workspace.search_text("museum")
    assert len(results) == 1
    hit = results[0]
    assert hit["url"] == "https://example.test/welcome"
    assert "museum" in hit["snippet"].lower()
    assert hit["warc_id"] == "WARC-1"


def test_search_text_returns_empty_on_no_match(workspace_with_texts: Path) -> None:
    with Workspace(str(workspace_with_texts), read_only=False, create=False) as workspace:
        results = workspace.search_text("nonexistent-term-xyz")
    assert results == []


def test_search_text_returns_empty_when_no_sidecar(indexed_workspace) -> None:
    database, _ = indexed_workspace
    with Workspace(str(database), read_only=False, create=False) as workspace:
        results = workspace.search_text("anything")
    assert results == []


def test_search_text_rejects_empty_phrase(indexed_workspace) -> None:
    database, _ = indexed_workspace
    with (
        Workspace(str(database), read_only=False, create=False) as workspace,
        pytest.raises(ValueError, match="phrase"),
    ):
        workspace.search_text("")


def test_search_text_rejects_zero_limit(workspace_with_texts: Path) -> None:
    with (
        Workspace(str(workspace_with_texts), read_only=False, create=False) as workspace,
        pytest.raises(ValueError, match="limit"),
    ):
        workspace.search_text("museum", limit=0)


def test_search_text_respects_limit_indexed_workspace(indexed_workspace) -> None:
    database, _ = indexed_workspace
    with (
        Workspace(str(database), read_only=False, create=False) as workspace,
        pytest.raises(ValueError, match="limit"),
    ):
        workspace.search_text("anything", limit=10_000)


def test_search_text_is_case_insensitive(workspace_with_texts: Path) -> None:
    with Workspace(str(workspace_with_texts), read_only=False, create=False) as workspace:
        results = workspace.search_text("MUSEUM")
    assert len(results) == 1
    assert results[0]["url"] == "https://example.test/welcome"
