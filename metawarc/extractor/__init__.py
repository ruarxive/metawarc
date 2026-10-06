"""Metadata extraction from WARC payloads via a per-format registry.

The package exposes the same public API as the legacy single-file module;
internal organization moved to a small per-format split so the next format
family can land without pushing any module past the 500-LOC threshold.

Public API (re-exported from the per-format modules):

- :mod:`envelope` — schemas, ``ExtractionLimits``, ``MetadataEnvelope``,
  ``MetadataExtractor`` protocol, signal helpers, ``extraction_deadline``,
  ``managed_payload_path``, ``normalize_metadata``, ``normalize_mime``.
- :mod:`pdf` — ``PdfExtractor`` and ``decode_pdf_metadata_text``.
- :mod:`office` — ``OoxmlExtractor``.
- :mod:`links` — ``LinkExtractor``.
- :mod:`media` — ``FontExtractor``, ``HachoirExtractor``, ``SvgExtractor``,
  ``WebpExtractor`` plus binary probes.
- :mod:`registry` — ``ExtractorRegistry`` and the ``DEFAULT_REGISTRY``.
- :mod:`record` — ``Extractor``, ``extract_record``, ``processWarcRecord``,
  ``read_payload_limited``.
- :mod:`indexer` — ``ContentIndexer``.
"""

from __future__ import annotations

from ..errors import ExtractionLimitError
from .envelope import (
    DEFAULT_EXTRACTION_LIMITS,
    LINK_SCHEMA,
    METADATA_SCHEMA,
    METADATA_SCHEMA_VERSION,
    TEXT_SCHEMA,
    ExtractionLimits,
    MetadataEnvelope,
    MetadataExtractor,
    _extension,
    _looks_like_html,
    _svg_child_text,
    _trim_metadata_text,
    _xml_root,
    extraction_deadline,
    managed_payload_path,
    normalize_metadata,
    normalize_mime,
)
from .indexer import ContentIndexer
from .links import LinkExtractor
from .media import (
    FONT_NAME_IDS,
    FontExtractor,
    HachoirExtractor,
    SvgExtractor,
    WebpExtractor,
    _audio_probe,
    _font_probe,
    _image_probe,
    _svg_probe,
    _video_probe,
)
from .office import OoxmlExtractor
from .pdf import PDFDocument as _PDFDocument  # for backward-compat tests
from .pdf import PdfExtractor, decode_pdf_metadata_text
from .record import Extractor, extract_record, processWarcRecord, read_payload_limited
from .registry import DEFAULT_REGISTRY, ExtractorRegistry, get_text_registry
from .text import TextExtractor
from .text_ooxml import OoxmlTextExtractor
from .text_pdf import PdfTextExtractor


def __getattr__(name: str) -> object:
    """Re-export ``PDFDocument`` for backward compatibility with older tests."""
    if name == "PDFDocument":
        return _PDFDocument
    raise AttributeError(name)


__all__ = [
    "ContentIndexer",
    "DEFAULT_EXTRACTION_LIMITS",
    "DEFAULT_REGISTRY",
    "ExtractionLimitError",
    "Extractor",
    "ExtractorRegistry",
    "ExtractionLimits",
    "get_text_registry",
    "FONT_NAME_IDS",
    "FontExtractor",
    "HachoirExtractor",
    "LINK_SCHEMA",
    "LinkExtractor",
    "METADATA_SCHEMA",
    "METADATA_SCHEMA_VERSION",
    "MetadataEnvelope",
    "MetadataExtractor",
    "TEXT_SCHEMA",
    "OoxmlExtractor",
    "PdfExtractor",
    "SvgExtractor",
    "OoxmlTextExtractor",
    "PdfTextExtractor",
    "TextExtractor",
    "WebpExtractor",
    "_audio_probe",
    "_extension",
    "_font_probe",
    "_image_probe",
    "_looks_like_html",
    "_svg_child_text",
    "_svg_probe",
    "_trim_metadata_text",
    "_video_probe",
    "_xml_root",
    "decode_pdf_metadata_text",
    "extract_record",
    "extraction_deadline",
    "managed_payload_path",
    "normalize_metadata",
    "normalize_mime",
    "processWarcRecord",
    "read_payload_limited",
]
