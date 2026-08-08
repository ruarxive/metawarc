"""Safe catalog-backed record listing and payload export."""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import re
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from warcio import ArchiveIterator

from ..constants import MIME_EXT_MAP
from ..errors import QueryValidationError, WorkspaceError
from ..progress import ProgressCallback, ProgressEvent, emit_progress
from ..query import MAX_PAGE_SIZE, QueryService, RecordQuery
from ..workspace import Workspace, canonical_path, utc_now

READ_SIZE = 1024 * 1024
SAFE_TOKEN = re.compile(r"[^A-Za-z0-9._-]+")


def get_ext_from_content_type(content_type: str | None) -> str:
    """Return a conservative extension for a content type."""
    if content_type:
        normalized = content_type.split(";", 1)[0].strip().lower()
        mapped = MIME_EXT_MAP.get(normalized)
        if mapped:
            return mapped
        guessed = mimetypes.guess_extension(normalized)
        if guessed:
            return guessed.lstrip(".")
    return "bin"


def safe_record_token(value: str | None) -> str:
    """Convert untrusted record identifiers into a direct-child filename token."""
    token = SAFE_TOKEN.sub("_", (value or "record").strip()).strip(" ._-")
    if not token or token in {".", ".."}:
        token = "record"
    return token[:160]


def safe_output_path(
    output_dir: Path,
    record: dict[str, Any],
    *,
    reserved: set[Path] | None = None,
) -> Path:
    """Create a collision-free output path below output_dir."""
    reserved = reserved if reserved is not None else set()
    extension = safe_record_token(record.get("ext")) or get_ext_from_content_type(
        record.get("content_type")
    )
    if extension == "record":
        extension = get_ext_from_content_type(record.get("content_type"))
    base = safe_record_token(record.get("warc_id"))
    candidate = output_dir / f"{base}.{extension}"
    counter = 1
    while candidate.exists() or candidate in reserved:
        candidate = output_dir / f"{base}-{counter}.{extension}"
        counter += 1
    root = output_dir.resolve()
    resolved_parent = candidate.parent.resolve()
    if resolved_parent != root:
        raise WorkspaceError("Generated export path escaped the output directory")
    reserved.add(candidate)
    return candidate


@contextmanager
def open_record_payload(record: dict[str, Any]) -> Iterator[Any]:
    """Open the indexed record payload and close its WARC source reliably."""
    source = canonical_path(record["source"])
    if not source.exists():
        raise WorkspaceError(f"WARC source not found: {source}")
    with source.open("rb") as handle:
        handle.seek(int(record["offset"]))
        iterator = ArchiveIterator(handle)
        try:
            warc_record = next(iterator)
        except StopIteration as exc:
            raise WorkspaceError(
                f"No WARC record at offset {record['offset']} in {source}"
            ) from exc
        yield warc_record.content_stream()


def iter_payload(
    record: dict[str, Any],
    *,
    chunk_size: int = READ_SIZE,
    max_bytes: int | None = None,
) -> Iterator[bytes]:
    """Yield payload chunks with cancellation-safe source cleanup."""
    read = 0
    with open_record_payload(record) as stream:
        while chunk := stream.read(chunk_size):
            read += len(chunk)
            if max_bytes is not None and read > max_bytes:
                raise WorkspaceError(f"Payload exceeds configured limit of {max_bytes} bytes")
            yield chunk


def _query_from_legacy(
    *,
    archive_ids: str | Sequence[str] | None = None,
    mimes: str | Sequence[str] | None = None,
    exts: str | Sequence[str] | None = None,
    url_pattern: str | None = None,
    query: str | None = None,
    start: int = 0,
    limit: int = 1000,
    sort_by: str = "offset",
) -> RecordQuery:
    return RecordQuery.from_values(
        archive_ids=archive_ids,
        mimes=mimes,
        exts=exts,
        url_pattern=url_pattern,
        unsafe_where=query,
        offset=start,
        limit=limit,
        sort_by=sort_by,
    )


