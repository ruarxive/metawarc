"""Plain-text projection for PDF payloads via pdfminer.six."""

from __future__ import annotations

from typing import Any

from pdfminer.high_level import extract_text as pdfminer_extract_text

from .envelope import ExtractionLimits, managed_payload_path


class PdfTextExtractor:
    """Project PDF page text into the shared ``texts`` sidecar."""

    name = "pdfminer-text"
    version = "1"
    detected_type = "links"
    mimes = frozenset({"application/pdf", "application/x-pdf"})
    extensions = frozenset({"pdf"})

    def probe(self, prefix: bytes) -> bool:
        return prefix.startswith(b"%PDF-")

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        if len(payload) > limits.max_payload_bytes:
            return {"language": None, "text": "", "truncated": True}
        try:
            with managed_payload_path(payload, "pdf", limits) as path:
                text = pdfminer_extract_text(str(path))
        except Exception:  # pragma: no cover - pdfminer surface area is large
            return {"language": None, "text": "", "truncated": False}
        if len(text) > limits.max_payload_bytes:
            text = text[: limits.max_payload_bytes]
        text = " ".join(text.split())
        return {"language": None, "text": text, "truncated": False}


__all__ = ["PdfTextExtractor"]
