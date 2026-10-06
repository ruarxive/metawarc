"""Extractor registry and the default registration order."""

from __future__ import annotations

from collections.abc import Sequence

from ..constants import MIMES_EXT_TYPE_BY_GROUP
from .envelope import (
    MetadataExtractor,
    _extension,
    _looks_like_html,
    normalize_mime,
)
from .links import LinkExtractor
from .media import (
    FontExtractor,
    HachoirExtractor,
    SvgExtractor,
    WebpExtractor,
    _audio_probe,
    _image_probe,
    _video_probe,
)
from .office import OoxmlExtractor
from .pdf import PdfExtractor
from .text import TextExtractor
from .text_ooxml import OoxmlTextExtractor
from .text_pdf import PdfTextExtractor


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
            PdfTextExtractor(),
            OoxmlExtractor(),
            OoxmlTextExtractor(),
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
            TextExtractor(),
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


__all__ = ["DEFAULT_REGISTRY", "ExtractorRegistry"]
