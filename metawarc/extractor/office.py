"""OOXML (Office Open XML) metadata extraction with safe archive handling."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any

from ..constants import MIMES_EXT_TYPE_BY_GROUP as _MAP
from ..errors import ExtractionLimitError
from .envelope import ExtractionLimits, _xml_root


class OoxmlExtractor:
    name = "ooxml-properties"
    detected_type = "ooxmldocs"
    mimes = frozenset(_MAP["ooxmldocs"]["mimes"])
    extensions = frozenset(_MAP["ooxmldocs"]["exts"])

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


__all__ = ["OoxmlExtractor"]
