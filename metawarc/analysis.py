"""Revision-scoped collection summaries, hashes, links, and integrity reports."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .cmds.dump import iter_payload
from .errors import WorkspaceError
from .progress import ProgressCallback, ProgressEvent, emit_progress
from .query import QueryService, RecordQuery
from .workspace import SourceFingerprint, Workspace, canonical_path, utc_now

ANALYSIS_VERSION = "1"

STORED_METADATA_TYPES = ("pdfs", "images", "ooxmldocs", "oledocs", "videos", "audio", "fonts")
NORMALIZED_METADATA_FIELDS = (
    "title",
    "creator",
    "created",
    "modified",
    "application",
    "duration",
    "width",
    "height",
    "font_family",
    "copyright",
)

HASH_SCHEMA = pa.schema(
    [
        ("archive_id", pa.string()),
        ("warc_id", pa.string()),
        ("url", pa.string()),
        ("source", pa.string()),
        ("algorithm", pa.string()),
        ("digest", pa.string()),
        ("bytes", pa.int64()),
        ("catalog_revision", pa.int64()),
        ("analysis_version", pa.string()),
    ]
)

INTEGRITY_SCHEMA = pa.schema(
    [
        ("archive_id", pa.string()),
        ("warc_id", pa.string()),
        ("url", pa.string()),
        ("status", pa.string()),
        ("error", pa.string()),
        ("length_expected", pa.int64()),
        ("length_observed", pa.int64()),
        ("digest", pa.string()),
        ("digest_algorithm", pa.string()),
        ("digest_expected", pa.string()),
        ("digest_observed", pa.string()),
        ("digest_status", pa.string()),
        ("last_safe_offset", pa.int64()),
        ("catalog_revision", pa.int64()),
        ("analysis_version", pa.string()),
    ]
)


@dataclass
class AnalysisReport:
    kind: str
    catalog_revision: int
    analysis_version: str = ANALYSIS_VERSION
    started_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)
    data: Any = None

    def finish(self) -> AnalysisReport:
        self.ended_at = utc_now()
        return self

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["failure_count"] = len(self.failures)
        return result


def write_report(report: AnalysisReport, output: str | Path, output_format: str) -> None:
    """Write equivalent report data in JSON, CSV, or Parquet form."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    output_format = output_format.lower()
    if output_format == "json":
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, default=str, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    rows = report.data if isinstance(report.data, list) else [report.data or {}]
    metadata = {
        "report_kind": report.kind,
        "catalog_revision": report.catalog_revision,
        "analysis_version": report.analysis_version,
        "started_at": report.started_at,
        "ended_at": report.ended_at,
        "filters_json": json.dumps(report.filters, sort_keys=True),
        "limits_json": json.dumps(report.limits, sort_keys=True),
        "failures_json": json.dumps(report.failures, sort_keys=True),
    }
    flattened = []
    for row in rows:
        normalized = {
            key: (
                json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)
                if isinstance(value, (dict, list, tuple))
                else value
            )
            for key, value in row.items()
        }
        flattened.append({**metadata, **normalized})
    if output_format == "csv":
        fields = list(flattened[0]) if flattened else list(metadata)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(flattened)
        return
    if output_format == "parquet":
        pq.write_table(pa.Table.from_pylist(flattened), path, compression="zstd")
        return
    raise ValueError("output format must be json, csv, or parquet")


