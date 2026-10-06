"""Tests for :class:`OoxmlTextExtractor`."""

from __future__ import annotations

import io
import zipfile
from typing import Final

import pytest

from metawarc.extractor import DEFAULT_EXTRACTION_LIMITS, ExtractionLimits, OoxmlTextExtractor


def _make_docx(paragraphs: list[str]) -> bytes:
    """Build a minimal OOXML zip with a ``word/document.xml`` body."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        paragraphs_xml = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{paragraphs_xml}</w:body></w:document>",
        )
    return buf.getvalue()


def _empty_zip() -> bytes:
    """Return a zip containing no entries at all."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED):
        pass
    return buf.getvalue()


SAMPLE_DOCX: Final[bytes] = _make_docx(
    [
        "Welcome to the museum of modern art",
        "Hello visitors from the exhibit",
    ]
)


@pytest.fixture
def limits() -> ExtractionLimits:
    return DEFAULT_EXTRACTION_LIMITS


def test_ooxml_text_extractor_probes_zip_prefix(limits: ExtractionLimits) -> None:
    extractor = OoxmlTextExtractor()
    assert extractor.probe(SAMPLE_DOCX[:4]) is True
    assert extractor.probe(b"random bytes") is False


def test_ooxml_text_extractor_extracts_text(limits: ExtractionLimits) -> None:
    extractor = OoxmlTextExtractor()
    result = extractor.extract(SAMPLE_DOCX, limits)
    assert result is not None
    assert "museum" in result["text"]
    assert "Hello visitors from the exhibit" in result["text"]


def test_ooxml_text_extractor_returns_empty_on_missing_document_xml(
    limits: ExtractionLimits,
) -> None:
    extractor = OoxmlTextExtractor()
    result = extractor.extract(_empty_zip(), limits)
    assert result == {"language": None, "text": "", "truncated": False}


def test_ooxml_text_extractor_handles_invalid_zip(limits: ExtractionLimits) -> None:
    extractor = OoxmlTextExtractor()
    result = extractor.extract(b"PK\x03\x04not actually a zip", limits)
    assert result == {"language": None, "text": "", "truncated": False}


def test_ooxml_text_extractor_re_exported() -> None:
    from metawarc import extractor as extractor_pkg

    assert hasattr(extractor_pkg, "OoxmlTextExtractor")
    assert extractor_pkg.OoxmlTextExtractor is OoxmlTextExtractor
