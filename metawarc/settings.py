"""Environment-backed settings for optional remote interfaces."""

from __future__ import annotations

import os
from dataclasses import dataclass


def env_str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip()
    return normalized or default


def env_bool(name: str, default: bool = False) -> bool:
    value = env_str(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = env_str(name)
    return int(value) if value is not None else default


@dataclass(frozen=True)
class ServerSettings:
    db_path: str = "warcindex.db"
    data_dir: str | None = None
    host: str = "127.0.0.1"
    port: int = 8000
    mcp_port: int = 8191
    token: str | None = None
    max_page: int = 500
    max_payload_bytes: int = 128 * 1024 * 1024
    request_timeout_seconds: int = 30
    max_concurrency: int = 16

    @classmethod
    def from_env(cls) -> ServerSettings:
        return cls(
            db_path=env_str("METAWARC_DB_PATH", "warcindex.db") or "warcindex.db",
            data_dir=env_str("METAWARC_DATA_DIR"),
            host=env_str("METAWARC_HOST", "127.0.0.1") or "127.0.0.1",
            port=env_int("METAWARC_PORT", 8000),
            mcp_port=env_int("METAWARC_MCP_PORT", 8191),
            token=env_str("METAWARC_API_TOKEN"),
            max_page=env_int("METAWARC_MAX_PAGE", 500),
            max_payload_bytes=env_int("METAWARC_MAX_PAYLOAD_BYTES", 128 * 1024 * 1024),
            request_timeout_seconds=env_int("METAWARC_REQUEST_TIMEOUT", 30),
            max_concurrency=env_int("METAWARC_MAX_CONCURRENCY", 16),
        )


def is_loopback(host: str) -> bool:
    return host.lower() in {"127.0.0.1", "::1", "localhost"}


__all__ = ["ServerSettings", "env_bool", "env_int", "env_str", "is_loopback"]
