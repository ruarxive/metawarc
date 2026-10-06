"""HTML link extraction via BeautifulSoup with the lxml backend."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .envelope import ExtractionLimits


class LinkExtractor:
    name = "beautifulsoup-links"
    detected_type = "links"
    mimes = frozenset({"text/html", "application/xhtml+xml", "text/xhtml", "text/sgml"})
    extensions = frozenset({"html", "htm", "xhtml", "sgml"})

    def probe(self, prefix: bytes) -> bool:
        lowered = prefix.lstrip().lower()
        return lowered.startswith((b"<!doctype html", b"<html", b"<a "))

    def extract(self, payload: bytes, limits: ExtractionLimits) -> dict[str, Any] | None:
        del limits  # link extraction has no per-record limits
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


__all__ = ["LinkExtractor"]
