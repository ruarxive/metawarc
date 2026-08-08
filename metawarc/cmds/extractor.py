"""Bounded, registry-based metadata extraction from indexed WARC records."""

from __future__ import annotations

import json
import logging
import os
import signal
import tempfile
import threading
import time
import zipfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass, field, replace
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

import pyarrow as pa
import pyarrow.parquet as pq
from bs4 import BeautifulSoup
from fontTools.misc.timeTools import timestampToString
from fontTools.ttLib import TTCollection, TTFont, TTLibError
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from lxml import etree
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.utils import decode_text
from warcio import ArchiveIterator

from ..constants import MIMES_EXT_TYPE_BY_GROUP
from ..errors import ExtractionLimitError, WorkspaceError
from ..progress import ProgressCallback, ProgressEvent, emit_progress
from ..workspace import Workspace, canonical_path

LOGGER = logging.getLogger(__name__)

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


def decode_pdf_metadata_text(value: bytes) -> str:
    """Decode a PDF text string using UTF-16BE BOM or PDFDocEncoding rules."""
    return decode_text(value)


class OoxmlExtractor:
    name = "ooxml-properties"
    detected_type = "ooxmldocs"
    mimes = frozenset(MIMES_EXT_TYPE_BY_GROUP["ooxmldocs"]["mimes"])
    extensions = frozenset(MIMES_EXT_TYPE_BY_GROUP["ooxmldocs"]["exts"])

    def probe(self, prefix: bytes) -> bool:
        return prefix.startswith(b"PK\x03\x04")

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        result: dict[str, Any] = {}
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            members = archive.infolist()
            if len(members) > limits.max_zip_members:
                raise ExtractionLimitError("ZIP member count exceeds limit")
            expanded = 0
            for info in members:
                member = PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ExtractionLimitError("unsafe ZIP member path")
                expanded += info.file_size
                if expanded > limits.max_zip_expanded_bytes:
                    raise ExtractionLimitError("ZIP expanded size exceeds limit")
                compressed = max(info.compress_size, 1)
                if info.file_size / compressed > limits.max_zip_ratio:
                    raise ExtractionLimitError("ZIP compression ratio exceeds limit")
            if "[Content_Types].xml" not in archive.namelist():
                raise ValueError("ZIP payload is not an OOXML OPC package")
            for name in ("docProps/core.xml", "docProps/app.xml"):
                try:
                    info = archive.getinfo(name)
                except KeyError:
                    continue
                if info.file_size > limits.max_xml_bytes:
                    raise ExtractionLimitError(f"{name} exceeds XML limit")
                raw = archive.read(info)
                if len(raw) > limits.max_xml_bytes:
                    raise ExtractionLimitError(f"{name} exceeds XML limit")
                root = _xml_root(raw, limits, name)
                for child in root:
                    key = child.tag.rsplit("}", 1)[-1]
                    result[key] = child.text
        return result or None


class HachoirExtractor:
    name = "hachoir"

    def __init__(
        self,
        detected_type: str,
        mimes: Sequence[str],
        extensions: Sequence[str],
        probe: Callable[[bytes], bool],
    ) -> None:
        self.detected_type = detected_type
        self.mimes = frozenset(mimes)
        self.extensions = frozenset(extensions)
        self._probe = probe

    def probe(self, prefix: bytes) -> bool:
        return self._probe(prefix)

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        with managed_payload_path(payload, "bin", limits) as path:
            parser = createParser(str(path))
            if not parser:
                return None
            try:
                metadata = extractMetadata(parser)
                if not metadata:
                    return None
                result = metadata.exportDictionary()
                return result.get("Metadata", result)
            finally:
                close = getattr(parser, "close", None)
                if callable(close):
                    close()


