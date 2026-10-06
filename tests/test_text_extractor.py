"""Tests for the :class:`TextExtractor` HTML-to-text projection."""

from __future__ import annotations

import pytest

from metawarc.extractor import (
    DEFAULT_EXTRACTION_LIMITS,
    ExtractionLimits,
    TextExtractor,
)

SAMPLE_HTML = b"""<!doctype html>
<html lang="en">
<head><title>Test page</title>
<style>body { color: red; }</style>
<script>window.alert('hi');</script>
</head>
<body>
<noscript>Enable JavaScript</noscript>
<h1>Heading</h1>
<p>Hello world</p>
</body>
</html>
"""

SAMPLE_NO_HTML = b"raw text payload without HTML tags"


@pytest.fixture
def limits() -> ExtractionLimits:
    return DEFAULT_EXTRACTION_LIMITS


def test_text_extractor_strips_scripts_and_styles(limits: ExtractionLimits) -> None:
    extractor = TextExtractor()
    payload = SAMPLE_HTML
    assert extractor.probe(payload[:64]) is True
    result = extractor.extract(payload, limits)
    assert result is not None
    assert result["truncated"] is False
    assert result["language"] == "en"
    text = result["text"]
    assert "Hello world" in text
    assert "window.alert" not in text
    assert "color: red" not in text
    assert "Enable JavaScript" not in text


def test_text_extractor_keeps_visible_text(limits: ExtractionLimits) -> None:
    extractor = TextExtractor()
    result = extractor.extract(b"<html><body><p>foo bar baz</p></body></html>", limits)
    assert result is not None
    assert "foo bar baz" in result["text"]


def test_text_extractor_handles_oversized_payload() -> None:
    extractor = TextExtractor()
    big_payload = (
        b"<html><body>" + b"x" * (TextExtractor.DEFAULT_MAX_TEXT_BYTES + 1) + b"</body></html>"
    )
    result = extractor.extract(big_payload, DEFAULT_EXTRACTION_LIMITS)
    assert result is not None
    assert result["truncated"] is True
    assert result["text"] == ""


def test_text_extractor_reports_no_language_when_unset(limits: ExtractionLimits) -> None:
    extractor = TextExtractor()
    result = extractor.extract(b"<html><body><p>text</p></body></html>", limits)
    assert result is not None
    assert result["language"] is None


def test_text_extractor_detects_probes_html_prefixes(limits: ExtractionLimits) -> None:
    extractor = TextExtractor()
    for prefix in (b"<!doctype html>", b"<html>", b"<head>", b"<body>"):
        assert extractor.probe(prefix) is True
    assert extractor.probe(b"random bytes") is False


def test_text_extractor_module_is_re_exported() -> None:
    from metawarc import extractor as extractor_pkg

    assert hasattr(extractor_pkg, "TextExtractor")
    assert extractor_pkg.TextExtractor is TextExtractor