class AnalysisService:
    """Analyze one versioned workspace without mutating source WARC files."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.query = QueryService(workspace)

    @staticmethod
    def _archive_progress_event(
        *,
        operation: str,
        label: str,
        completed: int,
        total: int,
        processed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        issues: int = 0,
        final: bool = False,
    ) -> ProgressEvent:
        return ProgressEvent(
            operation=operation,
            phase="archives",
            task_id="archives",
            label=label,
            unit="archive",
            completed=completed,
            total=total,
            scope="overall",
            status=(
                "failed" if final and (failed or issues) else "complete" if final else "running"
            ),
            counters={
                "processed": processed,
                "skipped": skipped,
                "failed": failed,
                "issues": issues,
            },
        )

    def summary(
        self,
        dimensions: Sequence[str] = ("mime", "ext", "status", "host", "date", "size_bucket"),
        *,
        query: RecordQuery | None = None,
        top: int | None = None,
    ) -> AnalysisReport:
        report = AnalysisReport(
            kind="collection-summary",
            catalog_revision=self.workspace.revision(),
            filters=asdict(query) if query else {},
            limits={"top": top},
            data={},
        )
        for dimension in dimensions:
            report.data[dimension] = self.query.aggregate(dimension, query=query, top=top)
        return report.finish()

    def stored_metadata(
        self,
        *,
        metadata_types: Sequence[str] | None = None,
        archive_ids: Sequence[str] | None = None,
        top: int = 10,
    ) -> AnalysisReport:
        """Summarize current document/image metadata sidecars without reading payloads."""
        if top < 1:
            raise ValueError("top must be at least 1")
        selected_types = resolve_stored_metadata_types(metadata_types)
        report = AnalysisReport(
            kind="stored-metadata",
            catalog_revision=self.workspace.revision(),
            filters={
                "archive_ids": list(archive_ids or []),
                "metadata_types": list(selected_types),
            },
            limits={"top": top},
            data=[],
        )
        for metadata_type in selected_types:
            paths = self.workspace.active_sidecar_paths(metadata_type, archive_ids)
            if not paths:
                report.data.append(empty_stored_metadata_row(metadata_type))
                continue
            try:
                row, failures = self._analyze_stored_metadata_type(
                    metadata_type,
                    paths,
                    top=top,
                )
                report.data.append(row)
                report.failures.extend(failures)
            except Exception as exc:
                row = empty_stored_metadata_row(metadata_type)
                row["status"] = "failed"
                report.data.append(row)
                report.failures.append(
                    {
                        "metadata_type": metadata_type,
                        "error": f"Unable to analyze stored metadata: {exc}",
                    }
                )
        return report.finish()

    def _analyze_stored_metadata_type(
        self,
        metadata_type: str,
        paths: Sequence[str],
        *,
        top: int,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        cursor = self.workspace.con.execute(
            """
            WITH parsed AS (
                SELECT *,
                       TRY_CAST(metadata_json AS JSON) AS raw_metadata,
                       TRY_CAST(normalized_json AS JSON) AS normalized_metadata,
                       TRY_CAST(warnings_json AS JSON) AS warnings
                FROM read_parquet(?)
            )
            SELECT
                COUNT(*) AS rows,
                COUNT(*) FILTER (
                    WHERE NULLIF(TRIM(error_code), '') IS NULL
                ) AS successes,
                COUNT(*) FILTER (
                    WHERE NULLIF(TRIM(error_code), '') IS NOT NULL
                ) AS errors,
                COUNT(*) FILTER (
                    WHERE json_type(warnings) = 'ARRAY'
                      AND COALESCE(json_array_length(warnings), 0) > 0
                ) AS warning_rows,
                COALESCE(SUM(
                    CASE WHEN json_type(warnings) = 'ARRAY'
                         THEN COALESCE(json_array_length(warnings), 0)
                         ELSE 0 END
                ), 0) AS warning_occurrences,
                COUNT(*) FILTER (
                    WHERE json_type(raw_metadata) = 'OBJECT'
                ) AS raw_metadata_rows,
                COUNT(*) FILTER (
                    WHERE json_type(normalized_metadata) = 'OBJECT'
                ) AS normalized_metadata_rows,
                COUNT(*) FILTER (
                    WHERE (metadata_json IS NOT NULL AND (
                               NOT json_valid(metadata_json)
                               OR json_type(raw_metadata) NOT IN ('OBJECT', 'NULL')
                           ))
                       OR (normalized_json IS NOT NULL AND (
                               NOT json_valid(normalized_json)
                               OR json_type(normalized_metadata) NOT IN ('OBJECT', 'NULL')
                           ))
                       OR (warnings_json IS NOT NULL AND (
                               NOT json_valid(warnings_json)
                               OR json_type(warnings) != 'ARRAY'
                           ))
                ) AS malformed_json_rows,
                COALESCE(SUM(bytes_inspected), 0) AS bytes_inspected,
                COALESCE(SUM(duration_ms), 0) AS duration_ms
            FROM parsed
            """,
            [list(paths)],
        )
        values = cursor.fetchone()
        if values is None:
            raise WorkspaceError(f"Unable to aggregate {metadata_type} metadata")
        aggregate = dict(zip([item[0] for item in cursor.description], values, strict=True))
        row: dict[str, Any] = {
            "metadata_type": metadata_type,
            "status": "complete",
            **{key: int(value or 0) for key, value in aggregate.items()},
            "field_coverage": {},
            "top_values": {},
        }

        for field_name in NORMALIZED_METADATA_FIELDS:
            path = f"$.{field_name}"
            field_count_row = self.workspace.con.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT NULLIF(
                        TRIM(json_extract_string(TRY_CAST(normalized_json AS JSON), ?)),
                        ''
                    ) AS value
                    FROM read_parquet(?)
                    WHERE json_type(TRY_CAST(normalized_json AS JSON)) = 'OBJECT'
                ) WHERE value IS NOT NULL
                """,
                [path, list(paths)],
            ).fetchone()
            if field_count_row is None:
                raise WorkspaceError(
                    f"Unable to aggregate {field_name} coverage for {metadata_type}"
                )
            field_count = field_count_row[0]
            count = int(field_count or 0)
            row["field_coverage"][field_name] = {
                "rows": count,
                "percent": round((count * 100.0 / row["rows"]) if row["rows"] else 0.0, 2),
            }
            top_cursor = self.workspace.con.execute(
                """
                SELECT value, COUNT(*) AS occurrences FROM (
                    SELECT NULLIF(
                        TRIM(json_extract_string(TRY_CAST(normalized_json AS JSON), ?)),
                        ''
                    ) AS value
                    FROM read_parquet(?)
                    WHERE json_type(TRY_CAST(normalized_json AS JSON)) = 'OBJECT'
                ) WHERE value IS NOT NULL
                GROUP BY value
                ORDER BY occurrences DESC, value
                LIMIT ?
                """,
                [path, list(paths), top],
            )
            row["top_values"][field_name] = [
                {"value": value, "count": int(count)} for value, count in top_cursor.fetchall()
            ]

        malformed_cursor = self.workspace.con.execute(
            """
            WITH parsed AS (
                SELECT archive_id, warc_id, metadata_json, normalized_json, warnings_json,
                       TRY_CAST(metadata_json AS JSON) AS raw_metadata,
                       TRY_CAST(normalized_json AS JSON) AS normalized_metadata,
                       TRY_CAST(warnings_json AS JSON) AS warnings
                FROM read_parquet(?)
            )
            SELECT archive_id, warc_id,
                   metadata_json IS NOT NULL AND (
                       NOT json_valid(metadata_json)
                       OR json_type(raw_metadata) NOT IN ('OBJECT', 'NULL')
                   ) AS malformed_metadata,
                   normalized_json IS NOT NULL AND (
                       NOT json_valid(normalized_json)
                       OR json_type(normalized_metadata) NOT IN ('OBJECT', 'NULL')
                   ) AS malformed_normalized,
                   warnings_json IS NOT NULL AND (
                       NOT json_valid(warnings_json)
                       OR json_type(warnings) != 'ARRAY'
                   ) AS malformed_warnings
            FROM parsed
            WHERE malformed_metadata OR malformed_normalized OR malformed_warnings
            ORDER BY archive_id, warc_id
            """,
            [list(paths)],
        )
        failures = []
        for (
            archive_id,
            warc_id,
            malformed_metadata,
            malformed_normalized,
            malformed_warnings,
        ) in malformed_cursor.fetchall():
            fields = [
                field_name
                for field_name, malformed in (
                    ("metadata_json", malformed_metadata),
                    ("normalized_json", malformed_normalized),
                    ("warnings_json", malformed_warnings),
                )
                if malformed
            ]
            failures.append(
                {
                    "metadata_type": metadata_type,
                    "archive_id": archive_id,
                    "warc_id": warc_id,
                    "fields": fields,
                    "error": "Malformed stored metadata JSON",
                }
            )
        if failures:
            row["status"] = "partial"
        return row, failures

    def hash_payloads(
        self,
        *,
        archive_ids: Sequence[str] | None = None,
        force: bool = False,
        resume: bool = True,
        batch_size: int = 1_000,
        progress: ProgressCallback | None = None,
    ) -> AnalysisReport:
        archives = [
            item
            for item in self.workspace.list_archives()
            if not archive_ids or item["id"] in set(archive_ids)
        ]
        request = {
            "archives": [item["id"] for item in archives],
            "force": force,
            "resume": resume,
            "batch_size": batch_size,
        }
        with self.workspace.writer_lock("analysis:hashes"):
            run_id = self.workspace.start_run("analysis:hashes", request)
            report = AnalysisReport(
                kind="payload-hashes",
                catalog_revision=self.workspace.revision(),
                filters={"archive_ids": list(archive_ids or [])},
                limits={"batch_size": batch_size},
                data=[],
            )
            processed = 0
            completed_archives = 0
            skipped_archives = 0
            failed_archives = 0
            emit_progress(
                progress,
                self._archive_progress_event(
                    operation="analysis:hashes",
                    label="Hash payloads",
                    completed=0,
                    total=len(archives),
                ),
            )
            try:
                for archive in archives:
                    if self.workspace.active_sidecars("hashes", [archive["id"]]) and not force:
                        report.data.append(
                            {"archive_id": archive["id"], "status": "skipped", "reason": "current"}
                        )
                        skipped_archives += 1
                        emit_progress(
                            progress,
                            ProgressEvent(
                                operation="analysis:hashes",
                                phase="records",
                                task_id=archive["id"],
                                label=f"Hash {Path(archive['source_path']).name}",
                                unit="record",
                                status="skipped",
                                context={"archive_id": archive["id"]},
                            ),
                        )
                        completed_archives += 1
                        emit_progress(
                            progress,
                            self._archive_progress_event(
                                operation="analysis:hashes",
                                label="Hash payloads",
                                completed=completed_archives,
                                total=len(archives),
                                processed=completed_archives - skipped_archives - failed_archives,
                                skipped=skipped_archives,
                                failed=failed_archives,
                                final=completed_archives == len(archives),
                            ),
                        )
                        continue
                    last_event: ProgressEvent | None = None

                    def track(event: ProgressEvent) -> None:
                        nonlocal last_event
                        last_event = event
                        emit_progress(progress, event)

                    try:
                        count = self._hash_archive(
                            archive,
                            run_id,
                            resume=resume,
                            batch_size=batch_size,
                            progress=track,
                        )
                        processed += count
                        report.data.append(
                            {"archive_id": archive["id"], "status": "complete", "records": count}
                        )
                    except Exception as exc:
                        report.failures.append({"archive_id": archive["id"], "error": str(exc)})
                        failed_archives += 1
                        if last_event is not None:
                            emit_progress(progress, replace(last_event, status="failed"))
                    completed_archives += 1
                    emit_progress(
                        progress,
                        self._archive_progress_event(
                            operation="analysis:hashes",
                            label="Hash payloads",
                            completed=completed_archives,
                            total=len(archives),
                            processed=completed_archives - skipped_archives - failed_archives,
                            skipped=skipped_archives,
                            failed=failed_archives,
                            final=completed_archives == len(archives),
                        ),
                    )
                if not archives:
                    emit_progress(
                        progress,
                        self._archive_progress_event(
                            operation="analysis:hashes",
                            label="Hash payloads",
                            completed=0,
                            total=0,
                            final=True,
                        ),
                    )
                report.finish()
                status = "complete" if not report.failures else "partial"
                self.workspace.finish_run(
                    run_id,
                    status=status,
                    summary={"processed": processed, **report.to_dict()},
                )
                return report
            except BaseException as exc:
                report.finish()
                self.workspace.finish_run(
                    run_id, status="failed", summary=report.to_dict(), error=str(exc)
                )
                raise

    def _hash_archive(
        self,
        archive: dict[str, Any],
        run_id: str,
        *,
        resume: bool,
        batch_size: int,
        progress: ProgressCallback | None,
    ) -> int:
        fingerprint = SourceFingerprint.from_json(archive["fingerprint"])
        current = SourceFingerprint.from_path(
            canonical_path(archive["source_path"]), digest=fingerprint.sha256 is not None
        )
        if current.to_json() != fingerprint.to_json():
            raise WorkspaceError(
                f"Source changed since indexing: {archive['source_path']}; update the index first"
            )
        checkpoint = (
            self.workspace.latest_checkpoint(archive["id"], fingerprint) if resume else None
        )
        parts: list[Path] = []
        next_offset = 0
        batch_number = 0
        count = 0
        adopted_run = None
        if (
            checkpoint
            and checkpoint["state"].get("kind") == "hashes"
            and checkpoint["state"].get("catalog_revision") == self.workspace.revision()
        ):
            candidate_parts = [Path(item) for item in checkpoint["state"].get("parts", [])]
            if all(path.exists() for path in candidate_parts):
                try:
                    for path in candidate_parts:
                        _ = pq.ParquetFile(path).metadata
                    parts = candidate_parts
                    next_offset = int(checkpoint["next_offset"])
                    count = int(checkpoint["records_count"])
                    batch_number = int(checkpoint["state"].get("batch_number", len(parts)))
                    adopted_run = checkpoint["run_id"]
                except Exception:
                    parts = []
                    next_offset = batch_number = count = 0

        record_paths = self.workspace.active_sidecar_paths("records", [archive["id"]])
        if not record_paths:
            raise WorkspaceError(f"No records sidecar for archive {archive['id']}")
        read_connection = duckdb.connect()
        total_row = read_connection.execute(
            'SELECT COUNT(*) FROM read_parquet(?) WHERE "offset" >= ?',
            [record_paths, next_offset],
        ).fetchone()
        total = count + (int(total_row[0]) if total_row else 0)
        cursor = read_connection.execute(
            """
            SELECT archive_id, warc_id, url, source, "offset", "length"
            FROM read_parquet(?) WHERE "offset" >= ? ORDER BY "offset"
            """,
            [record_paths, next_offset],
        )
        columns = [item[0] for item in cursor.description]
        stage = self.workspace.temporary_directory(run_id, archive["id"])
        rows: list[dict[str, Any]] = []
        bytes_inspected = 0
        task_id = archive["id"]
        label = f"Hash {Path(archive['source_path']).name}"
        emit_progress(
            progress,
            ProgressEvent(
                operation="analysis:hashes",
                phase="records",
                task_id=task_id,
                label=label,
                unit="record",
                completed=count,
                total=total,
                context={"archive_id": archive["id"]},
            ),
        )

        def flush(safe_offset: int) -> None:
            nonlocal rows, batch_number, count
            if not rows:
                return
            batch_number += 1
            part = stage / f"hashes-{batch_number:08d}.parquet"
            pq.write_table(pa.Table.from_pylist(rows, schema=HASH_SCHEMA), part, compression="zstd")
            parts.append(part)
            count += len(rows)
            rows = []
            self.workspace.save_checkpoint(
                run_id=run_id,
                archive_id=archive["id"],
                fingerprint=fingerprint,
                next_offset=safe_offset,
                records_count=count,
                headers_count=0,
                state={
                    "kind": "hashes",
                    "catalog_revision": self.workspace.revision(),
                    "batch_number": batch_number,
                    "parts": [str(item) for item in parts],
                },
            )

        safe_offset = next_offset
        try:
            while values := cursor.fetchmany(256):
                for raw in values:
                    record = dict(zip(columns, raw, strict=True))
                    hasher = hashlib.sha256()
                    length = 0
                    for chunk in iter_payload(record):
                        hasher.update(chunk)
                        length += len(chunk)
                        bytes_inspected += len(chunk)
                    rows.append(
                        {
                            "archive_id": record["archive_id"],
                            "warc_id": record["warc_id"],
                            "url": record["url"],
                            "source": record["source"],
                            "algorithm": "sha256",
                            "digest": hasher.hexdigest(),
                            "bytes": length,
                            "catalog_revision": self.workspace.revision(),
                            "analysis_version": ANALYSIS_VERSION,
                        }
                    )
                    safe_offset = int(record["offset"]) + int(record["length"])
                    emit_progress(
                        progress,
                        ProgressEvent(
                            operation="analysis:hashes",
                            phase="records",
                            task_id=task_id,
                            label=label,
                            unit="record",
                            completed=count + len(rows),
                            total=total,
                            counters={"bytes": bytes_inspected},
                            context={"archive_id": archive["id"]},
                        ),
                    )
                    if len(rows) >= batch_size:
                        flush(safe_offset)
        finally:
            read_connection.close()
        flush(safe_offset)
        destination = self.workspace.new_sidecar_path(archive["id"], run_id, "hashes")
        if parts:
            count = self.workspace.combine_parquet_parts(parts, destination, schema=HASH_SCHEMA)
        else:
            temp = destination.with_suffix(".tmp")
            pq.write_table(pa.Table.from_pylist([], schema=HASH_SCHEMA), temp, compression="zstd")
            os.replace(temp, destination)
            count = 0
        self.workspace.publish_sidecar(
            archive_id=archive["id"],
            kind="hashes",
            path=destination,
            num_items=count,
            run_id=run_id,
        )
        self.workspace.clear_checkpoints(archive["id"])
        self.workspace.cleanup_staging(run_id)
        if adopted_run and adopted_run != run_id:
            self.workspace.cleanup_staging(adopted_run)
        emit_progress(
            progress,
            ProgressEvent(
                operation="analysis:hashes",
                phase="records",
                task_id=task_id,
                label=label,
                unit="record",
                completed=count,
                total=total,
                status="complete",
                counters={"bytes": bytes_inspected},
                context={"archive_id": archive["id"]},
            ),
        )
        return count

    def duplicates(self, *, archive_ids: Sequence[str] | None = None) -> AnalysisReport:
        paths = self.workspace.active_sidecar_paths("hashes", archive_ids)
        report = AnalysisReport(
            kind="duplicates",
            catalog_revision=self.workspace.revision(),
            filters={"archive_ids": list(archive_ids or [])},
            data=[],
        )
        if not paths:
            return report.finish()
        groups = self.workspace.con.execute(
            """
            SELECT algorithm, digest, bytes, COUNT(*) AS records
            FROM read_parquet(?) GROUP BY algorithm, digest, bytes
            HAVING COUNT(*) > 1 ORDER BY records DESC, bytes DESC
            """,
            [paths],
        ).fetchall()
        for algorithm, digest, size, records in groups:
            cursor = self.workspace.con.execute(
                """
                SELECT archive_id, warc_id, url, source FROM read_parquet(?)
                WHERE algorithm = ? AND digest = ? AND bytes = ?
                ORDER BY archive_id, warc_id
                """,
                [paths, algorithm, digest, size],
            )
            columns = [item[0] for item in cursor.description]
            members = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
            report.data.append(
                {
                    "algorithm": algorithm,
                    "digest": digest,
                    "bytes": int(size),
                    "records": int(records),
                    "reclaimable_bytes": max(0, int(records) - 1) * int(size),
                    "canonical_candidate": members[0] if members else None,
                    "members": members,
                }
            )
        return report.finish()

    def link_graph(self, *, archive_ids: Sequence[str] | None = None) -> AnalysisReport:
        paths = self.workspace.active_sidecar_paths("links", archive_ids)
        report = AnalysisReport(
            kind="link-graph",
            catalog_revision=self.workspace.revision(),
            filters={"archive_ids": list(archive_ids or [])},
            data={"records": [], "hosts": [], "domains": []},
        )
        if not paths:
            return report.finish()
        cursor = self.workspace.con.execute(
            "SELECT archive_id, warc_id, url, base_url, target FROM read_parquet(?)", [paths]
        )
        columns = [item[0] for item in cursor.description]
        host_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
        domain_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
        record_edges: list[dict[str, Any]] = []
        for raw in cursor.fetchall():
            item = dict(zip(columns, raw, strict=True))
            target = item.get("target")
            if not target:
                continue
            try:
                base_url = urljoin(item["url"], item.get("base_url") or item["url"])
                normalized = normalize_url(base_url, target)
                source_host = (urlsplit(item["url"]).hostname or "").lower()
                target_host = (urlsplit(normalized).hostname or "").lower()
            except ValueError as exc:
                report.failures.append(
                    {
                        "archive_id": item["archive_id"],
                        "warc_id": item["warc_id"],
                        "error": str(exc),
                    }
                )
                continue
            relation = "internal" if source_host == target_host else "external"
            source_domain = registrable_domain(source_host)
            target_domain = registrable_domain(target_host)
            record_edges.append(
                {
                    "archive_id": item["archive_id"],
                    "warc_id": item["warc_id"],
                    "source_url": item["url"],
                    "original_target": target,
                    "normalized_target": normalized,
                    "source_host": source_host,
                    "target_host": target_host,
                    "relation": relation,
                    "normalization_version": ANALYSIS_VERSION,
                }
            )
            key = (source_host, target_host, relation)
            edge = host_edges.setdefault(
                key,
                {
                    "source_host": source_host,
                    "target_host": target_host,
                    "relation": relation,
                    "count": 0,
                    "sample_original": target,
                    "sample_normalized": normalized,
                    "normalization_version": ANALYSIS_VERSION,
                },
            )
            edge["count"] += 1
            domain_key = (source_domain, target_domain, relation)
            domain_edge = domain_edges.setdefault(
                domain_key,
                {
                    "source_domain": source_domain,
                    "target_domain": target_domain,
                    "relation": relation,
                    "count": 0,
                    "normalization_version": ANALYSIS_VERSION,
                },
            )
            domain_edge["count"] += 1
        report.data = {
            "records": sorted(
                record_edges,
                key=lambda value: (
                    value["archive_id"],
                    value["warc_id"],
                    value["normalized_target"],
                ),
            ),
            "hosts": sorted(
                host_edges.values(),
                key=lambda value: (
                    -value["count"],
                    value["source_host"],
                    value["target_host"],
                ),
            ),
            "domains": sorted(
                domain_edges.values(),
                key=lambda value: (
                    -value["count"],
                    value["source_domain"],
                    value["target_domain"],
                ),
            ),
        }
        return report.finish()

    def integrity(
        self,
        *,
        archive_ids: Sequence[str] | None = None,
        deep: bool = False,
        max_records: int = 10_000,
        resume: bool = True,
        force: bool = False,
        batch_size: int = 500,
        progress: ProgressCallback | None = None,
    ) -> AnalysisReport:
        doctor = self.workspace.doctor()
        report = AnalysisReport(
            kind="integrity",
            catalog_revision=self.workspace.revision(),
            filters={"archive_ids": list(archive_ids or []), "deep": deep},
            limits={"max_records": max_records, "batch_size": batch_size},
            data={"workspace": doctor.to_dict(), "records": []},
        )
        if not deep:
            return report.finish()
        if self.workspace.read_only:
            raise WorkspaceError("Deep integrity requires a writable workspace for checkpoints")
        selected = [
            archive
            for archive in self.workspace.list_archives()
            if not archive_ids or archive["id"] in set(archive_ids)
        ]
        request = {
            "archives": [archive["id"] for archive in selected],
            "max_records": max_records,
            "batch_size": batch_size,
            "resume": resume,
            "force": force,
        }
        with self.workspace.writer_lock("analysis:integrity"):
            run_id = self.workspace.start_run("analysis:integrity", request)
            remaining = max_records
            completed_archives = 0
            processed_archives = 0
            skipped_archives = 0
            failed_archives = 0
            emit_progress(
                progress,
                self._archive_progress_event(
                    operation="analysis:integrity",
                    label="Verify payloads",
                    completed=0,
                    total=len(selected),
                ),
            )
            try:
                for archive in selected:
                    if remaining <= 0:
                        break
                    last_event: ProgressEvent | None = None

                    def track(event: ProgressEvent) -> None:
                        nonlocal last_event
                        last_event = event
                        emit_progress(progress, event)

                    try:
                        paths = self.workspace.active_sidecar_paths("integrity", [archive["id"]])
                        if paths and not force:
                            outcomes = self._read_integrity_rows(paths, remaining)
                            skipped_archives += 1
                            emit_progress(
                                progress,
                                ProgressEvent(
                                    operation="analysis:integrity",
                                    phase="records",
                                    task_id=archive["id"],
                                    label=f"Verify {Path(archive['source_path']).name}",
                                    unit="record",
                                    completed=len(outcomes),
                                    total=len(outcomes),
                                    status="skipped",
                                    context={"archive_id": archive["id"]},
                                ),
                            )
                        else:
                            outcomes = self._integrity_archive(
                                archive,
                                run_id,
                                resume=resume,
                                batch_size=batch_size,
                                max_records=remaining,
                                progress=track,
                            )
                            processed_archives += 1
                        report.data["records"].extend(outcomes)
                        report.failures.extend(
                            item for item in outcomes if item["status"] == "failed"
                        )
                        remaining -= len(outcomes)
                    except Exception as exc:
                        report.failures.append(
                            {"archive_id": archive["id"], "status": "failed", "error": str(exc)}
                        )
                        failed_archives += 1
                        if last_event is not None:
                            emit_progress(progress, replace(last_event, status="failed"))
                    completed_archives += 1
                    emit_progress(
                        progress,
                        self._archive_progress_event(
                            operation="analysis:integrity",
                            label="Verify payloads",
                            completed=completed_archives,
                            total=len(selected),
                            processed=processed_archives,
                            skipped=skipped_archives,
                            failed=failed_archives,
                            issues=len(report.failures),
                        ),
                    )
                emit_progress(
                    progress,
                    self._archive_progress_event(
                        operation="analysis:integrity",
                        label="Verify payloads",
                        completed=completed_archives,
                        total=len(selected),
                        processed=processed_archives,
                        skipped=skipped_archives,
                        failed=failed_archives,
                        issues=len(report.failures),
                        final=True,
                    ),
                )
                report.finish()
                self.workspace.finish_run(
                    run_id,
                    status="partial" if report.failures else "complete",
                    summary=report.to_dict(),
                )
                return report
            except BaseException as exc:
                report.finish()
                self.workspace.finish_run(
                    run_id, status="failed", summary=report.to_dict(), error=str(exc)
                )
                raise

    def _read_integrity_rows(self, paths: Sequence[str], limit: int) -> list[dict[str, Any]]:
        connection = duckdb.connect()
        try:
            cursor = connection.execute(
                "SELECT * FROM read_parquet(?) ORDER BY archive_id, last_safe_offset LIMIT ?",
                [list(paths), limit],
            )
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        finally:
            connection.close()

    def _integrity_archive(
        self,
        archive: dict[str, Any],
        run_id: str,
        *,
        resume: bool,
        batch_size: int,
        max_records: int,
        progress: ProgressCallback | None,
    ) -> list[dict[str, Any]]:
        fingerprint = SourceFingerprint.from_json(archive["fingerprint"])
        current = SourceFingerprint.from_path(
            canonical_path(archive["source_path"]), digest=fingerprint.sha256 is not None
        )
        if current.to_json() != fingerprint.to_json():
            raise WorkspaceError(
                f"Source changed since indexing: {archive['source_path']}; update the index first"
            )
        checkpoint = (
            self.workspace.latest_checkpoint(archive["id"], fingerprint) if resume else None
        )
        parts: list[Path] = []
        next_offset = 0
        count = 0
        batch_number = 0
        adopted_run = None
        if (
            checkpoint
            and checkpoint["state"].get("kind") == "integrity"
            and checkpoint["state"].get("catalog_revision") == self.workspace.revision()
        ):
            candidate_parts = [Path(value) for value in checkpoint["state"].get("parts", [])]
            if all(path.exists() for path in candidate_parts):
                try:
                    for path in candidate_parts:
                        _ = pq.ParquetFile(path).metadata
                    parts = candidate_parts
                    next_offset = int(checkpoint["next_offset"])
                    count = int(checkpoint["records_count"])
                    batch_number = int(checkpoint["state"].get("batch_number", len(parts)))
                    adopted_run = checkpoint["run_id"]
                except Exception:
                    parts = []
                    next_offset = count = batch_number = 0

        record_paths = self.workspace.active_sidecar_paths("records", [archive["id"]])
        connection = duckdb.connect()
        remaining_limit = max(0, max_records - count)
        total_row = connection.execute(
            'SELECT COUNT(*) FROM read_parquet(?) WHERE "offset" >= ?',
            [record_paths, next_offset],
        ).fetchone()
        total = count + min(remaining_limit, int(total_row[0]) if total_row else 0)
        cursor = connection.execute(
            """
            SELECT archive_id, warc_id, url, source, "offset", "length",
                   content_length, payload_digest
            FROM read_parquet(?) WHERE "offset" >= ? ORDER BY "offset" LIMIT ?
            """,
            [record_paths, next_offset, remaining_limit],
        )
        columns = [item[0] for item in cursor.description]
        stage = self.workspace.temporary_directory(run_id, archive["id"])
        rows: list[dict[str, Any]] = []
        bytes_inspected = 0
        failed_records = 0
        task_id = archive["id"]
        label = f"Verify {Path(archive['source_path']).name}"
        emit_progress(
            progress,
            ProgressEvent(
                operation="analysis:integrity",
                phase="records",
                task_id=task_id,
                label=label,
                unit="record",
                completed=count,
                total=total,
                context={"archive_id": archive["id"]},
            ),
        )

        def flush(safe_offset: int) -> None:
            nonlocal rows, count, batch_number
            if not rows:
                return
            batch_number += 1
            part = stage / f"integrity-{batch_number:08d}.parquet"
            pq.write_table(
                pa.Table.from_pylist(rows, schema=INTEGRITY_SCHEMA),
                part,
                compression="zstd",
            )
            parts.append(part)
            count += len(rows)
            rows = []
            self.workspace.save_checkpoint(
                run_id=run_id,
                archive_id=archive["id"],
                fingerprint=fingerprint,
                next_offset=safe_offset,
                records_count=count,
                headers_count=0,
                state={
                    "kind": "integrity",
                    "catalog_revision": self.workspace.revision(),
                    "batch_number": batch_number,
                    "parts": [str(path) for path in parts],
                },
            )

        safe_offset = next_offset
        try:
            while values := cursor.fetchmany(128):
                for raw in values:
                    item = dict(zip(columns, raw, strict=True))
                    outcome: dict[str, Any] = {
                        "archive_id": item["archive_id"],
                        "warc_id": item["warc_id"],
                        "url": item["url"],
                        "status": "ok",
                        "error": None,
                        "length_expected": int(item.get("content_length") or 0),
                        "length_observed": 0,
                        "digest": item.get("payload_digest"),
                        "digest_algorithm": None,
                        "digest_expected": None,
                        "digest_observed": None,
                        "digest_status": None,
                        "last_safe_offset": int(item["offset"]) + int(item["length"]),
                        "catalog_revision": self.workspace.revision(),
                        "analysis_version": ANALYSIS_VERSION,
                    }
                    try:
                        if not item.get("warc_id") or not item.get("url"):
                            outcome.update(
                                status="failed",
                                error="required WARC record ID or target URI is missing",
                            )
                        sha1 = hashlib.sha1()
                        sha256 = hashlib.sha256()
                        for chunk in iter_payload(item):
                            outcome["length_observed"] += len(chunk)
                            bytes_inspected += len(chunk)
                            sha1.update(chunk)
                            sha256.update(chunk)
                        if outcome["length_expected"] and (
                            outcome["length_observed"] != outcome["length_expected"]
                        ):
                            outcome.update(
                                status="failed", error="declared payload length mismatch"
                            )
                        if outcome["digest"]:
                            digest = digest_observation(
                                outcome["digest"], sha1.digest(), sha256.digest()
                            )
                            outcome.update(digest)
                            if digest["digest_status"] == "failed":
                                outcome.update(status="failed", error="payload digest mismatch")
                    except Exception as exc:
                        outcome.update(status="failed", error=str(exc))
                    if outcome["status"] == "failed":
                        failed_records += 1
                    safe_offset = int(outcome["last_safe_offset"])
                    rows.append(outcome)
                    emit_progress(
                        progress,
                        ProgressEvent(
                            operation="analysis:integrity",
                            phase="records",
                            task_id=task_id,
                            label=label,
                            unit="record",
                            completed=count + len(rows),
                            total=total,
                            counters={"bytes": bytes_inspected, "issues": failed_records},
                            context={"archive_id": archive["id"]},
                        ),
                    )
                    if len(rows) >= batch_size:
                        flush(safe_offset)
        finally:
            connection.close()
        flush(safe_offset)
        destination = self.workspace.new_sidecar_path(archive["id"], run_id, "integrity")
        if parts:
            self.workspace.combine_parquet_parts(parts, destination, schema=INTEGRITY_SCHEMA)
        else:
            temporary = destination.with_suffix(".tmp")
            pq.write_table(pa.Table.from_pylist([], schema=INTEGRITY_SCHEMA), temporary)
            os.replace(temporary, destination)
        self.workspace.publish_sidecar(
            archive_id=archive["id"],
            kind="integrity",
            path=destination,
            num_items=count,
            run_id=run_id,
        )
        self.workspace.clear_checkpoints(archive["id"])
        self.workspace.cleanup_staging(run_id)
        if adopted_run and adopted_run != run_id:
            self.workspace.cleanup_staging(adopted_run)
        emit_progress(
            progress,
            ProgressEvent(
                operation="analysis:integrity",
                phase="records",
                task_id=task_id,
                label=label,
                unit="record",
                completed=count,
                total=total,
                status="failed" if failed_records else "complete",
                counters={"bytes": bytes_inspected, "issues": failed_records},
                context={"archive_id": archive["id"]},
            ),
        )
        return self._read_integrity_rows([str(destination)], max_records)


