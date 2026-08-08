"""Tests for website replay resolution, rewriting, serve routes, and CDXJ export."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from metawarc.cmds.indexer import Indexer
from metawarc.cmds.server import create_app
from metawarc.core import cli
from metawarc.query import QueryService
from metawarc.replay import (
    ReplayError,
    ReplayService,
    export_cdxj,
    rewrite_css,
    rewrite_html,
    surt_key,
)
from metawarc.settings import ServerSettings
from metawarc.workspace import Workspace


def _index(tmp_path: Path, warc_factory, records: list[dict], name: str = "replay.warc"):
    source = warc_factory(name, records)
    database = tmp_path / "replay.db"
    summary = Indexer(batch_size=8).index_records([source], str(database), silent=True)
    assert summary.failed == 0
    return database, source


def test_find_capture_closest_and_exact(tmp_path: Path, warc_factory):
    records = [
        {
            "id": "<urn:uuid:early>",
            "url": "https://example.test/page",
            "mime": "text/html",
            "payload": b"<html><body>early</body></html>",
            "warc_headers": {"WARC-Date": "2020-01-01T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:late>",
            "url": "https://example.test/page",
            "mime": "text/html",
            "payload": b"<html><body>late</body></html>",
            "warc_headers": {"WARC-Date": "2020-01-03T00:00:00Z"},
        },
    ]
    database, _ = _index(tmp_path, warc_factory, records)
    with Workspace(database, read_only=True, create=False) as workspace:
        service = QueryService(workspace)
        closest = service.find_capture(
            "https://example.test/page",
            "20200101120000",
            policy="closest",
        )
        assert closest is not None
        assert closest["warc_id"] == "urn:uuid:early"
        exact = service.find_capture(
            "https://example.test/page",
            datetime(2020, 1, 3, tzinfo=UTC),
            policy="exact",
        )
        assert exact is not None
        assert exact["warc_id"] == "urn:uuid:late"
        assert (
            service.find_capture(
                "https://example.test/missing",
                "20200101120000",
                policy="closest",
            )
            is None
        )


def test_find_capture_closest_compressed(tmp_path: Path, warc_factory):
    records = [
        {
            "id": "<urn:uuid:gz>",
            "url": "https://example.test/gz",
            "mime": "text/plain",
            "payload": b"gzipped",
            "warc_headers": {"WARC-Date": "2021-06-15T12:00:00Z"},
        }
    ]
    database, _ = _index(tmp_path, warc_factory, records, name="replay.warc.gz")
    with Workspace(database, read_only=True, create=False) as workspace:
        row = QueryService(workspace).find_capture(
            "https://example.test/gz", "20210615120000", policy="closest"
        )
        assert row is not None
        assert row["warc_id"] == "urn:uuid:gz"


def test_redirect_hop_limit(tmp_path: Path, warc_factory):
    records = [
        {
            "id": "<urn:uuid:r1>",
            "url": "https://example.test/a",
            "status": "302 Found",
            "mime": "text/html",
            "headers": [("Location", "https://example.test/b")],
            "payload": b"",
            "warc_headers": {"WARC-Date": "2020-01-01T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:r2>",
            "url": "https://example.test/b",
            "status": "302 Found",
            "mime": "text/html",
            "headers": [("Location", "https://example.test/c")],
            "payload": b"",
            "warc_headers": {"WARC-Date": "2020-01-01T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:r3>",
            "url": "https://example.test/c",
            "mime": "text/html",
            "payload": b"<html><body>done</body></html>",
            "warc_headers": {"WARC-Date": "2020-01-01T00:00:00Z"},
        },
    ]
    database, _ = _index(tmp_path, warc_factory, records)
    with Workspace(database, read_only=True, create=False) as workspace:
        service = ReplayService(workspace, redirect_hops=1)
        start = service.find_capture("https://example.test/a", "20200101000000")
        with pytest.raises(ReplayError, match="hop limit"):
            service.follow_redirects(start, "20200101000000", max_hops=1)
        final = ReplayService(workspace, redirect_hops=5).follow_redirects(
            start, "20200101000000"
        )
        assert final["warc_id"] == "urn:uuid:r3"


def test_html_css_rewrite_and_banner():
    html = (
        b"<html><head><link rel='stylesheet' href='https://example.test/a.css'>"
        b"<script>window.x='https://example.test/keep.js'</script></head>"
        b"<body><img src='/logo.png'><a href='https://example.test/next'>n</a></body></html>"
    )
    rewritten = rewrite_html(html, "https://example.test/page", "20200101120000mp_").decode()
    assert "/replay/20200101120000mp_/https://example.test/a.css" in rewritten
    assert "/replay/20200101120000mp_/https://example.test/logo.png" in rewritten
    assert "/replay/20200101120000mp_/https://example.test/next" in rewritten
    assert "https://example.test/keep.js" in rewritten
    assert "metawarc-replay-banner" in rewritten
    css = rewrite_css(
        "body{background:url('https://example.test/bg.png')}",
        "https://example.test/a.css",
        "20200101120000mp_",
    )
    assert "/replay/20200101120000mp_/https://example.test/bg.png" in css


def test_rewrite_preserves_utf8_and_cp1251_cyrillic():
    title = "Территориальный орган статистики"
    utf_payload = (
        "<html><head><meta charset='utf-8'><title>"
        f"{title}</title></head><body><p>{title}</p>"
        "<a href='https://example.test/далее'>x</a></body></html>"
    ).encode()
    rewritten = rewrite_html(
        utf_payload,
        "https://example.test/",
        "20200101120000mp_",
        content_type="text/html; charset=UTF-8",
    ).decode("utf-8")
    assert title in rewritten
    assert "Ð¢ÐµÑ" not in rewritten

    cp_payload = (
        "<html><head><meta http-equiv='Content-Type' "
        "content='text/html; charset=windows-1251'>"
        f"<title>{title}</title></head><body><p>{title}</p></body></html>"
    ).encode("cp1251")
    rewritten_cp = rewrite_html(
        cp_payload,
        "https://example.test/",
        "20200101120000mp_",
        content_type="text/html; charset=windows-1251",
    ).decode("utf-8")
    assert title in rewritten_cp
    assert "charset=utf-8" in rewritten_cp.lower() or 'charset="utf-8"' in rewritten_cp.lower()


def test_serve_replay_routes_and_identity_mode(tmp_path: Path, warc_factory):
    records = [
        {
            "id": "<urn:uuid:home>",
            "url": "https://example.test/",
            "mime": "text/html",
            "payload": (
                b"<html><body><link rel='stylesheet' href='https://example.test/site.css'>"
                b"<img src='https://example.test/pixel.png'></body></html>"
            ),
            "warc_headers": {"WARC-Date": "2020-02-02T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:css>",
            "url": "https://example.test/site.css",
            "mime": "text/css",
            "payload": b"body{background:url('https://example.test/pixel.png')}",
            "warc_headers": {"WARC-Date": "2020-02-02T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:img>",
            "url": "https://example.test/pixel.png",
            "mime": "image/png",
            "payload": b"\x89PNG\r\n\x1a\n",
            "warc_headers": {"WARC-Date": "2020-02-02T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:go>",
            "url": "https://example.test/go",
            "status": "302 Found",
            "mime": "text/html",
            "headers": [("Location", "https://example.test/")],
            "payload": b"",
            "warc_headers": {"WARC-Date": "2020-02-02T00:00:00Z"},
        },
    ]
    database, _ = _index(tmp_path, warc_factory, records)
    client = TestClient(create_app(ServerSettings(db_path=str(database))))

    page = client.get("/replay/20200202000000mp_/https://example.test/")
    assert page.status_code == 200
    assert "metawarc-replay-banner" in page.text
    assert "/replay/20200202000000mp_/https://example.test/site.css" in page.text
    assert page.headers["memento-datetime"]
    assert 'rel="original"' in page.headers["link"]

    raw = client.get("/replay/20200202000000id_/https://example.test/")
    assert raw.status_code == 200
    assert "metawarc-replay-banner" not in raw.text
    assert "https://example.test/site.css" in raw.text

    css = client.get("/replay/20200202000000mp_/https://example.test/site.css")
    assert css.status_code == 200
    assert "/replay/20200202000000mp_/https://example.test/pixel.png" in css.text

    image = client.get("/replay/20200202000000/https://example.test/pixel.png")
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")

    redirected = client.get(
        "/replay/20200202000000/https://example.test/go", follow_redirects=False
    )
    assert redirected.status_code == 302
    assert redirected.headers["location"].endswith(
        "/replay/20200202000000mp_/https://example.test/"
    )

    home = client.get("/")
    assert home.status_code == 200
    assert "text/html" in home.headers["content-type"]
    assert "example.test" in home.text
    assert "/replay/20200202000000mp_/https://example.test/" in home.text
    assert client.get("/replay").status_code == 200
    sites = client.get("/replay/sites")
    assert sites.status_code == 200
    payload = sites.json()
    assert payload[0]["host"] == "example.test"
    assert payload[0]["entry_url"] == "https://example.test/"
    assert payload[0]["replay_path"].endswith("/https://example.test/")


def test_home_prefers_site_root_across_hosts(tmp_path: Path, warc_factory):
    records = [
        {
            "id": "<urn:uuid:a-deep>",
            "url": "https://alpha.test/docs/page",
            "mime": "text/html",
            "payload": b"<html><body>deep</body></html>",
            "warc_headers": {"WARC-Date": "2020-03-01T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:a-root>",
            "url": "https://alpha.test/",
            "mime": "text/html",
            "payload": b"<html><body>root</body></html>",
            "warc_headers": {"WARC-Date": "2020-03-02T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:b>",
            "url": "https://beta.test/about",
            "mime": "text/html",
            "payload": b"<html><body>beta</body></html>",
            "warc_headers": {"WARC-Date": "2020-03-03T00:00:00Z"},
        },
    ]
    database, _ = _index(tmp_path, warc_factory, records)
    with Workspace(database, read_only=True, create=False) as workspace:
        sites = ReplayService(workspace).list_sites()
    by_host = {item["host"]: item for item in sites}
    assert by_host["alpha.test"]["entry_url"] == "https://alpha.test/"
    assert by_host["beta.test"]["entry_url"] == "https://beta.test/about"


def test_home_prefers_https_root_over_http_redirect(tmp_path: Path, warc_factory):
    records = [
        {
            "id": "<urn:uuid:http-redirect>",
            "url": "http://gamma.test/",
            "status": "301 Moved Permanently",
            "mime": "text/html",
            "headers": [("Location", "https://gamma.test/")],
            "payload": b"<html><body>moved</body></html>",
            "warc_headers": {"WARC-Date": "2020-04-01T00:00:00Z"},
        },
        {
            "id": "<urn:uuid:https-root>",
            "url": "https://gamma.test/",
            "mime": "text/html",
            "payload": b"<html><body>ok</body></html>",
            "warc_headers": {"WARC-Date": "2020-04-02T00:00:00Z"},
        },
    ]
    database, _ = _index(tmp_path, warc_factory, records)
    with Workspace(database, read_only=True, create=False) as workspace:
        sites = ReplayService(workspace).list_sites()
    assert sites[0]["entry_url"] == "https://gamma.test/"


def test_export_cdxj_and_cli(tmp_path: Path, warc_factory):
    records = [
        {
            "id": "<urn:uuid:cdx>",
            "url": "https://www.example.test/docs?x=1",
            "mime": "text/html",
            "payload": b"<html></html>",
            "warc_headers": {"WARC-Date": "2019-05-01T08:30:00Z"},
        }
    ]
    database, source = _index(tmp_path, warc_factory, records)
    cdxj = tmp_path / "out.cdxj"
    paths = tmp_path / "paths.tsv"
    with Workspace(database, read_only=True, create=False) as workspace:
        result = export_cdxj(workspace, cdxj, path_index=paths)
    assert result["records"] == 1
    line = cdxj.read_text().strip()
    assert line.startswith(surt_key("https://www.example.test/docs?x=1"))
    assert "20190501083000" in line
    assert source.name in line
    assert paths.read_text().startswith(f"{source.name}\t")

    runner = CliRunner()
    cli_out = tmp_path / "cli.cdxj"
    exported = runner.invoke(
        cli,
        [
            "export-cdxj",
            "--dbfile",
            str(database),
            "--output",
            str(cli_out),
            "--output-format",
            "json",
        ],
    )
    assert exported.exit_code == 0, exported.output
    assert cli_out.exists()
    help_replay = runner.invoke(cli, ["replay", "--help"])
    assert help_replay.exit_code == 0
