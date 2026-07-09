import pytest
from fastapi.testclient import TestClient

from metawarc import settings
from metawarc.cmds.server import create_app


@pytest.fixture
def api_client(indexed_workspace, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", str(indexed_workspace["db"]))
    return TestClient(create_app())


def test_warcs_list(api_client):
    response = api_client.get("/warcs/list")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["num_records"] >= 1


def test_records_list(api_client):
    response = api_client.get("/records/list", params={"exts": "html"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"] >= 1
    assert any("example.com" in item["url"] for item in payload["items"])


def test_records_list_rejects_unsafe_query(api_client):
    response = api_client.get("/records/list", params={"query": "1=1; DROP TABLE files"})
    assert response.status_code == 400


def test_missing_db_returns_404(tmp_path, monkeypatch):
    missing = tmp_path / "missing.db"
    monkeypatch.setattr(settings, "DB_PATH", str(missing))
    client = TestClient(create_app())
    response = client.get("/warcs/list")
    assert response.status_code == 404


def test_redoc_page_renders(api_client):
    response = api_client.get("/")
    assert response.status_code == 200
    assert "Redoc.init" in response.text
    assert "/openapi.json" in response.text
    assert "redoc-container" in response.text
