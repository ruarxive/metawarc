"""Unit tests for ``metawarc.settings`` environment helpers."""

from __future__ import annotations

import pytest

from metawarc.settings import is_loopback


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "127.0.0.2",
        "127.1.2.3",
        "::1",
        "0:0:0:0:0:0:0:1",
        "0:0:0:0:0:0:0:0001",
        "[::1]",
        "localhost",
        "LOCALHOST",
        " 127.0.0.1 ",
    ],
)
def test_is_loopback_accepts_canonical_loopback(host: str) -> None:
    assert is_loopback(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "0.0.0.0",
        "::",
        "192.168.1.1",
        "10.0.0.1",
        "8.8.8.8",
        "[fe80::1]",
        "example.com",
        "loopback",
    ],
)
def test_is_loopback_rejects_non_loopback(host: str) -> None:
    assert is_loopback(host) is False


@pytest.mark.parametrize("host", ["", "   ", "not-an-ip", "127.0.0.1:8000", "[unbalanced"])
def test_is_loopback_treats_invalid_as_non_loopback(host: str) -> None:
    """An invalid host string MUST be reported as non-loopback.

    The caller in :mod:`metawarc.core` raises the documented security
    message on the non-loopback path, so the malformed-input case
    should reach the same branch.
    """
    assert is_loopback(host) is False
