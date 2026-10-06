"""ContentIndexer: end-to-end extraction pipeline driven by the workspace catalog."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from warcio import ArchiveIterator

from ..constants import MIMES_EXT_TYPE_BY_GROUP
from ..errors import WorkspaceError
from ..progress import ProgressCallback, ProgressEvent, emit_progress
from ..workspace import Workspace, canonical_path
from .envelope import (
    DEFAULT_EXTRACTION_LIMITS,
    LINK_SCHEMA,
    METADATA_SCHEMA,
    TEXT_SCHEMA,
    ExtractionLimits,
    normalize_mime,
)
from .record import extract_record
from .registry import DEFAULT_REGISTRY, ExtractorRegistry, get_text_registry

LOGGER = logging.getLogger(__name__)


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
        del silent
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

    def index_texts(
        self,
        fromfiles: Sequence[str | Path] | None = None,
        tofile: str = "warcindex.db",
        rescan: bool = False,
        silent: bool = True,
        *,
        data_dir: str | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Populate the ``texts`` sidecar with plain-text projections.

        Walks the same catalog candidates as :meth:`index_by_table_type`
        but routes them through the text-projection registry
        (``TextExtractor``, ``PdfTextExtractor``, ``OoxmlTextExtractor``)
        and writes the ``texts`` sidecar using :data:`TEXT_SCHEMA`.
        Archives that already have an active ``texts`` sidecar are
        skipped unless ``rescan=True``.
        """
        del silent
        text_registry = get_text_registry()
        with Workspace(tofile, data_dir=data_dir) as workspace:
            archives = self._selected_archives(workspace, fromfiles)
            request = {"archives": [item["id"] for item in archives], "kind": "texts"}
            with workspace.writer_lock("index-content:texts"):
                run_id = workspace.start_run("index-content", request)
                summary: dict[str, Any] = {
                    "run_id": run_id,
                    "kind": "texts",
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
                        task_id="texts",
                        label="Index texts",
                        unit="archive",
                        total=len(archives),
                        scope="overall",
                        context={"metadata_type": "texts"},
                    ),
                )
                try:
                    for position, archive in enumerate(archives, start=1):
                        archive_id = archive["id"]
                        if workspace.active_sidecars("texts", [archive_id]) and not rescan:
                            summary["skipped"] += 1
                            emit_progress(
                                progress,
                                ProgressEvent(
                                    operation="index-content",
                                    phase="candidates",
                                    task_id=f"texts:{archive_id}",
                                    label=f"texts: {Path(archive['source_path']).name}",
                                    unit="record",
                                    total=0,
                                    status="skipped",
                                    context={"metadata_type": "texts", "archive_id": archive_id},
                                ),
                            )
                            emit_progress(
                                progress,
                                self._content_overall_event_texts(position, len(archives), summary),
                            )
                            continue
                        try:
                            count, errors, warnings, inspected, duration = (
                                self._index_texts_archive(
                                    workspace,
                                    run_id,
                                    archive,
                                    text_registry,
                                    progress=progress,
                                )
                            )
                            summary["processed"] += 1
                            summary["items"] += count
                            summary["errors"] += errors
                            summary["warnings"] += warnings
                            summary["bytes_inspected"] += inspected
                            summary["duration_ms"] += duration
                        except Exception:
                            LOGGER.exception("Text indexing failed for %s", archive["source_path"])
                            summary["failed"] += 1
                        emit_progress(
                            progress,
                            self._content_overall_event_texts(position, len(archives), summary),
                        )
                    status = "complete" if summary["failed"] == 0 else "partial"
                    workspace.finish_run(run_id, status=status, summary=summary)
                    return summary
                except BaseException as exc:
                    workspace.finish_run(run_id, status="failed", summary=summary, error=str(exc))
                    raise

    @staticmethod
    def _content_overall_event_texts(
        completed: int,
        total: int,
        summary: dict[str, Any],
    ) -> ProgressEvent:
        return ProgressEvent(
            operation="index-content",
            phase="archives",
            task_id="texts",
            label="Index texts",
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
            context={"metadata_type": "texts"},
        )

    def _texts_candidate_cursor(self, workspace: Workspace, archive_id: str) -> tuple[Any, int]:
        """Return (cursor, total) for HTML/PDF/OOXML records."""
        paths = workspace.active_sidecar_paths("records", [archive_id])
        if not paths:
            raise WorkspaceError(f"No records sidecar for archive {archive_id}")
        mimes: set[str] = set()
        exts: set[str] = set()
        for group in ("html", "pdfs", "ooxmldocs"):
            config = MIMES_EXT_TYPE_BY_GROUP[group]
            mimes.update(config["mimes"])
            exts.update(config["exts"])
        normalized_mimes = tuple(normalize_mime(m) for m in mimes)
        normalized_exts = tuple(e.lower() for e in exts)
        mime_marks = ",".join("?" for _ in normalized_mimes)
        ext_marks = ",".join("?" for _ in normalized_exts)
        parameters: list[Any] = [paths, *normalized_mimes, *normalized_exts]
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

    def _index_texts_archive(
        self,
        workspace: Workspace,
        run_id: str,
        archive: dict[str, Any],
        text_registry: ExtractorRegistry,
        *,
        progress: ProgressCallback | None,
    ) -> tuple[int, int, int, int, int]:
        cursor, candidate_total = self._texts_candidate_cursor(workspace, archive["id"])
        columns = [item[0] for item in cursor.description]
        stage = workspace.temporary_directory(run_id, archive["id"])
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
            part = stage / f"texts-{batch:08d}.parquet"
            pq.write_table(pa.Table.from_pylist(rows, schema=TEXT_SCHEMA), part, compression="zstd")
            parts.append(part)
            rows = []

        source = canonical_path(archive["source_path"])
        archive_id = archive["id"]
        task_id = f"texts:{archive_id}"
        emit_progress(
            progress,
            ProgressEvent(
                operation="index-content",
                phase="candidates",
                task_id=task_id,
                label=f"texts: {source.name}",
                unit="record",
                total=candidate_total,
                context={"metadata_type": "texts", "archive_id": archive_id},
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
                        continue
                    envelope = extract_record(
                        record,
                        archive_id=item["archive_id"],
                        warc_id=item["warc_id"],
                        url=item["url"],
                        filename=item["filename"],
                        source=item["source"],
                        mime=item["c_type"],
                        registry=text_registry,
                        limits=self.limits,
                    )
                    text_data = envelope.metadata or {}
                    text = text_data.get("text", "")
                    language = text_data.get("language")
                    rows.append(
                        {
                            "archive_id": envelope.archive_id,
                            "warc_id": envelope.warc_id,
                            "source": envelope.source,
                            "url": envelope.url,
                            "language": language,
                            "text": text,
                        }
                    )
                    if envelope.error_code:
                        errors += 1
                    warnings += len(envelope.warnings)
                    inspected += envelope.bytes_inspected
                    duration += envelope.duration_ms
                    if len(rows) >= self.batch_size:
                        flush()
                    emit_progress(
                        progress,
                        ProgressEvent(
                            operation="index-content",
                            phase="candidates",
                            task_id=task_id,
                            label=f"texts: {source.name}",
                            unit="record",
                            completed=candidates,
                            total=candidate_total,
                            counters={"errors": errors, "warnings": warnings},
                            context={"metadata_type": "texts", "archive_id": archive_id},
                        ),
                    )
        flush()
        destination = workspace.new_sidecar_path(archive_id, run_id, "texts")
        if parts:
            count = workspace.combine_parquet_parts(parts, destination, schema=TEXT_SCHEMA)
        else:
            temp = destination.with_suffix(".tmp")
            pq.write_table(pa.Table.from_pylist([], schema=TEXT_SCHEMA), temp, compression="zstd")
            os.replace(temp, destination)
            count = 0
        workspace.publish_sidecar(
            archive_id=archive_id,
            kind="texts",
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
                label=f"texts: {source.name}",
                unit="record",
                completed=candidates,
                total=candidate_total,
                status="complete",
                counters={"items": count, "errors": errors, "warnings": warnings},
                context={"metadata_type": "texts", "archive_id": archive_id},
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
        progress: ProgressCallback | None,
    ) -> int:
        from contextlib import nullcontext

        del silent
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


__all__ = ["ContentIndexer"]
