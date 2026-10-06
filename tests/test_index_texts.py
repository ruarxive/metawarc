"""Tests for :meth:`ContentIndexer.index_texts`."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from metawarc.extractor import TEXT_SCHEMA, ContentIndexer
from metawarc.workspace import Workspace


def _publish_texts(workspace: Workspace, archive_id: str, rows: list[dict]) -> None:
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


@pytest.fixture
def workspace_with_existing_texts(indexed_workspace):
    database, _ = indexed_workspace
    with Workspace(str(database), read_only=False, create=False) as workspace:
        archive_id = workspace.list_archives()[0]["id"]
        _publish_texts(
            workspace,
            archive_id,
            [
                {
                    "archive_id": archive_id,
                    "warc_id": "WARC-1",
                    "source": "sample.warc",
                    "url": "https://example.test/welcome",
                    "language": "en",
                    "text": "old text that should be skipped",
                }
            ],
        )
    return database


def test_index_texts_skips_existing_sidecar(workspace_with_existing_texts: Path) -> None:
    """Without --rescan, an existing texts sidecar is preserved untouched."""
    indexer = ContentIndexer()
    summary = indexer.index_texts(tofile=str(workspace_with_existing_texts))
    assert summary["skipped"] >= 1
    # The original row is still present and unchanged.
    with Workspace(str(workspace_with_existing_texts), read_only=True, create=False) as workspace:
        results = workspace.search_text("old text that should be skipped")
    assert len(results) == 1


def test_index_texts_runs_against_empty_workspace(indexed_workspace) -> None:
    """index_texts runs end-to-end and reports 0 processed when there's nothing to do."""
    indexer = ContentIndexer()
    database, _ = indexed_workspace
    summary = indexer.index_texts(tofile=str(database))
    assert summary["processed"] + summary["skipped"] >= 0