def normalize_url(base_url: str, target: str) -> str:
    """Resolve and normalize a link while removing its fragment."""
    absolute, _fragment = urldefrag(urljoin(base_url, target))
    parsed = urlsplit(absolute)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Link is not an absolute HTTP target after resolution: {target!r}")
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError(f"Link has no host: {target!r}")
    host = host.encode("idna").decode("ascii")
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


def resolve_stored_metadata_types(metadata_types: Sequence[str] | None = None) -> tuple[str, ...]:
    """Validate stored metadata type selection and expand the exclusive ``all`` value."""
    requested = tuple(metadata_types or ("all",))
    invalid = sorted(set(requested) - {*STORED_METADATA_TYPES, "all"})
    if invalid:
        raise ValueError(
            "metadata type must be one of "
            + ", ".join((*STORED_METADATA_TYPES, "all"))
            + f"; received {', '.join(invalid)}"
        )
    if "all" in requested:
        if any(value != "all" for value in requested):
            raise ValueError("metadata type 'all' cannot be combined with explicit types")
        return STORED_METADATA_TYPES
    return tuple(dict.fromkeys(requested))


def empty_stored_metadata_row(metadata_type: str) -> dict[str, Any]:
    """Return the stable zero-value shape for an unindexed metadata type."""
    return {
        "metadata_type": metadata_type,
        "status": "not-indexed",
        "rows": 0,
        "successes": 0,
        "errors": 0,
        "warning_rows": 0,
        "warning_occurrences": 0,
        "raw_metadata_rows": 0,
        "normalized_metadata_rows": 0,
        "malformed_json_rows": 0,
        "bytes_inspected": 0,
        "duration_ms": 0,
        "field_coverage": {
            field_name: {"rows": 0, "percent": 0.0} for field_name in NORMALIZED_METADATA_FIELDS
        },
        "top_values": {field_name: [] for field_name in NORMALIZED_METADATA_FIELDS},
    }


