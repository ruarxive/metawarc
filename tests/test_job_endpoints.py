"""REST endpoint tests for ``/jobs/*``."""

from __future__ import annotations

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


@pytest.mark.parametrize(
    "filters",
    [
        {"unknown": "value"},
        {"status_min": 500, "status_max": 400},
        {"size_min": -1},
    ],
)
def test_jobs_post_invalid_filters_returns_422_without_persisting(jobs_app, filters):
    response = jobs_app.post(
        "/jobs",
        json={"kind": "export-records", "filters": filters},
    )

    assert response.status_code == 422
    assert jobs_app.get("/jobs").json() == {"total": 0, "items": []}


@pytest.mark.parametrize("suffix", ["", "result", "result/content"])
def test_jobs_unknown_routes_return_404(jobs_app, suffix: str):
    response = jobs_app.get(f"/jobs/job-does-not-exist/{suffix}".rstrip("/"))
    assert response.status_code == 404


@pytest.mark.parametrize("format_", ["json", "csv", "parquet"])
def test_jobs_end_to_end_download(jobs_app, format_: str):
    response = jobs_app.post(
        "/jobs",
        json={"kind": "export-records", "format": format_, "limit": 5},
    )
    assert response.status_code == 201
    assert response.json()["progress"] is None
    job_id = response.json()["id"]

    finished = _wait_for_terminal(jobs_app, job_id, token="")
    assert finished["status"] == "succeeded"
    assert finished["result"]["rows"] >= 1
    assert finished["started_at"] is not None
    assert finished["ended_at"] is not None
    assert "path" not in finished["result"]
    assert finished["result"]["download_url"] == f"/jobs/{job_id}/result/content"
    assert finished["progress"]["processed_rows"] == finished["result"]["rows"]
    assert finished["progress"]["total_rows"] == finished["result"]["rows"]

    listed = jobs_app.get("/jobs").json()["items"]
    listed_job = next(item for item in listed if item["id"] == job_id)
    listed_result = listed_job["result"]
    assert "path" not in listed_result
    assert listed_result["download_url"] == finished["result"]["download_url"]
    assert listed_job["progress"] == finished["progress"]

    result = jobs_app.get(f"/jobs/{job_id}/result")
    assert result.status_code == 200
    body = result.json()
    assert body["job_id"] == job_id
    assert body["format"] == format_
    assert body["rows"] >= 1
    assert body["size"] > 0
    assert "path" not in body
    assert body["download_url"] == finished["result"]["download_url"]

    downloaded = jobs_app.get(body["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["cache-control"] == "no-store"
    assert downloaded.headers["content-length"] == str(body["size"])
    assert downloaded.headers["content-disposition"] == (
        f'attachment; filename="metawarc-{job_id}.{format_}"'
    )
    expected_media_types = {
        "json": "application/json",
        "csv": "text/csv; charset=utf-8",
        "parquet": "application/vnd.apache.parquet",
    }
    assert downloaded.headers["content-type"] == expected_media_types[format_]

    local_path = jobs_app.app.state.job_runner.get(job_id).result["path"]
    assert downloaded.content == Path(local_path).read_bytes()
    assert len(downloaded.content) == body["size"]
    if format_ == "json":
        assert len(downloaded.json()) >= 1
    elif format_ == "csv":
        assert len(downloaded.text.splitlines()) >= 2
    else:
        import io

        import pyarrow.parquet as pq

        assert pq.read_table(io.BytesIO(downloaded.content)).num_rows >= 1


def _persist_result_job(client, *, format_: str = "json", status: str = "succeeded"):
    from metawarc.jobs import Job, JobKind

    store = client.app.state.job_runner.store
    job = Job.new(JobKind.EXPORT_RECORDS, {"format": format_, "limit": 1})
    job.status = status
    job.result = {
        "path": str(store.result_path(job, f".{format_}")),
        "format": format_,
        "rows": 1,
        "size": 999,
    }
    store.save(job)
    return job, store


@pytest.mark.parametrize("path_kind", ["absolute", "traversal"])
def test_jobs_result_rejects_external_persisted_path(jobs_app, tmp_path: Path, path_kind: str):
    job, store = _persist_result_job(jobs_app)
    external = tmp_path / "external.json"
    external.write_text("secret", encoding="utf-8")
    job.result["path"] = (
        str(external) if path_kind == "absolute" else str(tmp_path / ".." / "external.json")
    )
    store.save(job)

    for suffix in ("result", "result/content"):
        response = jobs_app.get(f"/jobs/{job.id}/{suffix}")
        assert response.status_code == 404
        assert response.content != b"secret"
        assert str(tmp_path) not in response.text


def test_jobs_result_ignores_external_path_when_internal_file_exists(jobs_app, tmp_path: Path):
    job, store = _persist_result_job(jobs_app)
    external = tmp_path / "external.json"
    external.write_text("secret", encoding="utf-8")
    internal = store.result_path(job, ".json")
    internal.write_bytes(b"[]\n")
    job.result["path"] = str(external)
    store.save(job)

    metadata = jobs_app.get(f"/jobs/{job.id}/result")
    assert metadata.status_code == 200
    assert metadata.json()["size"] == 3
    downloaded = jobs_app.get(f"/jobs/{job.id}/result/content")
    assert downloaded.status_code == 200
    assert downloaded.content == b"[]\n"
    assert store.load(job.id).result["path"] == str(external)


@pytest.mark.parametrize("artifact_kind", ["missing", "directory", "symlink", "wrong-format"])
def test_jobs_result_rejects_invalid_artifact(jobs_app, tmp_path: Path, artifact_kind: str):
    format_ = "yaml" if artifact_kind == "wrong-format" else "json"
    job, store = _persist_result_job(jobs_app, format_=format_)
    target = store.result_path(job, ".json")
    if artifact_kind == "directory":
        target.mkdir()
    elif artifact_kind == "symlink":
        external = tmp_path / "external.json"
        external.write_text("secret", encoding="utf-8")
        try:
            target.symlink_to(external)
        except OSError:
            pytest.skip("creating symlinks requires additional platform permission")
    elif artifact_kind == "missing":
        target.write_text("temporary", encoding="utf-8")
        target.unlink()

    for suffix in ("result", "result/content"):
        response = jobs_app.get(f"/jobs/{job.id}/{suffix}")
        assert response.status_code == 404
        assert response.content != b"secret"
        assert str(tmp_path) not in response.text


@pytest.mark.parametrize("status", ["pending", "running", "failed", "cancelled"])
def test_jobs_result_routes_return_409_for_non_succeeded(jobs_app, status: str, monkeypatch):
    runner = jobs_app.app.state.job_runner
    monkeypatch.setattr(runner, "_schedule", lambda job_id: None)
    job, _ = _persist_result_job(jobs_app, status=status)
    for suffix in ("result", "result/content"):
        response = jobs_app.get(f"/jobs/{job.id}/{suffix}")
        assert response.status_code == 409
        assert response.json()["detail"].startswith(f"Job is {status}")


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
            ("/jobs/job-id/result/content", "get"),
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

        job, store = _persist_result_job(client)
        store.result_path(job, ".json").write_bytes(b"[]\n")
        for suffix in ("result", "result/content"):
            path = f"/jobs/{job.id}/{suffix}"
            rejected = client.get(path, headers=_auth("wrong-token"))
            assert rejected.status_code == 401
            assert b"[]\n" not in rejected.content
            accepted = client.get(path, headers=_auth("secret-token"))
            assert accepted.status_code == 200
        assert accepted.content == b"[]\n"

        response = client.get("/jobs", headers=_auth("wrong-token"))
        assert response.status_code == 401
