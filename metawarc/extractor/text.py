"""HTML text projection: script-free, style-free, tag-free plain text."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .envelope import ExtractionLimits


class TextExtractor:
    """Strip HTML into a bounded plain-text blob for the ``texts`` sidecar."""

    name = "beautifulsoup-text"
    version = "1"
    detected_type = "links"
    mimes = frozenset({"text/html", "application/xhtml+xml", "text/xhtml", "text/sgml"})
    extensions = frozenset({"html", "htm", "xhtml", "sgml"})

    # Default per-record text ceiling; payloads above this size yield an
    # empty ``text`` field rather than the full text.
    DEFAULT_MAX_TEXT_BYTES = 1 * 1024 * 1024

    def probe(self, prefix: bytes) -> bool:
        lowered = prefix.lstrip().lower()
        return lowered.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        # Use the same ceiling as the rest of the extraction pipeline
        # unless a tighter per-extractor budget is configured. Payloads
        # above the ceiling still emit a row, with an empty ``text``.
        max_bytes = min(limits.max_payload_bytes, self.DEFAULT_MAX_TEXT_BYTES)
        if len(payload) > max_bytes:
            return {"language": None, "text": "", "truncated": True}
        soup = BeautifulSoup(payload, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        if len(text) > max_bytes:
            text = text[:max_bytes]
        # ``lang`` is exposed as a normalised attribute on the root
        # ``<html>`` element when present.
        html_root = soup.find("html")
        language: str | None = None
        if html_root is not None:
            raw_lang = html_root.get("lang") or html_root.get(
                "{http://www.w3.org/XML/1998/namespace}lang"
            )
            if raw_lang:
                language = str(raw_lang).strip() or None
        return {"language": language, "text": text, "truncated": False}


__all__ = ["TextExtractor"]
