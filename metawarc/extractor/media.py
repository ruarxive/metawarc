"""Image, video, audio, and font extractors plus their binary probes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from io import BytesIO
from typing import Any

from fontTools.misc.timeTools import timestampToString
from fontTools.ttLib import TTCollection, TTFont, TTLibError
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from lxml import etree

from ..constants import MIMES_EXT_TYPE_BY_GROUP as _MAP
from ..errors import ExtractionLimitError
from .envelope import (
    ExtractionLimits,
    _svg_child_text,
    _trim_metadata_text,
    _xml_root,
    managed_payload_path,
)


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
        del limits
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
    mimes = frozenset(_MAP["fonts"]["mimes"])
    extensions = frozenset(_MAP["fonts"]["exts"])

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


__all__ = [
    "FONT_NAME_IDS",
    "FontExtractor",
    "HachoirExtractor",
    "SvgExtractor",
    "WebpExtractor",
    "_audio_probe",
    "_font_probe",
    "_image_probe",
    "_svg_probe",
    "_video_probe",
]