def registrable_domain(host: str) -> str:
    """Return a deterministic best-effort registrable-domain grouping."""
    labels = [item for item in host.rstrip(".").lower().split(".") if item]
    if len(labels) <= 2:
        return ".".join(labels)
    common_second_level = {"co.uk", "org.uk", "com.au", "com.br", "co.jp", "co.nz"}
    suffix = ".".join(labels[-2:])
    width = 3 if suffix in common_second_level else 2
    return ".".join(labels[-width:])


def verify_warc_digest(payload: bytes, declared: str) -> bool | None:
    """Verify supported WARC payload digest encodings."""
    algorithm, separator, raw_value = declared.partition(":")
    if not separator:
        return None
    normalized_algorithm = algorithm.lower().replace("-", "")
    if normalized_algorithm not in {"sha1", "sha256"}:
        return None
    digest = hashlib.new(normalized_algorithm, payload).digest()
    value = raw_value.strip()
    candidates = {
        digest.hex().lower(),
        base64.b32encode(digest).decode("ascii").rstrip("=").lower(),
    }
    return value.rstrip("=").lower() in candidates


def verify_computed_digest(declared: str, sha1_digest: bytes, sha256_digest: bytes) -> bool | None:
    """Verify a WARC digest from streaming-computed digest bytes."""
    status = digest_observation(declared, sha1_digest, sha256_digest)["digest_status"]
    return None if status == "unsupported" else status == "ok"


