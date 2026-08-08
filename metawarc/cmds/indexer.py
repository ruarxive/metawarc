"""Streaming WARC indexing and catalog-backed statistics."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pyarrow as pa
import pyarrow.parquet as pq
from warcio import ArchiveIterator

from ..progress import ProgressCallback, ProgressEvent, emit_progress
from ..workspace import SourceFingerprint, Workspace, canonical_path, utc_now

LOGGER = logging.getLogger(__name__)
DEFAULT_BATCH_SIZE = 10_000

try:
    READER_VERSION = version("warcio")
except PackageNotFoundError:  # pragma: no cover - editable source edge case
    READER_VERSION = "unknown"

RECORD_SCHEMA = pa.schema(
    [
        ("archive_id", pa.string()),
        ("warc_id", pa.string()),
        ("url", pa.string()),
        ("host", pa.string()),
        ("content_type", pa.string()),
        ("c_type", pa.string()),
        ("c_type_charset", pa.string()),
        ("offset", pa.int64()),
        ("length", pa.int64()),
        ("rec_date", pa.timestamp("us", tz="UTC")),
        ("content_length", pa.int64()),
        ("status_code", pa.int32()),
        ("source", pa.string()),
        ("filename", pa.string()),
        ("ext", pa.string()),
        ("payload_digest", pa.string()),
        ("block_digest", pa.string()),
    ]
)

HEADER_SCHEMA = pa.schema(
    [
        ("archive_id", pa.string()),
        ("warc_id", pa.string()),
        ("key", pa.string()),
        ("value", pa.string()),
        ("source", pa.string()),
    ]
)


@dataclass
class IndexSummary:
    """Machine-readable result of an indexing run."""

    run_id: str
    mode: str
    sources: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    records: int = 0
    headers: int = 0
    bytes: int = 0
    revision: int = 0
    started_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    duration_ms: int = 0
    analysis: dict[str, Any] | None = None
    outcomes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def _content_type(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    pieces = [item.strip() for item in value.split(";")]
    base = pieces[0].lower() or None
    charset = None
    for parameter in pieces[1:]:
        key, separator, item_value = parameter.partition("=")
        if separator and key.strip().lower() == "charset":
            charset = item_value.strip().strip('"').lower() or None
            break
    return base, charset


def _normalize_record_id(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().strip("<>")


def _write_part(path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path, compression="zstd")
    _ = pq.ParquetFile(path).metadata


class Indexer:
    """Index WARC record/header metadata into a versioned workspace."""

    def __init__(self, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size

    def index_records(
        self,
        fromfiles: Sequence[str | Path],
        tofile: str = "warcindex.db",
        tables: Sequence[str] = ("records", "headers"),
        *,
        data_dir: str | None = None,
        mode: str = "update",
        rescan: bool = False,
        force: bool = False,
        resume: bool = False,
        silent: bool = False,
        digest_fingerprint: bool = False,
        progress: ProgressCallback | None = None,
    ) -> IndexSummary:
        """Index sources with explicit update semantics and bounded batches."""
        if rescan:
            mode = "rescan"
        if force:
            mode = "force"
        if mode not in {"add", "update", "rescan", "force"}:
            raise ValueError("mode must be add, update, rescan, or force")
        selected = set(tables)
        unsupported = selected - {"records", "headers"}
        if unsupported:
            raise ValueError(f"Unsupported index tables: {', '.join(sorted(unsupported))}")

        sources = [canonical_path(item) for item in fromfiles]
        started = time.monotonic()
        with Workspace(tofile, data_dir=data_dir) as workspace:
            request = {
                "sources": [str(item) for item in sources],
                "tables": sorted(selected),
                "mode": mode,
                "resume": resume,
                "batch_size": self.batch_size,
            }
            with workspace.writer_lock("index"):
                run_id = workspace.start_run("index", request)
                summary = IndexSummary(run_id=run_id, mode=mode, sources=len(sources))
                emit_progress(
                    progress,
                    ProgressEvent(
                        operation="index",
                        phase="sources",
                        task_id="sources",
                        label="Index archives",
                        unit="archive",
                        total=len(sources),
                        scope="overall",
                    ),
                )
                try:
                    for position, source in enumerate(sources, start=1):
                        outcome = self._process_source(
                            workspace,
                            run_id,
                            source,
                            selected,
                            mode=mode,
                            resume=resume,
                            silent=silent,
                            digest_fingerprint=digest_fingerprint,
                            progress=progress,
                        )
                        summary.outcomes.append(outcome)
                        result = outcome["status"]
                        if result == "complete":
                            summary.processed += 1
                            summary.records += int(outcome.get("records", 0))
                            summary.headers += int(outcome.get("headers", 0))
                            summary.bytes += int(outcome.get("bytes", 0))
                        elif result == "skipped":
                            summary.skipped += 1
                        else:
                            summary.failed += 1
                        emit_progress(
                            progress,
                            ProgressEvent(
                                operation="index",
                                phase="sources",
                                task_id="sources",
                                label="Index archives",
                                unit="archive",
                                completed=position,
                                total=len(sources),
                                scope="overall",
                                status=(
                                    "failed"
                                    if position == len(sources) and summary.failed
                                    else "complete"
                                    if position == len(sources)
                                    else "running"
                                ),
                                counters={
                                    "processed": summary.processed,
                                    "skipped": summary.skipped,
                                    "failed": summary.failed,
                                },
                            ),
                        )
                    summary.revision = workspace.revision()
                    summary.ended_at = utc_now()
                    summary.duration_ms = int((time.monotonic() - started) * 1000)
                    status = "complete" if summary.failed == 0 else "partial"
                    workspace.finish_run(run_id, status=status, summary=summary.to_dict())
                    return summary
                except BaseException as exc:
                    emit_progress(
                        progress,
                        ProgressEvent(
                            operation="index",
                            phase="sources",
                            task_id="sources",
                            label="Index archives",
                            unit="archive",
                            completed=len(summary.outcomes),
                            total=len(sources),
                            scope="overall",
                            status="failed",
                            counters={
                                "processed": summary.processed,
                                "skipped": summary.skipped,
                                "failed": summary.failed,
                            },
                        ),
                    )
                    summary.revision = workspace.revision()
                    summary.ended_at = utc_now()
                    summary.duration_ms = int((time.monotonic() - started) * 1000)
                    workspace.finish_run(
                        run_id,
                        status="failed",
                        summary=summary.to_dict(),
                        error=str(exc),
                    )
                    raise

    def _process_source(
        self,
        workspace: Workspace,
        run_id: str,
        source: Path,
        tables: set[str],
        *,
        mode: str,
        resume: bool,
        silent: bool,
        digest_fingerprint: bool,
        progress: ProgressCallback | None,
    ) -> dict[str, Any]:
        task_id = str(source)
        emit_progress(
            progress,
            ProgressEvent(
                operation="index",
                phase="records",
                task_id=task_id,
                label=f"Index {source.name}",
                unit="record",
            ),
        )
        if not source.exists() or not source.is_file():
            emit_progress(
                progress,
                ProgressEvent(
                    operation="index",
                    phase="records",
                    task_id=task_id,
                    label=f"Index {source.name}",
                    unit="record",
                    status="failed",
                ),
            )
            return {"source": str(source), "status": "failed", "error": "source not found"}
        if not (source.name.lower().endswith(".warc") or source.name.lower().endswith(".warc.gz")):
            emit_progress(
                progress,
                ProgressEvent(
                    operation="index",
                    phase="records",
                    task_id=task_id,
                    label=f"Index {source.name}",
                    unit="record",
                    status="failed",
                ),
            )
            return {"source": str(source), "status": "failed", "error": "unsupported extension"}

        fingerprint = SourceFingerprint.from_path(source, digest=digest_fingerprint)
        existing = workspace.find_archive_by_source(source)
        archive = workspace.ensure_archive(source, fingerprint)
        archive_id = archive["id"]
        if existing:
            stored = SourceFingerprint.from_json(existing["fingerprint"])
            unchanged = stored.to_json() == fingerprint.to_json()
            if mode == "add":
                emit_progress(
                    progress,
                    ProgressEvent(
                        operation="index",
                        phase="records",
                        task_id=task_id,
                        label=f"Index {source.name}",
                        unit="record",
                        status="skipped",
                    ),
                )
                return {
                    "source": str(source),
                    "archive_id": archive_id,
                    "status": "skipped",
                    "reason": "already registered",
                }
            if mode == "update" and unchanged and existing["status"] == "complete":
                emit_progress(
                    progress,
                    ProgressEvent(
                        operation="index",
                        phase="records",
                        task_id=task_id,
                        label=f"Index {source.name}",
                        unit="record",
                        status="skipped",
                    ),
                )
                return {
                    "source": str(source),
                    "archive_id": archive_id,
                    "status": "skipped",
                    "reason": "unchanged",
                }

        try:
            result = self._scan_source(
                workspace,
                run_id,
                archive_id,
                source,
                fingerprint,
                tables,
                resume=resume,
                silent=silent,
                progress=progress,
            )
            result.update(
                {
                    "source": str(source),
                    "archive_id": archive_id,
                    "status": "complete",
                    "bytes": fingerprint.size,
                }
            )
            emit_progress(
                progress,
                ProgressEvent(
                    operation="index",
                    phase="records",
                    task_id=task_id,
                    label=f"Index {source.name}",
                    unit="record",
                    completed=int(result.get("records", 0)),
                    status="complete",
                    counters={"headers": int(result.get("headers", 0))},
                ),
            )
            return result
        except KeyboardInterrupt:
            workspace.mark_archive_error(archive_id, "interrupted", partial=True)
            raise
        except Exception as exc:
            LOGGER.exception("Failed to index %s", source)
            workspace.mark_archive_error(archive_id, str(exc), partial=True)
            return {
                "source": str(source),
                "archive_id": archive_id,
                "status": "failed",
                "error": str(exc),
            }

    def _resume_state(
        self,
        workspace: Workspace,
        archive_id: str,
        fingerprint: SourceFingerprint,
        enabled: bool,
    ) -> tuple[int, int, int, int, list[Path], list[Path], str | None]:
        if not enabled:
            return 0, 0, 0, 0, [], [], None
        checkpoint = workspace.latest_checkpoint(archive_id, fingerprint)
        if not checkpoint:
            return 0, 0, 0, 0, [], [], None
        state = checkpoint["state"]
        if state.get("reader") != "warcio" or state.get("reader_version") != READER_VERSION:
            return 0, 0, 0, 0, [], [], None
        record_parts = [Path(item) for item in state.get("record_parts", [])]
        header_parts = [Path(item) for item in state.get("header_parts", [])]
        if not all(path.exists() for path in record_parts + header_parts):
            return 0, 0, 0, 0, [], [], None
        try:
            for path in record_parts + header_parts:
                _ = pq.ParquetFile(path).metadata
        except Exception:
            return 0, 0, 0, 0, [], [], None
        return (
            int(checkpoint["next_offset"]),
            int(checkpoint["records_count"]),
            int(checkpoint["headers_count"]),
            int(state.get("batch_number", len(record_parts))),
            record_parts,
            header_parts,
            str(checkpoint["run_id"]),
        )

    def _scan_source(
        self,
        workspace: Workspace,
        run_id: str,
        archive_id: str,
        source: Path,
        fingerprint: SourceFingerprint,
        tables: set[str],
        *,
        resume: bool,
        silent: bool,
        progress: ProgressCallback | None,
    ) -> dict[str, Any]:
        (
            next_offset,
            records_count,
            headers_count,
            batch_number,
            record_parts,
            header_parts,
            adopted_run,
        ) = self._resume_state(workspace, archive_id, fingerprint, resume)
        stage = workspace.temporary_directory(run_id, archive_id)
        record_rows: list[dict[str, Any]] = []
        header_rows: list[dict[str, Any]] = []

        def flush(offset: int) -> None:
            nonlocal batch_number, records_count, headers_count, record_rows, header_rows
            if not record_rows and not header_rows:
                return
            batch_number += 1
            if record_rows and "records" in tables:
                part = stage / f"records-{batch_number:08d}.parquet"
                _write_part(part, record_rows, RECORD_SCHEMA)
                record_parts.append(part)
                records_count += len(record_rows)
            if header_rows and "headers" in tables:
                part = stage / f"headers-{batch_number:08d}.parquet"
                _write_part(part, header_rows, HEADER_SCHEMA)
                header_parts.append(part)
                headers_count += len(header_rows)
            record_rows = []
            header_rows = []
            workspace.save_checkpoint(
                run_id=run_id,
                archive_id=archive_id,
                fingerprint=fingerprint,
                next_offset=offset,
                records_count=records_count,
                headers_count=headers_count,
                state={
                    "batch_number": batch_number,
                    "record_parts": [str(item) for item in record_parts],
                    "header_parts": [str(item) for item in header_parts],
                    "reader": "warcio",
                    "reader_version": READER_VERSION,
                },
            )

        with source.open("rb") as stream:
            if next_offset:
                stream.seek(next_offset)
            iterator = ArchiveIterator(stream)
            safe_next_offset = next_offset
            for record in iterator:
                offset = int(iterator.get_record_offset())
                length = int(iterator.get_record_length())
                # warcio excludes the four-byte record separator from plain
                # WARC lengths. Gzip lengths already span the complete member.
                separator = 0 if source.name.lower().endswith(".gz") else 4
                safe_next_offset = offset + length + separator
                if record.rec_type != "response" or record.http_headers is None:
                    continue
                row, headers = self._record_rows(archive_id, source, record, offset, length)
                if "records" in tables:
                    record_rows.append(row)
                if "headers" in tables:
                    header_rows.extend(headers)
                emit_progress(
                    progress,
                    ProgressEvent(
                        operation="index",
                        phase="records",
                        task_id=str(source),
                        label=f"Index {source.name}",
                        unit="record",
                        completed=records_count + len(record_rows),
                        counters={"headers": headers_count + len(header_rows)},
                        context={"source": str(source), "archive_id": archive_id},
                    ),
                )
                if len(record_rows) >= self.batch_size or len(header_rows) >= self.batch_size * 8:
                    flush(safe_next_offset)
            flush(safe_next_offset)

        published: list[tuple[str, Path, int]] = []
        if record_parts and "records" in tables:
            path = workspace.new_sidecar_path(archive_id, run_id, "records")
            records_count = workspace.combine_parquet_parts(
                record_parts, path, schema=RECORD_SCHEMA
            )
            published.append(("records", path, records_count))
        if header_parts and "headers" in tables:
            path = workspace.new_sidecar_path(archive_id, run_id, "headers")
            headers_count = workspace.combine_parquet_parts(
                header_parts, path, schema=HEADER_SCHEMA
            )
            published.append(("headers", path, headers_count))

        workspace.publish_archive(
            archive_id=archive_id,
            fingerprint=fingerprint,
            run_id=run_id,
            sidecars=published,
            num_records=records_count,
        )
        workspace.clear_checkpoints(archive_id)
        workspace.cleanup_staging(run_id)
        if adopted_run and adopted_run != run_id:
            workspace.cleanup_staging(adopted_run)
        return {"records": records_count, "headers": headers_count}

    def _record_rows(
        self,
        archive_id: str,
        source: Path,
        record: Any,
        offset: int,
        length: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rec_headers = record.rec_headers
        http_headers = record.http_headers
        warc_id = _normalize_record_id(rec_headers.get_header("WARC-Record-ID"))
        url = rec_headers.get_header("WARC-Target-URI") or ""
        raw_content_type = http_headers.get_header("Content-Type")
        normalized_type, charset = _content_type(raw_content_type)
        parsed_url = urlsplit(url)
        filename = Path(parsed_url.path).name.lower()
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        status_line = getattr(http_headers, "statusline", "") or ""
        status_code = _safe_int(status_line.split(" ", 1)[0], 0)
        content_length = _safe_int(
            http_headers.get_header("Content-Length"),
            _safe_int(rec_headers.get_header("Content-Length"), 0),
        )
        row = {
            "archive_id": archive_id,
            "warc_id": warc_id,
            "url": url,
            "host": (parsed_url.hostname or "").lower(),
            "content_type": raw_content_type,
            "c_type": normalized_type,
            "c_type_charset": charset,
            "offset": offset,
            "length": length,
            "rec_date": _parse_date(rec_headers.get_header("WARC-Date")),
            "content_length": content_length,
            "status_code": status_code,
            "source": str(source),
            "filename": filename,
            "ext": extension,
            "payload_digest": rec_headers.get_header("WARC-Payload-Digest"),
            "block_digest": rec_headers.get_header("WARC-Block-Digest"),
        }
        headers = [
            {
                "archive_id": archive_id,
                "warc_id": warc_id,
                "key": str(key),
                "value": str(value),
                "source": str(source),
            }
            for key, value in http_headers.headers
        ]
        return row, headers

    def calc_stats(
        self,
        dbfile: str = "warcindex.db",
        mode: str = "mimes",
        *,
        data_dir: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return and print MIME or extension statistics through the query service."""
        from rich.console import Console
        from rich.table import Table

        from ..query import QueryService

        dimension = "c_type" if mode == "mimes" else "ext" if mode == "exts" else None
        if dimension is None:
            raise ValueError("mode must be mimes or exts")
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
            rows = QueryService(workspace).aggregate(dimension)
        table = Table(title=f"Records by {'MIME type' if mode == 'mimes' else 'extension'}")
        table.add_column(dimension)
        table.add_column("bytes", justify="right")
        table.add_column("share", justify="right")
        table.add_column("count", justify="right")
        total = sum(int(item["bytes"] or 0) for item in rows)
        for item in rows:
            size = int(item["bytes"] or 0)
            share = f"{size * 100.0 / total:.2f}%" if total else "0.00%"
            item["share"] = share
            table.add_row(str(item[dimension] or ""), str(size), share, str(item["count"]))
        Console().print(table)
        return rows

    def index_by_table_type(self, *args: Any, **kwargs: Any) -> Any:
        """Compatibility adapter for the new extraction index service."""
        from .extractor import ContentIndexer

        return ContentIndexer(batch_size=self.batch_size).index_by_table_type(*args, **kwargs)

    def dump_metadata(self, *args: Any, **kwargs: Any) -> Any:
        """Compatibility adapter for metadata export."""
        from .extractor import ContentIndexer

        return ContentIndexer(batch_size=self.batch_size).dump_metadata(*args, **kwargs)


def summary_json(summary: IndexSummary) -> str:
    return json.dumps(summary.to_dict(), ensure_ascii=False, sort_keys=True)


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "HEADER_SCHEMA",
    "Indexer",
    "IndexSummary",
    "RECORD_SCHEMA",
    "summary_json",
]
