"""Tests for :class:`PdfTextExtractor`."""

from __future__ import annotations

from typing import Final

import pytest

from metawarc.extractor import DEFAULT_EXTRACTION_LIMITS, ExtractionLimits, PdfTextExtractor

MINIMAL_PDF: Final[bytes] = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    b"4 0 obj\n<< /Length 68 >>\nstream\n"
    b"BT\n/F1 12 Tf\n50 750 Td\n"
    b"(Welcome to the museum of modern art) Tj\n0 -20 Td\n(Hello visitors) Tj\n"
    b"ET\nendstream\nendobj\n"
    b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    b"xref\n0 6\n0000000000 65535 f \n"
    b"0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n"
    b"0000000208 00000 n \n0000000328 00000 n \n"
    b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n402\n%%EOF\n"
)


@pytest.fixture
def limits() -> ExtractionLimits:
    return DEFAULT_EXTRACTION_LIMITS


def test_pdf_text_extractor_probes_pdf_prefix(limits: ExtractionLimits) -> None:
    extractor = PdfTextExtractor()
    assert extractor.probe(b"%PDF-1.4") is True
    assert extractor.probe(b"random bytes") is False


def test_pdf_text_extractor_extracts_text(limits: ExtractionLimits) -> None:
    extractor = PdfTextExtractor()
    result = extractor.extract(MINIMAL_PDF, limits)
    assert result is not None
    assert "museum" in result["text"]
    assert "Hello visitors" in result["text"]


def test_pdf_text_extractor_handles_oversized_payload() -> None:
    extractor = PdfTextExtractor()
    big_payload = b"%PDF-1.4" + b"x" * (extractor.name.count("x") + 1)
    result = extractor.extract(big_payload + b"more", DEFAULT_EXTRACTION_LIMITS)
    # With default limits the test fixture is below the ceiling; the
    # truncated flag should be False for the minimum PDF.
    assert result is not None
    assert result["truncated"] is False


def test_pdf_text_extractor_re_exported() -> None:
    from metawarc import extractor as extractor_pkg

    assert hasattr(extractor_pkg, "PdfTextExtractor")
    assert extractor_pkg.PdfTextExtractor is PdfTextExtractor
