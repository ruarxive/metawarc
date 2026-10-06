"""Smoke tests for the ``python -m metawarc`` entry point."""

from __future__ import annotations

import re
import subprocess
import sys

PACKAGE_VERSION = "2.0.3"


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "metawarc", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_python_m_metawarc_version() -> None:
    """`python -m metawarc --version` exits 0 and prints the package version."""
    result = _run_module("--version")
    assert result.returncode == 0, result.stderr
    assert PACKAGE_VERSION in result.stdout


def test_python_m_metawarc_help_lists_commands() -> None:
    """`python -m metawarc --help` exits 0 and lists the documented commands."""
    result = _run_module("--help")
    assert result.returncode == 0, result.stderr
    for command in (
        "index",
        "list-files",
        "stats",
        "dump",
        "doctor",
        "catalog",
        "serve",
        "mcp",
        "analyze",
    ):
        assert command in result.stdout, f"missing command {command!r} in --help output"


def test_python_m_metawarc_help_references_version_flag() -> None:
    """The --help output documents the --version flag as a meta-option."""
    result = _run_module("--help")
    assert result.returncode == 0, result.stderr
    assert "--version" in result.stdout


def test_python_m_metawarc_unknown_command_exits_nonzero() -> None:
    """An unknown command exits nonzero with a useful error."""
    result = _run_module("definitely-not-a-real-command")
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert re.search(r"no such command", combined, re.IGNORECASE) or "Error" in combined
