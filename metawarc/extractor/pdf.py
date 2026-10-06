"""PDF metadata extraction via pdfminer.six."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.utils import decode_text

from .envelope import ExtractionLimits


def decode_pdf_metadata_text(value: bytes) -> str:
    """Decode a PDF text string using UTF-16BE BOM or PDFDocEncoding rules."""
    return decode_text(value)


class PdfExtractor:
    name = "pdfminer"
    version = "2"
    detected_type = "pdfs"
    mimes = frozenset({"application/pdf", "application/x-pdf"})
    extensions = frozenset({"pdf"})

    def probe(self, prefix: bytes) -> bool:
        return prefix.startswith(b"%PDF-")

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        with BytesIO(payload) as handle:
            document = PDFDocument(PDFParser(handle))
            if not document.info:
                return None
            result: dict[str, Any] = {}
            for key, value in document.info[0].items():
                if isinstance(value, bytes):
                    result[str(key)] = decode_pdf_metadata_text(value)
                else:
                    result[str(key)] = str(value)
            return result


__all__ = ["PdfExtractor", "decode_pdf_metadata_text"]