class Dumper:
    """List and export WARC records through the typed query service."""

    def listfiles(
        self,
        warcfileids: str | Sequence[str] | None = None,
        dbfile: str = "warcindex.db",
        mimes: str | Sequence[str] | None = None,
        exts: str | Sequence[str] | None = None,
        query: str | None = None,
        start: int = 0,
        limit: int = 1000,
        output: str | None = None,
        silent: bool = False,
        *,
        data_dir: str | None = None,
        url_pattern: str | None = None,
        output_format: str = "table",
        allow_unsafe: bool = False,
        record_query: RecordQuery | None = None,
    ) -> list[dict[str, Any]]:
        selected = record_query or _query_from_legacy(
            archive_ids=warcfileids,
            mimes=mimes,
            exts=exts,
            url_pattern=url_pattern,
            query=query,
            start=start,
            limit=limit,
        )
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
            total, rows = QueryService(workspace).list_records(selected, allow_unsafe=allow_unsafe)
        if output:
            self._write_rows(Path(output), rows, output_format)
        elif not silent:
            self._print_rows(rows, total)
        return rows

    def _write_rows(self, path: Path, rows: list[dict[str, Any]], output_format: str) -> None:
        output_format = output_format.lower()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise WorkspaceError(f"Output exists; refusing to overwrite: {path}")
        if output_format == "jsonl" or path.suffix.lower() == ".jsonl":
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
            return
        if output_format != "csv" and path.suffix.lower() != ".csv":
            raise QueryValidationError("file output format must be csv or jsonl")
        fields = list(rows[0]) if rows else list(RECORD_LIST_FIELDS)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def _print_rows(self, rows: list[dict[str, Any]], total: int) -> None:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=f"WARC records ({len(rows)} of {total})")
        for field in RECORD_LIST_FIELDS:
            table.add_column(field, overflow="fold")
        for row in rows:
            table.add_row(*(str(row.get(field, "")) for field in RECORD_LIST_FIELDS))
        Console().print(table)

    def dump(
        self,
        warcfiles: str | Sequence[str] | None = None,
        dbfile: str = "warcindex.db",
        mimes: str | Sequence[str] | None = None,
        exts: str | Sequence[str] | None = None,
        query: str | None = None,
        start: int = 0,
        limit: int = 1000,
        output: str = "dump",
        silent: bool = False,
        *,
        data_dir: str | None = None,
        url_pattern: str | None = None,
        max_bytes: int | None = None,
        allow_unsafe: bool = False,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        if limit < 1:
            raise QueryValidationError("limit must be positive")
        output_dir = canonical_path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "manifest.jsonl"
        manifest_counter = 1
        while manifest_path.exists():
            manifest_path = output_dir / f"manifest-{manifest_counter}.jsonl"
            manifest_counter += 1
        selected = _query_from_legacy(
            archive_ids=warcfiles,
            mimes=mimes,
            exts=exts,
            url_pattern=url_pattern,
            query=query,
            start=start,
            limit=min(limit, MAX_PAGE_SIZE),
            sort_by="offset",
        )
        summary: dict[str, Any] = {
            "started_at": utc_now(),
            "completed": 0,
            "skipped": 0,
            "failed": 0,
            "bytes": 0,
            "limit": limit,
            "max_bytes": max_bytes,
            "manifest": str(manifest_path),
        }
        reserved: set[Path] = {manifest_path}
        selected_total = 0
        seen = 0
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
            service = QueryService(workspace)
            matching = service.count_records(selected, allow_unsafe=allow_unsafe)
            selected_total = min(limit, max(0, matching - selected.offset))
            emit_progress(
                progress,
                ProgressEvent(
                    operation="dump",
                    phase="records",
                    task_id="records",
                    label="Export payloads",
                    unit="record",
                    total=selected_total,
                    scope="overall",
                ),
            )
            records = service.iter_records(
                selected,
                allow_unsafe=allow_unsafe,
                export_limit=limit,
            )
            with manifest_path.open("w", encoding="utf-8") as manifest:
                for record in records:
                    seen += 1
                    entry = {
                        "archive_id": record["archive_id"],
                        "warc_id": record["warc_id"],
                        "source": record["source"],
                        "url": record["url"],
                        "content_type": record["content_type"],
                        "status": "pending",
                    }
                    declared = int(record.get("content_length") or 0)
                    task_id = f"{record['archive_id']}:{record['warc_id']}"
                    label = f"Export {safe_record_token(record['warc_id'])}"
                    emit_progress(
                        progress,
                        ProgressEvent(
                            operation="dump",
                            phase="payload",
                            task_id=task_id,
                            label=label,
                            unit="byte",
                            total=declared or None,
                            context={
                                "archive_id": record["archive_id"],
                                "warc_id": record["warc_id"],
                            },
                        ),
                    )
                    if (
                        max_bytes is not None
                        and declared
                        and summary["bytes"] + declared > max_bytes
                    ):
                        entry.update(status="skipped", error="total byte limit")
                        summary["skipped"] += 1
                        manifest.write(json.dumps(entry, ensure_ascii=False) + "\n")
                        emit_progress(
                            progress,
                            ProgressEvent(
                                operation="dump",
                                phase="payload",
                                task_id=task_id,
                                label=label,
                                unit="byte",
                                total=declared or None,
                                status="skipped",
                            ),
                        )
                        break
                    path = safe_output_path(output_dir, record, reserved=reserved)
                    partial = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
                    hasher = hashlib.sha256()
                    written = 0
                    try:
                        with partial.open("xb") as output_handle:
                            for chunk in iter_payload(record):
                                if (
                                    max_bytes is not None
                                    and summary["bytes"] + written + len(chunk) > max_bytes
                                ):
                                    raise WorkspaceError("total byte limit")
                                output_handle.write(chunk)
                                hasher.update(chunk)
                                written += len(chunk)
                                emit_progress(
                                    progress,
                                    ProgressEvent(
                                        operation="dump",
                                        phase="payload",
                                        task_id=task_id,
                                        label=label,
                                        unit="byte",
                                        completed=written,
                                        total=declared or None,
                                    ),
                                )
                        os.replace(partial, path)
                        summary["completed"] += 1
                        summary["bytes"] += written
                        entry.update(
                            status="complete",
                            output_path=str(path),
                            bytes=written,
                            sha256=hasher.hexdigest(),
                        )
                        emit_progress(
                            progress,
                            ProgressEvent(
                                operation="dump",
                                phase="payload",
                                task_id=task_id,
                                label=label,
                                unit="byte",
                                completed=written,
                                total=declared or None,
                                status="complete",
                            ),
                        )
                    except Exception as exc:
                        if partial.exists():
                            partial.unlink()
                        summary["failed"] += 1
                        entry.update(status="failed", error=str(exc), bytes=written)
                        emit_progress(
                            progress,
                            ProgressEvent(
                                operation="dump",
                                phase="payload",
                                task_id=task_id,
                                label=label,
                                unit="byte",
                                completed=written,
                                total=declared or None,
                                status="failed",
                            ),
                        )
                    manifest.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    manifest.flush()
                    emit_progress(
                        progress,
                        ProgressEvent(
                            operation="dump",
                            phase="records",
                            task_id="records",
                            label="Export payloads",
                            unit="record",
                            completed=seen,
                            total=selected_total,
                            scope="overall",
                            counters={
                                "complete": int(summary["completed"]),
                                "skipped": int(summary["skipped"]),
                                "failed": int(summary["failed"]),
                            },
                        ),
                    )
        emit_progress(
            progress,
            ProgressEvent(
                operation="dump",
                phase="records",
                task_id="records",
                label="Export payloads",
                unit="record",
                completed=seen,
                total=selected_total,
                scope="overall",
                status="failed" if summary["failed"] else "complete",
                counters={
                    "complete": int(summary["completed"]),
                    "skipped": int(summary["skipped"]),
                    "failed": int(summary["failed"]),
                },
            ),
        )
        summary["ended_at"] = utc_now()
        return summary

    def get_file(
        self,
        fileid: str,
        dbfile: str = "warcindex.db",
        output: str | None = None,
        silent: bool = False,
        *,
        data_dir: str | None = None,
        archive_id: str | None = None,
        max_bytes: int | None = None,
    ) -> Path | None:
        with Workspace(dbfile, data_dir=data_dir, read_only=True, create=False) as workspace:
            record = QueryService(workspace).get_record(fileid, archive_id=archive_id)
            if not record:
                return None
            if output:
                path = canonical_path(output)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    raise WorkspaceError(f"Output exists; refusing to overwrite: {path}")
            else:
                path = safe_output_path(Path.cwd(), record)
            partial = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
            try:
                with partial.open("xb") as handle:
                    for chunk in iter_payload(record, max_bytes=max_bytes):
                        handle.write(chunk)
                os.replace(partial, path)
            finally:
                if partial.exists():
                    partial.unlink()
        if not silent:
            print(f"Wrote {path}: {record['url']}")
        return path


RECORD_LIST_FIELDS = (
    "archive_id",
    "warc_id",
    "url",
    "content_type",
    "ext",
    "content_length",
    "status_code",
    "offset",
)


__all__ = [
    "Dumper",
    "get_ext_from_content_type",
    "iter_payload",
    "open_record_payload",
    "safe_output_path",
    "safe_record_token",
]
