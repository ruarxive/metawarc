import zipfile
from typing import Any

from lxml import etree

from .envelope import ExtractionLimits, managed_payload_path

_TEXT_TAG = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_PARAGRAPH_TAG = f"{_W_NS}p"


def _open_document_xml(payload: bytes, limits: ExtractionLimits) -> bytes | None:
    """Open ``word/document.xml`` from a zip payload, or None on failure."""
    if len(payload) > limits.max_payload_bytes:
        return None
    try:
        with (
            managed_payload_path(payload, "bin", limits) as path,
            zipfile.ZipFile(str(path), "r") as archive,
            archive.open("word/document.xml") as handle,
        ):
            return handle.read(limits.max_payload_bytes + 1)
    except (KeyError, zipfile.BadZipFile, OSError):
        return None


class OoxmlTextExtractor:
    """Project OOXML paragraph text into the shared ``texts`` sidecar."""

    name = "ooxml-text"
    version = "1"
    detected_type = "links"
    mimes = frozenset(
        {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
    )
    extensions = frozenset({"docx", "xlsx", "pptx"})

    def probe(self, prefix: bytes) -> bool:
        return prefix.startswith(b"PK\x03\x04")

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        if len(payload) > limits.max_payload_bytes:
            return {"language": None, "text": "", "truncated": True}
        xml_bytes = _open_document_xml(payload, limits)
        if xml_bytes is None:
            return {"language": None, "text": "", "truncated": False}
        if len(xml_bytes) > limits.max_payload_bytes:
            xml_bytes = xml_bytes[: limits.max_payload_bytes]
        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError:
            return {"language": None, "text": "", "truncated": False}
        paragraphs: list[str] = []
        for paragraph in root.iter(_PARAGRAPH_TAG):
            text = "".join(t.text or "" for t in paragraph.iter(_TEXT_TAG))
            text = text.strip()
            if text:
                paragraphs.append(text)
        text = " ".join(paragraphs)
        if len(text) > limits.max_payload_bytes:
            text = text[: limits.max_payload_bytes]
        return {"language": None, "text": text, "truncated": False}


__all__ = ["OoxmlTextExtractor"]