def _image_probe(prefix: bytes) -> bool:
    return (
        prefix.startswith(
            (
                b"\xff\xd8\xff",
                b"\x89PNG\r\n\x1a\n",
                b"II*\x00",
                b"MM\x00*",
                b"GIF87a",
                b"GIF89a",
                b"BM",
                b"\x00\x00\x01\x00",
                b"\x00\x00\x02\x00",
                b"8BPS",
                b"gimp xcf ",
                b"\xd7\xcd\xc6\x9a",
            )
        )
        or (prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP")
        or (prefix.startswith((b"II", b"MM")) and prefix[8:10] == b"CR")
    )


def _svg_probe(prefix: bytes) -> bool:
    lowered = prefix.lstrip().lower()
    return lowered.startswith(b"<svg") or (
        lowered.startswith(b"<?xml") and b"<svg" in lowered[:4096]
    )


def _video_probe(prefix: bytes) -> bool:
    asf = b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
    return (
        (len(prefix) >= 12 and prefix[4:8] == b"ftyp")
        or (prefix.startswith(b"RIFF") and prefix[8:12] == b"AVI ")
        or prefix.startswith((b"\x1a\x45\xdf\xa3", b"OggS", b"FLV", b".RMF", asf))
        or prefix.startswith(b"\x00\x00\x01\xb3")
    )


def _audio_probe(prefix: bytes) -> bool:
    asf = b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
    return (
        prefix.startswith((b"ID3", b"fLaC", b"OggS", b"MThd", b".snd", b".ra\xfd", asf))
        or (prefix.startswith(b"RIFF") and prefix[8:12] == b"WAVE")
        or (prefix.startswith(b"FORM") and prefix[8:12] in {b"AIFF", b"AIFC"})
        or (len(prefix) >= 2 and prefix[0] == 0xFF and (prefix[1] & 0xE0) == 0xE0)
        or (len(prefix) >= 12 and prefix[4:8] == b"ftyp")
    )


def _font_probe(prefix: bytes) -> bool:
    return prefix.startswith(
        (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1", b"ttcf", b"wOFF", b"wOF2")
    ) or (len(prefix) >= 36 and prefix[34:36] == b"LP")


def _trim_metadata_text(value: str | None, limit: int = 8192) -> str | None:
    if value is None:
        return None
    compact = " ".join(value.split())
    if not compact:
        return None
    return compact if len(compact) <= limit else compact[:limit] + "…"


def _svg_child_text(root: etree._Element, names: Sequence[str]) -> str | None:
    expected = set(names)
    for element in root.iter():
        if isinstance(element.tag, str) and element.tag.rsplit("}", 1)[-1] in expected:
            return _trim_metadata_text("".join(element.itertext()))
    return None


class SvgExtractor:
    name = "svg-xml"
    version = "1"
    detected_type = "images"
    mimes = frozenset({"image/svg+xml"})
    extensions = frozenset({"svg"})

    def probe(self, prefix: bytes) -> bool:
        return _svg_probe(prefix)

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        try:
            root = _xml_root(payload, limits, "SVG payload")
        except etree.XMLSyntaxError:
            marker = b"<svg"
            position = payload.lower().find(marker)
            if position < 0:
                raise
            known_namespaces = {
                b"xlink": b"http://www.w3.org/1999/xlink",
                b"rdf": b"http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                b"dc": b"http://purl.org/dc/elements/1.1/",
                b"cc": b"http://creativecommons.org/ns#",
            }
            declarations = b"".join(
                b" xmlns:" + prefix + b'="' + uri + b'"'
                for prefix, uri in known_namespaces.items()
                if prefix + b":" in payload and b"xmlns:" + prefix not in payload
            )
            if not declarations:
                raise
            patched = (
                payload[: position + len(marker)] + declarations + payload[position + len(marker) :]
            )
            root = _xml_root(patched, limits, "SVG payload")
        if not isinstance(root.tag, str) or root.tag.rsplit("}", 1)[-1].lower() != "svg":
            raise ValueError("XML payload is not an SVG document")
        references = 0
        external_references = 0
        for element in root.iter():
            if not isinstance(element.tag, str):
                continue
            for attr_name, value in element.attrib.items():
                if attr_name.rsplit("}", 1)[-1] not in {"href", "src"}:
                    continue
                references += 1
                if value.strip().lower().startswith(("http://", "https://", "//")):
                    external_references += 1
        metadata_nodes = [
            _trim_metadata_text("".join(element.itertext()))
            for element in root.iter()
            if isinstance(element.tag, str) and element.tag.rsplit("}", 1)[-1] == "metadata"
        ]
        result = {
            "MIME type": "image/svg+xml",
            "Image width": root.get("width"),
            "Image height": root.get("height"),
            "View box": root.get("viewBox"),
            "Version": root.get("version"),
            "Language": root.get("{http://www.w3.org/XML/1998/namespace}lang") or root.get("lang"),
            "Title": _svg_child_text(root, ("title",)),
            "Description": _svg_child_text(root, ("desc", "description")),
            "Creator": _svg_child_text(root, ("creator",)),
            "Creation date": _svg_child_text(root, ("created", "date")),
            "Modification date": _svg_child_text(root, ("modified",)),
            "Reference count": references,
            "External reference count": external_references,
            "Metadata": [value for value in metadata_nodes if value],
        }
        return {key: value for key, value in result.items() if value not in (None, [], "")}


class WebpExtractor:
    name = "webp-header"
    version = "1"
    detected_type = "images"
    mimes = frozenset({"image/webp"})
    extensions = frozenset({"webp"})

    def probe(self, prefix: bytes) -> bool:
        return prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        if not self.probe(payload[:16]) or len(payload) < 20:
            raise ValueError("payload is not a WebP image")
        chunk = payload[12:16]
        width: int | None = None
        height: int | None = None
        if chunk == b"VP8X" and len(payload) >= 30:
            width = int.from_bytes(payload[24:27], "little") + 1
            height = int.from_bytes(payload[27:30], "little") + 1
        elif chunk == b"VP8 " and len(payload) >= 30 and payload[23:26] == b"\x9d\x01\x2a":
            width = int.from_bytes(payload[26:28], "little") & 0x3FFF
            height = int.from_bytes(payload[28:30], "little") & 0x3FFF
        elif chunk == b"VP8L" and len(payload) >= 25 and payload[20] == 0x2F:
            bits = int.from_bytes(payload[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
        result: dict[str, Any] = {"MIME type": "image/webp", "Chunk type": chunk.decode("ascii")}
        if width is not None:
            result["Image width"] = width
        if height is not None:
            result["Image height"] = height
        return result


FONT_NAME_IDS = {
    0: "Copyright",
    1: "Family",
    2: "Subfamily",
    4: "Full name",
    5: "Version",
    6: "PostScript name",
    7: "Trademark",
    8: "Manufacturer",
    9: "Designer",
    13: "License",
    14: "License URL",
}


def _font_name_metadata(font: TTFont) -> dict[str, str]:
    if "name" not in font:
        return {}
    values: dict[str, str] = {}
    for record in font["name"].names:
        key = FONT_NAME_IDS.get(record.nameID)
        if key is None or key in values:
            continue
        try:
            value = _trim_metadata_text(record.toUnicode(), 4096)
        except Exception:
            continue
        if value:
            values[key] = value
    return values


def _font_metadata(font: TTFont) -> dict[str, Any]:
    result: dict[str, Any] = _font_name_metadata(font)
    if "head" in font:
        result["Units per em"] = int(font["head"].unitsPerEm)
        result["Created"] = timestampToString(font["head"].created)
        result["Modified"] = timestampToString(font["head"].modified)
    if "maxp" in font:
        result["Glyph count"] = int(font["maxp"].numGlyphs)
    if "OS/2" in font:
        vendor = font["OS/2"].achVendID
        if isinstance(vendor, bytes):
            vendor = vendor.decode("latin-1", errors="replace")
        result["Vendor"] = str(vendor).strip()
    return {key: value for key, value in result.items() if value not in (None, "")}


def _eot_metadata(payload: bytes) -> dict[str, Any]:
    if len(payload) < 84 or payload[34:36] != b"LP":
        raise ValueError("payload is not an Embedded OpenType font")
    offset = 82
    labels = ("Family", "Subfamily", "Version", "Full name", "Root string")
    result: dict[str, Any] = {
        "Format": "Embedded OpenType",
        "EOT size": int.from_bytes(payload[0:4], "little"),
        "Font data size": int.from_bytes(payload[4:8], "little"),
        "Version number": int.from_bytes(payload[8:12], "little"),
        "Weight": int.from_bytes(payload[28:32], "little"),
    }
    for label in labels:
        if offset + 2 > len(payload):
            break
        size = int.from_bytes(payload[offset : offset + 2], "little")
        offset += 2
        if size < 0 or offset + size > len(payload):
            raise ValueError("invalid EOT name table length")
        value = _trim_metadata_text(payload[offset : offset + size].decode("utf-16le", "replace"))
        offset += size
        if value:
            result[label] = value
    return result


class FontExtractor:
    name = "fonttools"
    version = "1"
    detected_type = "fonts"
    mimes = frozenset(MIMES_EXT_TYPE_BY_GROUP["fonts"]["mimes"])
    extensions = frozenset(MIMES_EXT_TYPE_BY_GROUP["fonts"]["exts"])

    def probe(self, prefix: bytes) -> bool:
        return _font_probe(prefix)

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        if len(payload) > limits.max_temporary_bytes:
            raise ExtractionLimitError("font payload exceeds temporary storage limit")
        if len(payload) >= 36 and payload[34:36] == b"LP":
            return _eot_metadata(payload)
        try:
            if payload.startswith(b"ttcf"):
                collection = TTCollection(BytesIO(payload), lazy=True)
                try:
                    faces = [_font_metadata(font) for font in collection.fonts]
                finally:
                    collection.close()
                result = dict(faces[0]) if faces else {}
                result["Collection faces"] = len(faces)
                result["Faces"] = faces
                return result or None
            font = TTFont(BytesIO(payload), lazy=True)
            try:
                return _font_metadata(font) or None
            finally:
                font.close()
        except TTLibError as exc:
            raise ValueError(f"invalid font payload: {exc}") from exc


class LinkExtractor:
    name = "beautifulsoup-links"
    detected_type = "links"
    mimes = frozenset({"text/html", "application/xhtml+xml", "text/xhtml", "text/sgml"})
    extensions = frozenset({"html", "htm", "xhtml", "sgml"})

    def probe(self, prefix: bytes) -> bool:
        lowered = prefix.lstrip().lower()
        return lowered.startswith((b"<!doctype html", b"<html", b"<a "))

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        root = BeautifulSoup(payload, "lxml")
        base = root.find("base", href=True)
        links = []
        for anchor in root.find_all("a"):
            links.append(
                {
                    "target": anchor.get("href"),
                    "text": anchor.get_text(" ", strip=True),
                    "class": anchor.get("class"),
                    "id": anchor.get("id"),
                }
            )
        return {"base_url": base.get("href") if base else None, "links": links}


class ExtractorRegistry:
    """Select extractors using normalized MIME, extension, and bounded probes."""

    def __init__(self, extractors: Sequence[MetadataExtractor] | None = None) -> None:
        image_config = MIMES_EXT_TYPE_BY_GROUP["images"]
        binary_image_mimes = tuple(
            item for item in image_config["mimes"] if item not in {"image/svg+xml", "image/webp"}
        )
        binary_image_extensions = tuple(
            item for item in image_config["exts"] if item not in {"svg", "webp"}
        )
        defaults: list[MetadataExtractor] = [
            PdfExtractor(),
            OoxmlExtractor(),
            SvgExtractor(),
            WebpExtractor(),
            HachoirExtractor(
                "images",
                binary_image_mimes,
                binary_image_extensions,
                _image_probe,
            ),
            HachoirExtractor(
                "videos",
                MIMES_EXT_TYPE_BY_GROUP["videos"]["mimes"],
                MIMES_EXT_TYPE_BY_GROUP["videos"]["exts"],
                _video_probe,
            ),
            HachoirExtractor(
                "audio",
                MIMES_EXT_TYPE_BY_GROUP["audio"]["mimes"],
                MIMES_EXT_TYPE_BY_GROUP["audio"]["exts"],
                _audio_probe,
            ),
            FontExtractor(),
            HachoirExtractor(
                "oledocs",
                (
                    "application/msword",
                    "application/vnd.ms-excel",
                    "application/vnd.ms-powerpoint",
                ),
                ("doc", "xls", "ppt"),
                lambda prefix: prefix.startswith(b"\xd0\xcf\x11\xe0"),
            ),
            LinkExtractor(),
        ]
        self.extractors: list[MetadataExtractor] = (
            list(extractors) if extractors is not None else defaults
        )

    def select(
        self,
        *,
        mime: str | None,
        filename: str,
        prefix: bytes,
        expected_type: str | None = None,
    ) -> tuple[MetadataExtractor | None, list[str]]:
        normalized = normalize_mime(mime)
        extension = _extension(filename)
        warnings: list[str] = []
        candidates = [
            item
            for item in self.extractors
            if expected_type is None or item.detected_type == expected_type
        ]
        mime_matches = [item for item in candidates if normalized in item.mimes]
        ext_matches = [item for item in candidates if extension in item.extensions]
        if expected_type != "links" and _looks_like_html(prefix) and (mime_matches or ext_matches):
            warnings.append("Payload appears to be HTML; refusing binary format selection")
            return None, warnings
        if mime_matches and ext_matches and mime_matches[0] is not ext_matches[0]:
            warnings.append(
                f"MIME {normalized!r} conflicts with extension {extension!r}; MIME took precedence"
            )
        if mime_matches:
            return mime_matches[0], warnings
        if ext_matches:
            if normalized:
                warnings.append(f"Unsupported MIME {normalized!r}; selected by extension")
            return ext_matches[0], warnings
        probe_matches = [item for item in candidates if item.probe(prefix[:4096])]
        if probe_matches:
            warnings.append("Selected extractor by bounded signature probe")
            return probe_matches[0], warnings
        return None, warnings


DEFAULT_REGISTRY = ExtractorRegistry()


def read_payload_limited(record: Any, limits: ExtractionLimits) -> bytes:
    expected = getattr(record, "payload_length", None)
    if expected is not None and int(expected or 0) > limits.max_payload_bytes:
        raise ExtractionLimitError("payload exceeds configured byte limit")
    output = BytesIO()
    stream = record.content_stream()
    while chunk := stream.read(min(1024 * 1024, limits.max_payload_bytes + 1)):
        output.write(chunk)
        if output.tell() > limits.max_payload_bytes:
            raise ExtractionLimitError("payload exceeds configured byte limit")
    return output.getvalue()


def extract_record(
    record: Any,
    *,
    archive_id: str,
    warc_id: str,
    url: str,
    filename: str,
    source: str,
    mime: str | None,
    expected_type: str | None = None,
    registry: ExtractorRegistry = DEFAULT_REGISTRY,
    limits: ExtractionLimits | None = None,
) -> MetadataEnvelope:
    limits = limits or DEFAULT_EXTRACTION_LIMITS
    started = time.monotonic()
    envelope = MetadataEnvelope(
        archive_id=archive_id,
        warc_id=warc_id,
        source=source,
        filename=filename,
        ext=_extension(filename),
        url=url,
        declared_mime=normalize_mime(mime),
    )
    try:
        payload = read_payload_limited(record, limits)
        envelope.bytes_inspected = len(payload)
        extractor, warnings = registry.select(
            mime=mime,
            filename=filename,
            prefix=payload[:4096],
            expected_type=expected_type,
        )
        envelope.warnings.extend(warnings)
        if extractor is None:
            envelope.error_code = "unsupported-format"
            envelope.error_message = "No extractor matched the record"
            return envelope
        envelope.extractor = extractor.name
        envelope.extractor_version = str(getattr(extractor, "version", "1"))
        envelope.detected_type = extractor.detected_type
        with extraction_deadline(limits.max_duration_seconds):
            envelope.metadata = extractor.extract(payload, limits)
        envelope.normalized = normalize_metadata(envelope.metadata)
        if envelope.metadata is None:
            envelope.warnings.append("Extractor recognized the format but returned no metadata")
    except ExtractionLimitError as exc:
        envelope.error_code = "limit-exceeded"
        envelope.error_message = str(exc)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        LOGGER.info("Metadata extraction failed for %s: %s", url, exc)
        envelope.error_code = "parser-failed"
        envelope.error_message = str(exc)
    finally:
        envelope.duration_ms = int((time.monotonic() - started) * 1000)
    return envelope


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
        "modified": lower.get("modified")
        or lower.get("modification date")
        or lower.get("last modification")
        or lower.get("lastmodifiedby"),
        "application": lower.get("application") or lower.get("producer"),
        "duration": lower.get("duration"),
        "width": lower.get("image width") or lower.get("width"),
        "height": lower.get("image height") or lower.get("height"),
        "font_family": lower.get("family"),
        "copyright": lower.get("copyright"),
    }
    return {key: value for key, value in result.items() if value is not None} or None


def processWarcRecord(
    record: Any,
    url: str,
    filename: str,
    mime: str | None = None,
    source: str | None = None,
    fields: Any = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Compatibility wrapper returning the historical result shape."""
    envelope = extract_record(
        record,
        archive_id="",
        warc_id="",
        url=url,
        filename=filename,
        source=source or "",
        mime=mime,
    )
    return {
        "source": source,
        "filename": filename,
        "ext": envelope.ext,
        "url": url,
        "mime": mime,
        "metadata": envelope.metadata,
        "error": envelope.error_code is not None,
        "msg": envelope.error_message,
    }


class ContentIndexer:
    """Extract typed metadata from catalog-selected WARC records."""

    VALID_TYPES = frozenset(
        {"links", "pdfs", "images", "ooxmldocs", "oledocs", "videos", "audio", "fonts"}
    )

    def __init__(
        self,
        *,
        batch_size: int = 1_000,
        registry: ExtractorRegistry = DEFAULT_REGISTRY,
        limits: ExtractionLimits | None = None,
    ) -> None:
        self.batch_size = batch_size
        self.registry = registry
        self.limits = limits or DEFAULT_EXTRACTION_LIMITS

    def index_by_table_type(
        self,
        fromfiles: Sequence[str | Path] | None = None,
        tofile: str = "warcindex.db",
        table_type: str = "links",
        rescan: bool = False,
        silent: bool = True,
        *,
        data_dir: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        if table_type not in self.VALID_TYPES:
            raise ValueError(f"metadata type must be one of {', '.join(sorted(self.VALID_TYPES))}")
        with Workspace(tofile, data_dir=data_dir) as workspace:
            archives = self._selected_archives(workspace, fromfiles)
            request = {"archives": [item["id"] for item in archives], "type": table_type}
            with workspace.writer_lock(f"index-content:{table_type}"):
                run_id = workspace.start_run("index-content", request)
                summary: dict[str, Any] = {
                    "run_id": run_id,
                    "type": table_type,
                    "processed": 0,
                    "skipped": 0,
                    "failed": 0,
                    "items": 0,
                    "errors": 0,
                    "warnings": 0,
                    "bytes_inspected": 0,
                    "duration_ms": 0,
                }
                emit_progress(
                    progress,
                    ProgressEvent(
                        operation="index-content",
                        phase="archives",
                        task_id=table_type,
                        label=f"Index {table_type}",
                        unit="archive",
                        total=len(archives),
                        scope="overall",
                        context={"metadata_type": table_type},
                    ),
                )
                try:
                    for position, archive in enumerate(archives, start=1):
                        task_id = f"{table_type}:{archive['id']}"
                        if workspace.active_sidecars(table_type, [archive["id"]]) and not rescan:
                            summary["skipped"] += 1
                            emit_progress(
                                progress,
                                ProgressEvent(
                                    operation="index-content",
                                    phase="candidates",
                                    task_id=task_id,
                                    label=f"{table_type}: {Path(archive['source_path']).name}",
                                    unit="record",
                                    total=0,
                                    status="skipped",
                                    context={
                                        "metadata_type": table_type,
                                        "archive_id": archive["id"],
                                    },
                                ),
                            )
                            emit_progress(
                                progress,
                                self._content_overall_event(
                                    table_type, position, len(archives), summary
                                ),
                            )
                            continue
                        last_event: ProgressEvent | None = None

                        def track(event: ProgressEvent) -> None:
                            nonlocal last_event
                            last_event = event
                            emit_progress(progress, event)

                        try:
                            count, errors, warnings, inspected, duration = self._index_archive(
                                workspace,
                                run_id,
                                archive,
                                table_type,
                                silent=silent,
                                progress=track,
                            )
                            summary["processed"] += 1
                            summary["items"] += count
                            summary["errors"] += errors
                            summary["warnings"] += warnings
                            summary["bytes_inspected"] += inspected
                            summary["duration_ms"] += duration
                        except Exception:
                            LOGGER.exception(
                                "Content indexing failed for %s", archive["source_path"]
                            )
                            summary["failed"] += 1
                            if last_event is not None:
                                emit_progress(progress, replace(last_event, status="failed"))
                        emit_progress(
                            progress,
                            self._content_overall_event(
                                table_type, position, len(archives), summary
                            ),
                        )
                    if not archives:
                        emit_progress(
                            progress,
                            self._content_overall_event(table_type, 0, 0, summary),
                        )
                    status = "complete" if summary["failed"] == 0 else "partial"
                    workspace.finish_run(run_id, status=status, summary=summary)
                    return summary
                except BaseException as exc:
                    workspace.finish_run(run_id, status="failed", summary=summary, error=str(exc))
                    raise

    @staticmethod
    def _content_overall_event(
        table_type: str,
        completed: int,
        total: int,
        summary: dict[str, Any],
    ) -> ProgressEvent:
        return ProgressEvent(
            operation="index-content",
            phase="archives",
            task_id=table_type,
            label=f"Index {table_type}",
            unit="archive",
            completed=completed,
            total=total,
            scope="overall",
            status=(
                "failed"
                if completed == total and summary["failed"]
                else "complete"
                if completed == total
                else "running"
            ),
            counters={
                "processed": int(summary["processed"]),
                "skipped": int(summary["skipped"]),
                "failed": int(summary["failed"]),
            },
            context={"metadata_type": table_type},
        )

    def _selected_archives(
        self, workspace: Workspace, fromfiles: Sequence[str | Path] | None
    ) -> list[dict[str, Any]]:
        if fromfiles is None:
            return workspace.list_archives()
        selected = []
        for item in fromfiles:
            archive = workspace.find_archive_by_source(canonical_path(item))
            if archive is None:
                raise WorkspaceError(f"Source is not indexed: {item}")
            selected.append(archive)
        return selected

    def _candidate_cursor(
        self, workspace: Workspace, archive_id: str, table_type: str
    ) -> tuple[Any, int]:
        paths = workspace.active_sidecar_paths("records", [archive_id])
        if not paths:
            raise WorkspaceError(f"No records sidecar for archive {archive_id}")
        group = "html" if table_type == "links" else table_type
        config = MIMES_EXT_TYPE_BY_GROUP[group]
        mimes = tuple(normalize_mime(item) for item in config["mimes"])
        exts = tuple(item.lower() for item in config["exts"])
        mime_marks = ",".join("?" for _ in mimes)
        ext_marks = ",".join("?" for _ in exts)
        parameters = [paths, *mimes, *exts]
        total_row = workspace.con.execute(
            f"""
            SELECT COUNT(*) FROM read_parquet(?)
            WHERE c_type IN ({mime_marks}) OR ext IN ({ext_marks})
            """,
            parameters,
        ).fetchone()
        total = int(total_row[0]) if total_row else 0
        cursor = workspace.con.execute(
            f"""
            SELECT archive_id, warc_id, url, filename, c_type, ext, source, "offset"
            FROM read_parquet(?)
            WHERE c_type IN ({mime_marks}) OR ext IN ({ext_marks})
            ORDER BY "offset"
            """,
            parameters,
        )
        return cursor, total

    def _index_archive(
        self,
        workspace: Workspace,
        run_id: str,
        archive: dict[str, Any],
        table_type: str,
        *,
        silent: bool,
        progress: ProgressCallback | None,
    ) -> tuple[int, int, int, int, int]:
        cursor, candidate_total = self._candidate_cursor(workspace, archive["id"], table_type)
        columns = [item[0] for item in cursor.description]
        stage = workspace.temporary_directory(run_id, archive["id"])
        schema = LINK_SCHEMA if table_type == "links" else METADATA_SCHEMA
        rows: list[dict[str, Any]] = []
        parts: list[Path] = []
        batch = 0
        errors = 0
        warnings = 0
        inspected = 0
        duration = 0
        candidates = 0

        def flush() -> None:
            nonlocal rows, batch
            if not rows:
                return
            batch += 1
            part = stage / f"{table_type}-{batch:08d}.parquet"
            pq.write_table(pa.Table.from_pylist(rows, schema=schema), part, compression="zstd")
            parts.append(part)
            rows = []

        source = canonical_path(archive["source_path"])
        task_id = f"{table_type}:{archive['id']}"
        emit_progress(
            progress,
            ProgressEvent(
                operation="index-content",
                phase="candidates",
                task_id=task_id,
                label=f"{table_type}: {source.name}",
                unit="record",
                total=candidate_total,
                context={"metadata_type": table_type, "archive_id": archive["id"]},
            ),
        )
        with source.open("rb") as handle:
            while records := cursor.fetchmany(256):
                for values in records:
                    candidates += 1
                    item = dict(zip(columns, values, strict=True))
                    handle.seek(int(item["offset"]))
                    try:
                        record = next(ArchiveIterator(handle))
                    except StopIteration:
                        errors += 1
                        emit_progress(
                            progress,
                            ProgressEvent(
                                operation="index-content",
                                phase="candidates",
                                task_id=task_id,
                                label=f"{table_type}: {source.name}",
                                unit="record",
                                completed=candidates,
                                total=candidate_total,
                                counters={"errors": errors, "warnings": warnings},
                                context={
                                    "metadata_type": table_type,
                                    "archive_id": archive["id"],
                                },
                            ),
                        )
                        continue
                    envelope = extract_record(
                        record,
                        archive_id=item["archive_id"],
                        warc_id=item["warc_id"],
                        url=item["url"],
                        filename=item["filename"],
                        source=item["source"],
                        mime=item["c_type"],
                        expected_type=table_type,
                        registry=self.registry,
                        limits=self.limits,
                    )
                    if envelope.error_code:
                        errors += 1
                    warnings += len(envelope.warnings)
                    inspected += envelope.bytes_inspected
                    duration += envelope.duration_ms
                    if table_type == "links":
                        base_url = (envelope.metadata or {}).get("base_url")
                        for link in (envelope.metadata or {}).get("links", []):
                            rows.append(
                                {
                                    "archive_id": envelope.archive_id,
                                    "warc_id": envelope.warc_id,
                                    "source": envelope.source,
                                    "url": envelope.url,
                                    "base_url": base_url,
                                    "target": link.get("target"),
                                    "text": link.get("text"),
                                    "class_json": json.dumps(link.get("class")),
                                    "element_id": link.get("id"),
                                }
                            )
                    else:
                        rows.append(envelope.to_row())
                    if len(rows) >= self.batch_size:
                        flush()
                    emit_progress(
                        progress,
                        ProgressEvent(
                            operation="index-content",
                            phase="candidates",
                            task_id=task_id,
                            label=f"{table_type}: {source.name}",
                            unit="record",
                            completed=candidates,
                            total=candidate_total,
                            counters={"errors": errors, "warnings": warnings},
                            context={
                                "metadata_type": table_type,
                                "archive_id": archive["id"],
                            },
                        ),
                    )
        flush()
        destination = workspace.new_sidecar_path(archive["id"], run_id, table_type)
        if parts:
            count = workspace.combine_parquet_parts(parts, destination, schema=schema)
        else:
            temp = destination.with_suffix(".tmp")
            pq.write_table(pa.Table.from_pylist([], schema=schema), temp, compression="zstd")
            os.replace(temp, destination)
            count = 0
        workspace.publish_sidecar(
            archive_id=archive["id"],
            kind=table_type,
            path=destination,
            num_items=count,
            run_id=run_id,
        )
        emit_progress(
            progress,
            ProgressEvent(
                operation="index-content",
                phase="candidates",
                task_id=task_id,
                label=f"{table_type}: {source.name}",
                unit="record",
                completed=candidates,
                total=candidate_total,
                status="complete",
                counters={"items": count, "errors": errors, "warnings": warnings},
                context={"metadata_type": table_type, "archive_id": archive["id"]},
            ),
        )
        return count, errors, warnings, inspected, duration

    def dump_metadata(
        self,
        fromfiles: Sequence[str | Path] | None = None,
        tofile: str = "warcindex.db",
        metadata_type: str = "ooxmldocs",
        output: str | None = None,
        silent: bool = True,
        *,
        data_dir: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> int:
        with Workspace(tofile, data_dir=data_dir, read_only=True, create=False) as workspace:
            archives = self._selected_archives(workspace, fromfiles)
            paths = workspace.active_sidecar_paths(metadata_type, [item["id"] for item in archives])
            if not paths:
                emit_progress(
                    progress,
                    ProgressEvent(
                        operation="dump-metadata",
                        phase="rows",
                        task_id=metadata_type,
                        label=f"Export {metadata_type}",
                        unit="row",
                        total=0,
                        scope="overall",
                        status="complete",
                    ),
                )
                return 0
            total_row = workspace.con.execute(
                "SELECT COUNT(*) FROM read_parquet(?)", [paths]
            ).fetchone()
            total = int(total_row[0]) if total_row else 0
            cursor = workspace.con.execute("SELECT * FROM read_parquet(?)", [paths])
            columns = [item[0] for item in cursor.description]
            output_path = Path(output) if output else None
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if output_path.exists():
                    raise WorkspaceError(f"Output exists; refusing to overwrite: {output_path}")
            output_context = (
                output_path.open("x", encoding="utf-8") if output_path else nullcontext()
            )
            count = 0
            emit_progress(
                progress,
                ProgressEvent(
                    operation="dump-metadata",
                    phase="rows",
                    task_id=metadata_type,
                    label=f"Export {metadata_type}",
                    unit="row",
                    total=total,
                    scope="overall",
                ),
            )
            with output_context as handle:
                while rows := cursor.fetchmany(256):
                    for row in rows:
                        value = json.dumps(
                            dict(zip(columns, row, strict=True)),
                            ensure_ascii=False,
                            default=str,
                        )
                        if handle:
                            handle.write(value + "\n")
                        else:
                            print(value)
                        count += 1
                        emit_progress(
                            progress,
                            ProgressEvent(
                                operation="dump-metadata",
                                phase="rows",
                                task_id=metadata_type,
                                label=f"Export {metadata_type}",
                                unit="row",
                                completed=count,
                                total=total,
                                scope="overall",
                            ),
                        )
            emit_progress(
                progress,
                ProgressEvent(
                    operation="dump-metadata",
                    phase="rows",
                    task_id=metadata_type,
                    label=f"Export {metadata_type}",
                    unit="row",
                    completed=count,
                    total=total,
                    scope="overall",
                    status="complete",
                ),
            )
            return count


class Extractor:
    """Legacy direct-WARC metadata export implemented with the hardened registry."""

    def metadata_by_ext(
        self,
        fromfile: str,
        file_types: Sequence[str] | None = None,
        fields: Any = None,
        output: str = "metadata.jsonl",
    ) -> None:
        source = canonical_path(fromfile)
        with source.open("rb") as handle, Path(output).open("w", encoding="utf-8") as target:
            for record in ArchiveIterator(handle, arc2warc=True):
                if record.rec_type != "response" or record.http_headers is None:
                    continue
                url = record.rec_headers.get_header("WARC-Target-URI") or ""
                filename = url.split("?", 1)[0].rsplit("/", 1)[-1].lower()
                if file_types and _extension(filename) not in file_types:
                    continue
                envelope = extract_record(
                    record,
                    archive_id="",
                    warc_id=record.rec_headers.get_header("WARC-Record-ID") or "",
                    url=url,
                    filename=filename,
                    source=str(source),
                    mime=record.http_headers.get_header("Content-Type"),
                )
                target.write(json.dumps(asdict(envelope), ensure_ascii=False, default=str) + "\n")


__all__ = [
    "ContentIndexer",
    "DEFAULT_REGISTRY",
    "ExtractionLimits",
    "Extractor",
    "ExtractorRegistry",
    "LINK_SCHEMA",
    "METADATA_SCHEMA",
    "MetadataEnvelope",
    "decode_pdf_metadata_text",
    "extract_record",
    "normalize_mime",
    "processWarcRecord",
]
