"""Tests for the bearer-token authentication surface in ``metawarc.api_server``."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from metawarc.api_server import create_app
from metawarc.core import cli
from metawarc.settings import ServerSettings

PROTECTED_PATHS = (
    "/health",
    "/warcs/list",
    "/records/list",
    "/records/search",
)


def _settings(database, *, token, host="127.0.0.1") -> ServerSettings:
    return ServerSettings(db_path=str(database), token=token, host=host)


def test_unauthenticated_request_returns_401(indexed_workspace) -> None:
    """A protected endpoint without ``Authorization`` returns 401 when a token is configured."""
    database, _ = indexed_workspace
    with TestClient(create_app(_settings(database, token="secret"))) as client:
        for path in PROTECTED_PATHS:
            params = {"phrase": "museum"} if path == "/records/search" else {}
            response = client.get(path, params=params)
            assert response.status_code == 401, path
            assert "bearer" in response.json()["detail"].lower()


def test_wrong_token_returns_401(indexed_workspace) -> None:
    """An incorrect Bearer credential returns 401 with the same detail message."""
    database, _ = indexed_workspace
    with TestClient(create_app(_settings(database, token="secret"))) as client:
        for path in PROTECTED_PATHS:
            params = {"phrase": "museum"} if path == "/records/search" else {}
            response = client.get(path, params=params, headers={"Authorization": "Bearer not-the-secret"})
            assert response.status_code == 401, path


def test_correct_token_is_accepted(indexed_workspace) -> None:
    """A request with the documented bearer token succeeds."""
    database, _ = indexed_workspace
    with TestClient(create_app(_settings(database, token="secret"))) as client:
        for path in PROTECTED_PATHS:
            params = {"phrase": "museum"} if path == "/records/search" else {}
            response = client.get(path, params=params, headers={"Authorization": "Bearer secret"})
            assert response.status_code == 200, path


def test_no_token_means_no_authentication(indexed_workspace) -> None:
    """When the server is configured without a token, requests succeed without Authorization."""
    database, _ = indexed_workspace
    with TestClient(create_app(_settings(database, token=None))) as client:
        for path in PROTECTED_PATHS:
            params = {"phrase": "museum"} if path == "/records/search" else {}
            response = client.get(path, params=params)
            assert response.status_code == 200, path


def test_replay_endpoints_inherit_auth(indexed_workspace) -> None:
    """Replay routes share the bearer-token enforcement."""
    database, _ = indexed_workspace
    with TestClient(create_app(_settings(database, token="secret"))) as client:
        for path in ("/", "/replay", "/replay/", "/replay/sites"):
            response = client.get(path)
            assert response.status_code == 401, path


def test_malformed_authorization_header_returns_401(indexed_workspace) -> None:
    """An Authorization header that is not ``Bearer <token>`` returns 401."""
    database, _ = indexed_workspace
    with TestClient(create_app(_settings(database, token="secret"))) as client:
        for header in (
            "secret",
            "Token secret",
            "Bearer",
            "Bearer secret extra",
        ):
            response = client.get("/health", headers={"Authorization": header})
            assert response.status_code == 401, header


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "::1",
        "0:0:0:0:0:0:0:1",
        "localhost",
    ],
)
def test_loopback_bind_without_token_passes_guard(host: str) -> None:
    """A loopback bind without a token is permitted; uvicorn is mocked so the test exits."""
    runner = CliRunner()
    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(cli, ["serve", "--host", host])
    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()


def test_non_loopback_bind_without_token_is_rejected() -> None:
    """A non-loopback bind without a token or --allow-insecure is rejected."""
    runner = CliRunner()
    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(cli, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code != 0
    assert "Non-loopback API binding requires" in result.output
    mock_run.assert_not_called()


def test_non_loopback_bind_with_token_passes_guard() -> None:
    """A non-loopback bind with a token is permitted."""
    runner = CliRunner()
    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(cli, ["serve", "--host", "0.0.0.0", "--token", "secret"])
    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()


def test_non_loopback_bind_with_allow_insecure_passes_guard() -> None:
    """A non-loopback bind with --allow-insecure passes the bind check."""
    runner = CliRunner()
    with patch("uvicorn.run") as mock_run:
        result = runner.invoke(cli, ["serve", "--host", "0.0.0.0", "--allow-insecure"])
    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()
