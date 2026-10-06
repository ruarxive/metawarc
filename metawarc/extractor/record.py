"""Per-record extraction: payload read, selection, normalization, and legacy facade."""

from __future__ import annotations

import logging
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from warcio import ArchiveIterator

from ..errors import ExtractionLimitError
from ..workspace import canonical_path
from .envelope import (
    DEFAULT_EXTRACTION_LIMITS,
    ExtractionLimits,
    MetadataEnvelope,
    _extension,
    extraction_deadline,
    normalize_metadata,
    normalize_mime,
)
from .registry import DEFAULT_REGISTRY, ExtractorRegistry

LOGGER = logging.getLogger(__name__)


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
    del fields, debug
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


class Extractor:
    """Legacy direct-WARC metadata export implemented with the hardened registry."""

    def metadata_by_ext(
        self,
        fromfile: str,
        file_types: Any = None,
        fields: Any = None,
        output: str = "metadata.jsonl",
    ) -> None:
        del file_types, fields
        source = canonical_path(fromfile)
        with source.open("rb") as handle, Path(output).open("w", encoding="utf-8") as target:
            for record in ArchiveIterator(handle, arc2warc=True):
                if record.rec_type != "response" or record.http_headers is None:
                    continue
                url = record.rec_headers.get_header("WARC-Target-URI") or ""
                filename = url.split("?", 1)[0].rsplit("/", 1)[-1].lower()
                envelope = extract_record(
                    record,
                    archive_id="",
                    warc_id=record.rec_headers.get_header("WARC-Record-ID") or "",
                    url=url,
                    filename=filename,
                    source=str(source),
                    mime=record.http_headers.get_header("Content-Type"),
                )
                import json
                from dataclasses import asdict

                target.write(json.dumps(asdict(envelope), ensure_ascii=False, default=str) + "\n")


__all__ = [
    "Extractor",
    "extract_record",
    "processWarcRecord",
    "read_payload_limited",
]