def digest_observation(
    declared: str, sha1_digest: bytes, sha256_digest: bytes
) -> dict[str, str | None]:
    """Describe expected and observed streaming digest values."""
    algorithm, separator, raw_value = declared.partition(":")
    if not separator:
        return {
            "digest_algorithm": None,
            "digest_expected": raw_value or declared,
            "digest_observed": None,
            "digest_status": "unsupported",
        }
    normalized_algorithm = algorithm.lower().replace("-", "")
    digest = {"sha1": sha1_digest, "sha256": sha256_digest}.get(normalized_algorithm)
    if digest is None:
        return {
            "digest_algorithm": normalized_algorithm,
            "digest_expected": raw_value.strip(),
            "digest_observed": None,
            "digest_status": "unsupported",
        }
    expected = raw_value.strip().rstrip("=").lower()
    if expected and all(character in "0123456789abcdef" for character in expected):
        observed = digest.hex().lower()
    else:
        observed = base64.b32encode(digest).decode("ascii").rstrip("=").lower()
    return {
        "digest_algorithm": normalized_algorithm,
        "digest_expected": expected,
        "digest_observed": observed,
        "digest_status": "ok" if observed == expected else "failed",
    }


__all__ = [
    "ANALYSIS_VERSION",
    "AnalysisReport",
    "AnalysisService",
    "HASH_SCHEMA",
    "INTEGRITY_SCHEMA",
    "NORMALIZED_METADATA_FIELDS",
    "STORED_METADATA_TYPES",
    "digest_observation",
    "empty_stored_metadata_row",
    "normalize_url",
    "registrable_domain",
    "resolve_stored_metadata_types",
    "verify_computed_digest",
    "verify_warc_digest",
    "write_report",
]
