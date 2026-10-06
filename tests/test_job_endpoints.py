"""REST endpoint tests for ``/jobs/*``."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metawarc.api_server import create_app
from metawarc.indexer import Indexer
from metawarc.settings import ServerSettings


@pytest.fixture
def jobs_app(tmp_path: Path, warc_factory):
    source = warc_factory()
    db_path = str(tmp_path / "collection.db")
    data_dir = str(tmp_path / "collection.data")
    Indexer(batch_size=1).index_records([source], db_path, data_dir=data_dir, silent=True)
    settings = ServerSettings(
        db_path=db_path,
        data_dir=data_dir,
        job_max_concurrent=2,
        request_timeout_seconds=30,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def token() -> str:
    return "secret-token"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _wait_for_terminal(client, job_id: str, token: str, attempts: int = 50) -> dict:
    for _ in range(attempts):
        response = client.get(f"/jobs/{job_id}", headers=_auth(token))
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"succeeded", "failed", "cancelled"}:
            return body
        time.sleep(0.1)
    raise AssertionError("job did not finish in time")


def test_jobs_endpoints_anonymous_when_no_token(jobs_app):
    """Loopback bind without token accepts the new routes."""
    response = jobs_app.get("/jobs")
    assert response.status_code == 200
    assert response.json() == {"total": 0, "items": []}


def test_jobs_post_returns_201_and_location(jobs_app):
    response = jobs_app.post(
        "/jobs",
        json={
            "kind": "export-records",
            "format": "json",
            "limit": 5,
            "filters": {"mimes": "text/html"},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "export-records"
    assert body["status"] == "pending"
    assert body["input"]["format"] == "json"
    assert body["input"]["limit"] == 5
    assert response.headers["Location"] == f"/jobs/{body['id']}"


def test_jobs_post_unknown_kind_returns_422(jobs_app):
    response = jobs_app.post("/jobs", json={"kind": "nonexistent-kind"})
    assert response.status_code == 422


def test_jobs_post_bad_export_format_returns_422(jobs_app):
    response = jobs_app.post("/jobs", json={"kind": "export-records", "format": "yaml"})
    assert response.status_code == 422


def test_jobs_get_unknown_returns_404(jobs_app):
    response = jobs_app.get("/jobs/job-does-not-exist")
    assert response.status_code == 404


def test_jobs_end_to_end_export_records(jobs_app, tmp_path: Path):
    response = jobs_app.post(
        "/jobs",
        json={"kind": "export-records", "format": "json", "limit": 5},
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    finished = _wait_for_terminal(jobs_app, job_id, token="")
    assert finished["status"] == "succeeded"
    assert finished["result"]["rows"] >= 1
    assert finished["started_at"] is not None
    assert finished["ended_at"] is not None

    result = jobs_app.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    body = result.json()
    assert body["job_id"] == job_id
    assert body["format"] == "json"
    assert body["rows"] >= 1
    assert body["size"] > 0
    exported = Path(body["path"])
    assert exported.exists()
    payload = json.loads(exported.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) >= 1


def test_jobs_result_returns_409_for_pending(jobs_app):
    response = jobs_app.post(
        "/jobs",
        json={"kind": "export-records", "format": "csv", "limit": 5},
    )
    job_id = response.json()["id"]
    finished = _wait_for_terminal(jobs_app, job_id, token="")
    assert finished["status"] == "succeeded"


def test_jobs_cancel_returns_409_when_succeeded(jobs_app):
    response = jobs_app.post(
        "/jobs",
        json={"kind": "export-records", "format": "json", "limit": 1},
    )
    job_id = response.json()["id"]
    finished = _wait_for_terminal(jobs_app, job_id, token="")
    assert finished["status"] == "succeeded"

    cancel = jobs_app.delete(f"/jobs/{job_id}")
    assert cancel.status_code == 409


def test_jobs_cancel_unknown_returns_404(jobs_app):
    response = jobs_app.delete("/jobs/job-does-not-exist")
    assert response.status_code == 404


def test_jobs_list_filters_by_status(jobs_app):
    response = jobs_app.post("/jobs", json={"kind": "export-records", "format": "json", "limit": 1})
    job_id = response.json()["id"]
    _wait_for_terminal(jobs_app, job_id, token="")

    response = jobs_app.get("/jobs", params={"status": "succeeded"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(item["status"] == "succeeded" for item in body["items"])

    response = jobs_app.get("/jobs", params={"status": "cancelled"})
    assert response.json()["total"] == 0


def test_jobs_list_rejects_unknown_status(jobs_app):
    response = jobs_app.get("/jobs", params={"status": "bogus"})
    assert response.status_code == 422


def test_jobs_routes_require_auth_when_token_configured(tmp_path: Path, warc_factory):
    source = warc_factory()
    db_path = str(tmp_path / "collection.db")
    data_dir = str(tmp_path / "collection.data")
    Indexer(batch_size=1).index_records([source], db_path, data_dir=data_dir, silent=True)
    settings = ServerSettings(db_path=db_path, data_dir=data_dir, token="secret-token")
    app = create_app(settings)
    with TestClient(app) as client:
        for path, verb in (
            ("/jobs", "get"),
            ("/jobs/job-id", "get"),
            ("/jobs/job-id/result", "get"),
            ("/jobs", "post"),
            ("/jobs/job-id", "delete"),
        ):
            method = getattr(client, verb)
            kwargs = {"json": {"kind": "export-records"}} if verb == "post" else {}
            response = method(path, **kwargs)
            assert response.status_code == 401, (
                f"{verb.upper()} {path} should require auth, got {response.status_code}"
            )

        response = client.get("/jobs", headers=_auth("secret-token"))
        assert response.status_code == 200

        response = client.get("/jobs", headers=_auth("wrong-token"))
        assert response.status_code == 401
