"""Envelope, schemas, limits, signal helpers, and normalization for extraction.

This module is the foundation of the extractor package: every per-format
module and the registry import from it. It owns the PyArrow schemas,
the extraction limits, the versioned metadata envelope, the MIME and
extension normalization helpers, the XML parser wrapper, the
deadline/timeout context manager, and the temporary-path helper.

It deliberately contains no format-specific logic.
"""

from __future__ import annotations

import json
import signal
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import pyarrow as pa
from lxml import etree

from ..errors import ExtractionLimitError

METADATA_SCHEMA_VERSION = 1

METADATA_SCHEMA = pa.schema(
    [
        ("archive_id", pa.string()),
        ("warc_id", pa.string()),
        ("source", pa.string()),
        ("filename", pa.string()),
        ("ext", pa.string()),
        ("url", pa.string()),
        ("declared_mime", pa.string()),
        ("detected_type", pa.string()),
        ("extractor", pa.string()),
        ("extractor_version", pa.string()),
        ("schema_version", pa.int32()),
        ("metadata_json", pa.string()),
        ("normalized_json", pa.string()),
        ("warnings_json", pa.string()),
        ("error_code", pa.string()),
        ("error_message", pa.string()),
        ("bytes_inspected", pa.int64()),
        ("duration_ms", pa.int64()),
    ]
)

LINK_SCHEMA = pa.schema(
    [
        ("archive_id", pa.string()),
        ("warc_id", pa.string()),
        ("source", pa.string()),
        ("url", pa.string()),
        ("base_url", pa.string()),
        ("target", pa.string()),
        ("text", pa.string()),
        ("class_json", pa.string()),
        ("element_id", pa.string()),
    ]
)

TEXT_SCHEMA = pa.schema(
    [
        ("archive_id", pa.string()),
        ("warc_id", pa.string()),
        ("source", pa.string()),
        ("url", pa.string()),
        ("language", pa.string()),
        ("text", pa.string()),
    ]
)


@dataclass(frozen=True)
class ExtractionLimits:
    max_payload_bytes: int = 64 * 1024 * 1024
    max_duration_seconds: float = 30.0
    max_temporary_bytes: int = 64 * 1024 * 1024
    max_zip_members: int = 1_000
    max_zip_expanded_bytes: int = 128 * 1024 * 1024
    max_zip_ratio: float = 200.0
    max_xml_bytes: int = 8 * 1024 * 1024


DEFAULT_EXTRACTION_LIMITS = ExtractionLimits()


@dataclass
class MetadataEnvelope:
    archive_id: str
    warc_id: str
    source: str
    filename: str
    ext: str
    url: str
    declared_mime: str | None
    detected_type: str | None = None
    extractor: str | None = None
    extractor_version: str = "1"
    schema_version: int = METADATA_SCHEMA_VERSION
    metadata: dict[str, Any] | None = None
    normalized: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    bytes_inspected: int = 0
    duration_ms: int = 0

    def to_row(self) -> dict[str, Any]:
        return {
            "archive_id": self.archive_id,
            "warc_id": self.warc_id,
            "source": self.source,
            "filename": self.filename,
            "ext": self.ext,
            "url": self.url,
            "declared_mime": self.declared_mime,
            "detected_type": self.detected_type,
            "extractor": self.extractor,
            "extractor_version": self.extractor_version,
            "schema_version": self.schema_version,
            "metadata_json": json.dumps(self.metadata, ensure_ascii=False, default=str),
            "normalized_json": json.dumps(self.normalized, ensure_ascii=False, default=str),
            "warnings_json": json.dumps(self.warnings, ensure_ascii=False),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "bytes_inspected": self.bytes_inspected,
            "duration_ms": self.duration_ms,
        }


class MetadataExtractor(Protocol):
    name: str
    detected_type: str
    mimes: frozenset[str]
    extensions: frozenset[str]

    def probe(self, prefix: bytes) -> bool: ...

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None: ...


def normalize_mime(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    lower: dict[str, Any] = {}

    def collect(values: dict[str, Any]) -> None:
        for key, value in values.items():
            normalized_key = str(key).lower()
            if isinstance(value, dict):
                collect(value)
            elif normalized_key not in lower:
                lower[normalized_key] = value

    collect(metadata)
    result = {
        "title": lower.get("title"),
        "creator": lower.get("creator") or lower.get("author") or lower.get("designer"),
        "created": lower.get("created") or lower.get("creation date"),
        "modified": (
            lower.get("modified")
            or lower.get("modification date")
            or lower.get("last modification")
            or lower.get("lastmodifiedby")
        ),
        "application": lower.get("application") or lower.get("producer"),
        "duration": lower.get("duration"),
        "width": lower.get("image width") or lower.get("width"),
        "height": lower.get("image height") or lower.get("height"),
        "font_family": lower.get("family"),
        "copyright": lower.get("copyright"),
    }
    return {key: value for key, value in result.items() if value is not None} or None


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _looks_like_html(prefix: bytes) -> bool:
    lowered = prefix.lstrip().lower()
    return lowered.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))


def _xml_root(payload: bytes, limits: ExtractionLimits, name: str) -> etree._Element:
    if len(payload) > limits.max_xml_bytes:
        raise ExtractionLimitError(f"{name} exceeds XML limit")
    lowered = payload.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise ExtractionLimitError(f"{name} contains a forbidden DTD or entity")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
        huge_tree=False,
    )
    return etree.fromstring(payload, parser=parser)


def _trim_metadata_text(value: str | None, limit: int = 8192) -> str | None:
    if value is None:
        return None
    compact = " ".join(value.split())
    if not compact:
        return None
    return compact if len(compact) <= limit else compact[:limit] + "…"


def _svg_child_text(root: etree._Element, names: tuple[str, ...]) -> str | None:
    expected = set(names)
    for element in root.iter():
        if isinstance(element.tag, str) and element.tag.rsplit("}", 1)[-1] in expected:
            return _trim_metadata_text("".join(element.itertext()))
    return None


@contextmanager
def extraction_deadline(seconds: float) -> Iterator[None]:
    """Best-effort hard deadline on POSIX main threads, elapsed check elsewhere."""
    start = time.monotonic()
    armed = (
        seconds > 0
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    )
    old_handler: Any = None

    def timeout_handler(signum: int, frame: Any) -> None:
        raise ExtractionLimitError(f"extraction exceeded {seconds:g} seconds")

    if armed:
        old_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        if armed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
        if time.monotonic() - start > seconds > 0:
            raise ExtractionLimitError(f"extraction exceeded {seconds:g} seconds")


@contextmanager
def managed_payload_path(
    payload: bytes, extension: str, limits: ExtractionLimits
) -> Iterator[Path]:
    if len(payload) > limits.max_temporary_bytes:
        raise ExtractionLimitError("payload exceeds temporary storage limit")
    suffix = f".{extension}" if extension else ".bin"
    with tempfile.TemporaryDirectory(prefix="metawarc-extract-") as directory:
        path = Path(directory) / f"payload{suffix}"
        path.write_bytes(payload)
        yield path


__all__ = [
    "DEFAULT_EXTRACTION_LIMITS",
    "ExtractionLimits",
    "LINK_SCHEMA",
    "METADATA_SCHEMA",
    "METADATA_SCHEMA_VERSION",
    "MetadataEnvelope",
    "MetadataExtractor",
    "TEXT_SCHEMA",
    "_extension",
    "_looks_like_html",
    "_svg_child_text",
    "_trim_metadata_text",
    "_xml_root",
    "extraction_deadline",
    "managed_payload_path",
    "normalize_metadata",
    "normalize_mime",
]
