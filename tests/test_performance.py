from __future__ import annotations

import time
import tracemalloc
from pathlib import Path

import pytest

from metawarc.analysis import AnalysisService
from metawarc.cmds.extractor import ContentIndexer
from metawarc.cmds.indexer import Indexer
from metawarc.workspace import Workspace


@pytest.mark.performance
def test_bounded_index_and_analysis_baseline(warc_factory, tmp_path: Path):
    records = [
        {
            "id": f"<urn:uuid:performance-{index:06d}>",
            "url": f"https://host-{index}.example.test/{index}.html",
            "mime": "text/html",
            "payload": (
                f'<html><a href="https://target-{index}.example.test/x">record-{index}</a></html>'
            ).encode(),
        }
        for index in range(250)
    ]
    source = warc_factory("performance.warc.gz", records)
    database = tmp_path / "performance.db"
    tracemalloc.start()
    started = time.monotonic()
    summary = Indexer(batch_size=25).index_records([source], str(database), silent=True)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert summary.records == 250
    assert peak < 128 * 1024 * 1024
    ContentIndexer(batch_size=25).index_by_table_type(None, str(database), "links", silent=True)
    with Workspace(database, create=False) as workspace:
        collection = AnalysisService(workspace).summary(top=25)
        hashes = AnalysisService(workspace).hash_payloads(batch_size=25)
        links = AnalysisService(workspace).link_graph()
        integrity = AnalysisService(workspace).integrity(deep=True, max_records=50, batch_size=10)
    assert sum(item["count"] for item in collection.data["host"]) == 25
    assert not hashes.failures
    assert len(links.data["records"]) == 250
    assert len(integrity.data["records"]) == 50
    assert time.monotonic() - started < 30
