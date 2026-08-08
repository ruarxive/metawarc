"""Versioned DuckDB catalog and filesystem workspace management."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import tempfile
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from .errors import SchemaCompatibilityError, WorkspaceError, WorkspaceLockedError

SCHEMA_VERSION = 2
SIDECAR_SCHEMA_VERSION = 1


def utc_now() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def canonical_path(path: str | os.PathLike[str], *, base: Path | None = None) -> Path:
    """Resolve a path without requiring it to exist."""
    value = Path(path).expanduser()
    if not value.is_absolute() and base is not None:
        value = base / value
    return value.resolve(strict=False)


@dataclass(frozen=True)
class SourceFingerprint:
    """Cheap source-change fingerprint with optional full digest."""

    size: int
    mtime_ns: int
    sha256: str | None = None

    @classmethod
    def from_path(cls, path: Path, *, digest: bool = False) -> SourceFingerprint:
        stat = path.stat()
        value = None
        if digest:
            hasher = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
            value = hasher.hexdigest()
        return cls(size=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=value)

    @classmethod
    def from_json(cls, raw: str) -> SourceFingerprint:
        return cls(**json.loads(raw))

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass
class DoctorIssue:
    """A workspace diagnostic finding."""

    code: str
    severity: str
    message: str
    archive_id: str | None = None
    path: str | None = None
    repair: str | None = None


@dataclass
class DoctorReport:
    """Results from workspace validation or repair."""

    database: str
    schema_version: int | None
    issues: list[DoctorIssue] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(item.severity == "error" for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "schema_version": self.schema_version,
            "ok": self.ok,
            "issues": [asdict(item) for item in self.issues],
            "actions": self.actions,
        }


class Workspace:
    """Own a DuckDB catalog and all sidecar/checkpoint paths for one index."""

    def __init__(
        self,
        db_path: str | os.PathLike[str] = "warcindex.db",
        *,
        data_dir: str | os.PathLike[str] | None = None,
        read_only: bool = False,
        create: bool = True,
        migrate: bool = True,
    ) -> None:
        self.db_path = canonical_path(db_path)
        self.read_only = read_only
        if read_only and not self.db_path.exists():
            raise WorkspaceError(f"Index database not found: {self.db_path}")
        if not create and not self.db_path.exists():
            raise WorkspaceError(f"Index database not found: {self.db_path}")

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._requested_data_root = (
            canonical_path(data_dir)
            if data_dir is not None
            else self.db_path.parent / f"{self.db_path.stem}.data"
        )
        try:
            self.con = duckdb.connect(str(self.db_path), read_only=read_only)
        except duckdb.ConnectionException as exc:
            # DuckDB rejects mixed connection configurations for one file in
            # a process. Internal readers remain logically read-only when a
            # writer connection is already open in this process.
            if not read_only or "different configuration" not in str(exc):
                raise
            self.con = duckdb.connect(str(self.db_path), read_only=False)

        if read_only:
            self._load_existing_metadata()
        else:
            self._initialize(migrate=migrate)
            self.data_root.mkdir(parents=True, exist_ok=True)
            self.sidecar_root.mkdir(parents=True, exist_ok=True)
            self.staging_root.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> Workspace:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def close(self) -> None:
        self.con.close()

    @property
    def sidecar_root(self) -> Path:
        return self.data_root / "sidecars"

    @property
    def staging_root(self) -> Path:
        return self.data_root / "staging"

    @property
    def quarantine_root(self) -> Path:
        return self.data_root / "quarantine"

    @property
    def lock_path(self) -> Path:
        return self.data_root / ".writer.lock"

    def _table_names(self) -> set[str]:
        return {row[0] for row in self.con.execute("SHOW TABLES").fetchall()}

    def _initialize(self, *, migrate: bool) -> None:
        tables = self._table_names()
        if not tables:
            self.data_root = self._requested_data_root
            self._create_schema()
            return

        if "meta" in tables:
            self._load_existing_metadata()
            return

        if {"files", "tables"}.issubset(tables):
            if not migrate:
                raise SchemaCompatibilityError(
                    "Legacy index detected. Reopen with migration enabled or rebuild the index."
                )
            self.data_root = self._requested_data_root
            self._migrate_legacy()
            return

        raise SchemaCompatibilityError(
            "Unrecognized DuckDB schema. The database was not modified; use a new "
            "workspace or run the documented rebuild procedure."
        )

    def _load_existing_metadata(self) -> None:
        tables = self._table_names()
        if "meta" not in tables:
            raise SchemaCompatibilityError(
                "Index has no schema metadata. Open it with migration enabled before reading."
            )
        rows = dict(self.con.execute("SELECT key, value FROM meta").fetchall())
        try:
            version = int(rows["schema_version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaCompatibilityError("Index schema version is missing or invalid") from exc
        if version != SCHEMA_VERSION:
            raise SchemaCompatibilityError(
                f"Unsupported index schema {version}; this release supports {SCHEMA_VERSION}. "
                "Migrate with a compatible release or rebuild."
            )
        stored = rows.get("data_root")
        self.data_root = canonical_path(stored) if stored else self._requested_data_root
        if (
            self._requested_data_root != self.data_root
            and self._requested_data_root != self.db_path.parent / f"{self.db_path.stem}.data"
        ):
            raise WorkspaceError(
                f"Workspace data root is {self.data_root}, not {self._requested_data_root}"
            )

    def _create_schema(self) -> None:
        self.con.execute("BEGIN TRANSACTION")
        try:
            self.con.execute("CREATE TABLE meta (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
            self.con.execute(
                """
                CREATE TABLE catalog_state (
                    singleton INTEGER PRIMARY KEY,
                    revision BIGINT NOT NULL,
                    updated_at VARCHAR NOT NULL
                )
                """
            )
            self.con.execute(
                """
                CREATE TABLE archives (
                    id VARCHAR PRIMARY KEY,
                    source_uri VARCHAR UNIQUE NOT NULL,
                    source_path VARCHAR NOT NULL,
                    filename VARCHAR NOT NULL,
                    size BIGINT NOT NULL,
                    mtime_ns BIGINT NOT NULL,
                    fingerprint VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    num_records BIGINT NOT NULL DEFAULT 0,
                    created_at VARCHAR NOT NULL,
                    updated_at VARCHAR NOT NULL,
                    last_error VARCHAR
                )
                """
            )
            self.con.execute(
                """
                CREATE TABLE sidecars (
                    id VARCHAR PRIMARY KEY,
                    archive_id VARCHAR NOT NULL,
                    kind VARCHAR NOT NULL,
                    path VARCHAR UNIQUE NOT NULL,
                    status VARCHAR NOT NULL,
                    num_items BIGINT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    run_id VARCHAR NOT NULL,
                    created_at VARCHAR NOT NULL,
                    retired_at VARCHAR
                )
                """
            )
            self.con.execute(
                """
                CREATE TABLE runs (
                    id VARCHAR PRIMARY KEY,
                    operation VARCHAR NOT NULL,
                    status VARCHAR NOT NULL,
                    started_at VARCHAR NOT NULL,
                    ended_at VARCHAR,
                    revision_before BIGINT NOT NULL,
                    revision_after BIGINT,
                    request_json VARCHAR NOT NULL,
                    summary_json VARCHAR,
                    error VARCHAR
                )
                """
            )
            self.con.execute(
                """
                CREATE TABLE checkpoints (
                    run_id VARCHAR NOT NULL,
                    archive_id VARCHAR NOT NULL,
                    source_fingerprint VARCHAR NOT NULL,
                    next_offset BIGINT NOT NULL,
                    records_count BIGINT NOT NULL,
                    headers_count BIGINT NOT NULL,
                    state_json VARCHAR NOT NULL,
                    updated_at VARCHAR NOT NULL,
                    PRIMARY KEY (run_id, archive_id)
                )
                """
            )
            self.con.execute(
                "INSERT INTO meta VALUES (?, ?), (?, ?)",
                [
                    "schema_version",
                    str(SCHEMA_VERSION),
                    "data_root",
                    str(self.data_root),
                ],
            )
            self.con.execute(
                "INSERT INTO catalog_state VALUES (1, 0, ?)",
                [utc_now()],
            )
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise

    def _legacy_columns(self, table: str) -> set[str]:
        return {row[1] for row in self.con.execute(f"PRAGMA table_info('{table}')").fetchall()}

    def _migrate_legacy(self) -> None:
        backup = self.db_path.with_suffix(self.db_path.suffix + ".legacy.bak")
        self.con.close()
        if not backup.exists():
            shutil.copy2(self.db_path, backup)
        try:
            self.con = duckdb.connect(str(self.db_path))
            self._apply_legacy_migration()
        except Exception:
            with suppress(Exception):
                self.con.close()
            shutil.copy2(backup, self.db_path)
            self.con = duckdb.connect(str(self.db_path))
            self.con.close()
            raise

    def _apply_legacy_migration(self) -> None:
        table_columns = self._legacy_columns("tables")

        self._create_schema()
        file_rows = self.con.execute("SELECT * FROM files").fetchall()
        file_names = [item[0] for item in self.con.description]
        archive_map: dict[str, str] = {}
        for values in file_rows:
            item = dict(zip(file_names, values, strict=True))
            raw_source = item.get("fullpath") or item.get("filename")
            source = canonical_path(str(raw_source), base=self.db_path.parent)
            archive_id = str(item.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, source.as_uri()).hex)
            size = int(item.get("filesize") or (source.stat().st_size if source.exists() else 0))
            mtime = source.stat().st_mtime_ns if source.exists() else 0
            fingerprint = SourceFingerprint(size=size, mtime_ns=mtime).to_json()
            now = utc_now()
            self.con.execute(
                """
                INSERT OR IGNORE INTO archives
                (id, source_uri, source_path, filename, size, mtime_ns, fingerprint,
                 status, num_records, created_at, updated_at, last_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                [
                    archive_id,
                    source.as_uri(),
                    str(source),
                    source.name,
                    size,
                    mtime,
                    fingerprint,
                    "legacy",
                    int(item.get("num_records") or 0),
                    now,
                    now,
                ],
            )
            archive_map[str(raw_source)] = archive_id
            archive_map[source.name] = archive_id

        if "wf_id" in table_columns:
            rows = self.con.execute(
                "SELECT wf_id, wf_filename, path, type, num_items FROM tables"
            ).fetchall()
            normalized = rows
            id_column = "wf_id"
        elif "warcfile" in table_columns:
            rows = self.con.execute(
                "SELECT warcfile, warcfile, path, type, num_items FROM tables"
            ).fetchall()
            normalized = rows
            id_column = "warcfile"
        elif {"file_id", "table_type", "path"}.issubset(table_columns):
            rows = self.con.execute(
                "SELECT file_id, file_id, path, table_type, 0 FROM tables"
            ).fetchall()
            normalized = rows
            id_column = "file_id"
        else:
            raise SchemaCompatibilityError(
                "Legacy tables layout is not recognized; restore the backup and rebuild"
            )
        for wf_id, wf_filename, raw_path, kind, num_items in normalized:
            migrated_archive_id: str | None = (
                str(wf_id) if id_column in {"wf_id", "file_id"} else archive_map.get(str(wf_id))
            )
            migrated_archive_id = migrated_archive_id or archive_map.get(
                Path(str(wf_filename)).name
            )
            if not migrated_archive_id:
                continue
            sidecar_path = canonical_path(str(raw_path), base=self.db_path.parent)
            self.con.execute(
                """
                INSERT OR IGNORE INTO sidecars
                (id, archive_id, kind, path, status, num_items, schema_version,
                 run_id, created_at, retired_at)
                VALUES (?, ?, ?, ?, 'active', ?, 0, 'legacy-migration', ?, NULL)
                """,
                [
                    uuid.uuid4().hex,
                    migrated_archive_id,
                    str(kind),
                    self.store_path(sidecar_path),
                    int(num_items or 0),
                    utc_now(),
                ],
            )

        self.con.execute(
            "INSERT OR REPLACE INTO meta VALUES ('migrated_from', ?)",
            ["1.2/1.3"],
        )

    def store_path(self, path: Path) -> str:
        """Store workspace paths relatively when possible."""
        path = canonical_path(path)
        try:
            return str(path.relative_to(self.data_root))
        except ValueError:
            return str(path)

    def resolve_path(self, stored: str) -> Path:
        path = Path(stored)
        return canonical_path(path if path.is_absolute() else self.data_root / path)

    def revision(self) -> int:
        row = self.con.execute("SELECT revision FROM catalog_state WHERE singleton = 1").fetchone()
        if row is None:
            raise SchemaCompatibilityError("Catalog revision row is missing")
        return int(row[0])

    def _advance_revision(self) -> int:
        revision = self.revision() + 1
        self.con.execute(
            "UPDATE catalog_state SET revision = ?, updated_at = ? WHERE singleton = 1",
            [revision, utc_now()],
        )
        return revision

    @contextmanager
    def writer_lock(self, operation: str) -> Iterator[None]:
        """Acquire the single-writer filesystem lock."""
        self.data_root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "operation": operation,
                "started_at": utc_now(),
            },
            sort_keys=True,
        )
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            try:
                owner = self.lock_path.read_text(encoding="utf-8")
            except OSError:
                owner = "unknown"
            raise WorkspaceLockedError(f"Workspace writer lock is held: {owner}") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            yield
        finally:
            with suppress(FileNotFoundError):
                self.lock_path.unlink()

    def start_run(self, operation: str, request: dict[str, Any]) -> str:
        run_id = uuid.uuid4().hex
        self.con.execute(
            """
            INSERT INTO runs
            (id, operation, status, started_at, ended_at, revision_before,
             revision_after, request_json, summary_json, error)
            VALUES (?, ?, 'running', ?, NULL, ?, NULL, ?, NULL, NULL)
            """,
            [run_id, operation, utc_now(), self.revision(), json.dumps(request, sort_keys=True)],
        )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, Any],
        error: str | None = None,
    ) -> None:
        self.con.execute(
            """
            UPDATE runs SET status = ?, ended_at = ?, revision_after = ?,
              summary_json = ?, error = ? WHERE id = ?
            """,
            [
                status,
                utc_now(),
                self.revision(),
                json.dumps(summary, sort_keys=True),
                error,
                run_id,
            ],
        )

    def annotate_run(
        self,
        run_id: str,
        *,
        operation: str,
        request: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """Attach an orchestration-level request and outcome to an existing run."""
        self.con.execute(
            "UPDATE runs SET operation = ?, request_json = ?, summary_json = ? WHERE id = ?",
            [
                operation,
                json.dumps(request, sort_keys=True),
                json.dumps(summary, sort_keys=True),
                run_id,
            ],
        )

    def ensure_archive(self, source: Path, fingerprint: SourceFingerprint) -> dict[str, Any]:
        source = canonical_path(source)
        row = self.con.execute(
            "SELECT * FROM archives WHERE source_uri = ?",
            [source.as_uri()],
        ).fetchone()
        if row:
            return dict(zip([item[0] for item in self.con.description], row, strict=True))
        archive_id = uuid.uuid4().hex
        now = utc_now()
        self.con.execute(
            """
            INSERT INTO archives
            (id, source_uri, source_path, filename, size, mtime_ns, fingerprint,
             status, num_records, created_at, updated_at, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'registered', 0, ?, ?, NULL)
            """,
            [
                archive_id,
                source.as_uri(),
                str(source),
                source.name,
                fingerprint.size,
                fingerprint.mtime_ns,
                fingerprint.to_json(),
                now,
                now,
            ],
        )
        return self.get_archive(archive_id)

    def get_archive(self, archive_id: str) -> dict[str, Any]:
        cursor = self.con.execute("SELECT * FROM archives WHERE id = ?", [archive_id])
        row = cursor.fetchone()
        if not row:
            raise WorkspaceError(f"Archive not found: {archive_id}")
        return dict(zip([item[0] for item in cursor.description], row, strict=True))

    def find_archive_by_source(self, source: Path) -> dict[str, Any] | None:
        cursor = self.con.execute(
            "SELECT * FROM archives WHERE source_uri = ?",
            [canonical_path(source).as_uri()],
        )
        row = cursor.fetchone()
        return (
            dict(zip([item[0] for item in cursor.description], row, strict=True)) if row else None
        )

    def list_archives(self) -> list[dict[str, Any]]:
        cursor = self.con.execute("SELECT * FROM archives ORDER BY source_path")
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def active_sidecars(
        self,
        kind: str,
        archive_ids: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM sidecars WHERE kind = ? AND status = 'active'"
        params: list[Any] = [kind]
        if archive_ids:
            sql += f" AND archive_id IN ({','.join('?' for _ in archive_ids)})"
            params.extend(archive_ids)
        sql += " ORDER BY archive_id, created_at"
        cursor = self.con.execute(sql, params)
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def active_sidecar_paths(
        self,
        kind: str,
        archive_ids: Sequence[str] | None = None,
    ) -> list[str]:
        return [
            str(self.resolve_path(item["path"])) for item in self.active_sidecars(kind, archive_ids)
        ]

    def publish_archive(
        self,
        *,
        archive_id: str,
        fingerprint: SourceFingerprint,
        run_id: str,
        sidecars: Sequence[tuple[str, Path, int]],
        num_records: int,
    ) -> int:
        """Atomically switch catalog membership to completed sidecars."""
        now = utc_now()
        self.con.execute("BEGIN TRANSACTION")
        try:
            kinds = [kind for kind, _, _ in sidecars]
            # Derived indexes are tied to the record revision that produced
            # them. Replacing records must make those older results invisible.
            if "records" in kinds:
                self.con.execute(
                    """
                    UPDATE sidecars SET status = 'retired', retired_at = ?
                    WHERE archive_id = ? AND kind NOT IN ('records', 'headers')
                      AND status = 'active'
                    """,
                    [now, archive_id],
                )
            for kind in kinds:
                self.con.execute(
                    """
                    UPDATE sidecars SET status = 'retired', retired_at = ?
                    WHERE archive_id = ? AND kind = ? AND status = 'active'
                    """,
                    [now, archive_id, kind],
                )
            for kind, path, count in sidecars:
                self.con.execute(
                    """
                    INSERT INTO sidecars
                    (id, archive_id, kind, path, status, num_items, schema_version,
                     run_id, created_at, retired_at)
                    VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, NULL)
                    """,
                    [
                        uuid.uuid4().hex,
                        archive_id,
                        kind,
                        self.store_path(path),
                        count,
                        SIDECAR_SCHEMA_VERSION,
                        run_id,
                        now,
                    ],
                )
            self.con.execute(
                """
                UPDATE archives SET size = ?, mtime_ns = ?, fingerprint = ?,
                  status = 'complete', num_records = ?, updated_at = ?, last_error = NULL
                WHERE id = ?
                """,
                [
                    fingerprint.size,
                    fingerprint.mtime_ns,
                    fingerprint.to_json(),
                    num_records,
                    now,
                    archive_id,
                ],
            )
            revision = self._advance_revision()
            self.con.execute("COMMIT")
            return revision
        except Exception:
            self.con.execute("ROLLBACK")
            raise

    def publish_sidecar(
        self,
        *,
        archive_id: str,
        kind: str,
        path: Path,
        num_items: int,
        run_id: str,
    ) -> int:
        return self.publish_archive(
            archive_id=archive_id,
            fingerprint=SourceFingerprint.from_json(self.get_archive(archive_id)["fingerprint"]),
            run_id=run_id,
            sidecars=[(kind, path, num_items)],
            num_records=int(self.get_archive(archive_id)["num_records"]),
        )

    def mark_archive_error(self, archive_id: str, error: str, *, partial: bool = False) -> None:
        self.con.execute(
            "UPDATE archives SET status = ?, updated_at = ?, last_error = ? WHERE id = ?",
            ["partial" if partial else "failed", utc_now(), error, archive_id],
        )

    def save_checkpoint(
        self,
        *,
        run_id: str,
        archive_id: str,
        fingerprint: SourceFingerprint,
        next_offset: int,
        records_count: int,
        headers_count: int,
        state: dict[str, Any],
    ) -> None:
        self.con.execute(
            """
            INSERT OR REPLACE INTO checkpoints
            (run_id, archive_id, source_fingerprint, next_offset, records_count,
             headers_count, state_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                archive_id,
                fingerprint.to_json(),
                next_offset,
                records_count,
                headers_count,
                json.dumps(state, sort_keys=True),
                utc_now(),
            ],
        )

    def latest_checkpoint(
        self, archive_id: str, fingerprint: SourceFingerprint
    ) -> dict[str, Any] | None:
        cursor = self.con.execute(
            """
            SELECT * FROM checkpoints
            WHERE archive_id = ? AND source_fingerprint = ?
            ORDER BY updated_at DESC LIMIT 1
            """,
            [archive_id, fingerprint.to_json()],
        )
        row = cursor.fetchone()
        if not row:
            return None
        result = dict(zip([item[0] for item in cursor.description], row, strict=True))
        result["state"] = json.loads(result.pop("state_json"))
        return result

    def clear_checkpoints(self, archive_id: str) -> None:
        self.con.execute("DELETE FROM checkpoints WHERE archive_id = ?", [archive_id])

    def rebind_archive(self, archive_id: str, new_source: Path, *, force: bool = False) -> None:
        archive = self.get_archive(archive_id)
        new_source = canonical_path(new_source)
        previous = SourceFingerprint.from_json(archive["fingerprint"])
        current = SourceFingerprint.from_path(new_source, digest=previous.sha256 is not None)
        matches = current.size == previous.size and (
            current.sha256 == previous.sha256
            if previous.sha256 is not None
            else current.mtime_ns == previous.mtime_ns
        )
        if not force and not matches:
            raise WorkspaceError(
                "New source fingerprint does not match; use force only after independent verification"
            )
        self.con.execute("BEGIN TRANSACTION")
        try:
            self.con.execute(
                """
                UPDATE archives SET source_uri = ?, source_path = ?, filename = ?,
                  size = ?, mtime_ns = ?, fingerprint = ?, updated_at = ? WHERE id = ?
                """,
                [
                    new_source.as_uri(),
                    str(new_source),
                    new_source.name,
                    current.size,
                    current.mtime_ns,
                    current.to_json(),
                    utc_now(),
                    archive_id,
                ],
            )
            self._advance_revision()
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise

    def doctor(self, *, repair: bool = False, dry_run: bool = True) -> DoctorReport:
        report = DoctorReport(database=str(self.db_path), schema_version=SCHEMA_VERSION)
        catalog_paths: set[Path] = set()
        for archive in self.list_archives():
            source = Path(archive["source_path"])
            if not source.exists():
                report.issues.append(
                    DoctorIssue(
                        code="source-missing",
                        severity="error",
                        archive_id=archive["id"],
                        path=str(source),
                        message="Registered WARC source is missing",
                        repair="rebind or restore the source",
                    )
                )
            else:
                current = SourceFingerprint.from_path(source)
                stored = SourceFingerprint.from_json(archive["fingerprint"])
                if (current.size, current.mtime_ns) != (stored.size, stored.mtime_ns):
                    report.issues.append(
                        DoctorIssue(
                            code="source-stale",
                            severity="warning",
                            archive_id=archive["id"],
                            path=str(source),
                            message="Source fingerprint changed since the last completed index",
                            repair="run update or force",
                        )
                    )

        cursor = self.con.execute("SELECT archive_id, kind, path, status FROM sidecars")
        for archive_id, kind, stored, status in cursor.fetchall():
            if status == "purged":
                continue
            path = self.resolve_path(stored)
            catalog_paths.add(path)
            if not path.exists():
                report.issues.append(
                    DoctorIssue(
                        code="sidecar-missing",
                        severity="error" if status == "active" else "warning",
                        archive_id=archive_id,
                        path=str(path),
                        message=f"{status} {kind} sidecar is missing",
                        repair=f"rescan {kind}",
                    )
                )
                continue
            try:
                _ = pq.ParquetFile(path).metadata
            except Exception as exc:
                report.issues.append(
                    DoctorIssue(
                        code="sidecar-corrupt",
                        severity="error" if status == "active" else "warning",
                        archive_id=archive_id,
                        path=str(path),
                        message=f"Unreadable {kind} sidecar: {exc}",
                        repair=f"rescan {kind}",
                    )
                )

        if self.sidecar_root.exists():
            for path in self.sidecar_root.rglob("*.parquet"):
                resolved = path.resolve()
                if resolved not in catalog_paths:
                    report.issues.append(
                        DoctorIssue(
                            code="orphan-sidecar",
                            severity="warning",
                            path=str(resolved),
                            message="Parquet sidecar is not registered in the catalog",
                            repair="move to quarantine",
                        )
                    )
                    if repair:
                        target = self.quarantine_root / resolved.relative_to(self.sidecar_root)
                        report.actions.append(f"move {resolved} -> {target}")
                        if not dry_run:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(resolved), str(target))
        return report

    def cleanup_retired(
        self,
        *,
        retention_days: float = 7.0,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Preview or purge expired retired sidecars and unprotected staging files."""
        if retention_days < 0:
            raise WorkspaceError("retention_days cannot be negative")
        cutoff = datetime.now(timezone.utc).timestamp() - retention_days * 86_400
        candidates: list[dict[str, Any]] = []
        active_paths = {
            self.resolve_path(row[0])
            for row in self.con.execute(
                "SELECT path FROM sidecars WHERE status = 'active'"
            ).fetchall()
        }
        retired = self.con.execute(
            "SELECT id, archive_id, kind, path, retired_at FROM sidecars "
            "WHERE status = 'retired' ORDER BY retired_at, id"
        ).fetchall()
        for sidecar_id, archive_id, kind, stored, retired_at in retired:
            path = self.resolve_path(stored)
            retired_time = (
                datetime.fromisoformat(str(retired_at)).timestamp()
                if retired_at
                else path.stat().st_mtime
                if path.exists()
                else 0
            )
            if retired_time > cutoff or path in active_paths:
                continue
            candidates.append(
                {
                    "category": "retired-sidecar",
                    "id": sidecar_id,
                    "archive_id": archive_id,
                    "kind": kind,
                    "path": str(path),
                    "reason": f"retired for at least {retention_days:g} days",
                }
            )

        protected_parts: set[Path] = set()
        for (state_json,) in self.con.execute("SELECT state_json FROM checkpoints").fetchall():
            state = json.loads(state_json)
            for key in ("record_parts", "header_parts", "parts"):
                protected_parts.update(canonical_path(value) for value in state.get(key, []))
        if self.staging_root.exists():
            for path in sorted(item for item in self.staging_root.rglob("*") if item.is_file()):
                if path in protected_parts or path.stat().st_mtime > cutoff:
                    continue
                candidates.append(
                    {
                        "category": "staging-file",
                        "id": None,
                        "archive_id": None,
                        "kind": None,
                        "path": str(path),
                        "reason": f"unreferenced staging file older than {retention_days:g} days",
                    }
                )

        actions: list[str] = []
        if not dry_run:
            self.con.execute("BEGIN TRANSACTION")
            try:
                for candidate in candidates:
                    path = Path(candidate["path"])
                    with suppress(FileNotFoundError):
                        path.unlink()
                    actions.append(f"removed {path}")
                    if candidate["category"] == "retired-sidecar":
                        self.con.execute(
                            "UPDATE sidecars SET status = 'purged' WHERE id = ? AND status = 'retired'",
                            [candidate["id"]],
                        )
                self.con.execute("COMMIT")
            except Exception:
                self.con.execute("ROLLBACK")
                raise
            if self.staging_root.exists():
                for directory in sorted(
                    (item for item in self.staging_root.rglob("*") if item.is_dir()),
                    reverse=True,
                ):
                    with suppress(OSError):
                        directory.rmdir()
        return {
            "database": str(self.db_path),
            "retention_days": retention_days,
            "dry_run": dry_run,
            "candidates": candidates,
            "actions": actions,
        }

    def temporary_directory(self, run_id: str, archive_id: str) -> Path:
        path = self.staging_root / run_id / archive_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def new_sidecar_path(self, archive_id: str, run_id: str, kind: str) -> Path:
        directory = self.sidecar_root / archive_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{run_id}-{kind}.parquet"

    def combine_parquet_parts(
        self,
        parts: Sequence[Path],
        destination: Path,
        *,
        schema: Any,
    ) -> int:
        """Combine valid bounded parts and atomically publish a Parquet file."""
        if not parts:
            return 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_temp = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(fd)
        temp_path = Path(raw_temp)
        count = 0
        writer = None
        try:
            import pyarrow as pa
            import pyarrow.parquet as parquet

            writer = parquet.ParquetWriter(temp_path, schema, compression="zstd")
            for part in parts:
                parquet_file = parquet.ParquetFile(part)
                for batch in parquet_file.iter_batches(batch_size=8192):
                    table = pa.Table.from_batches([batch], schema=schema)
                    writer.write_table(table)
                    count += table.num_rows
            writer.close()
            writer = None
            _ = pq.ParquetFile(temp_path).metadata
            os.replace(temp_path, destination)
            return count
        finally:
            if writer is not None:
                writer.close()
            if temp_path.exists():
                temp_path.unlink()

    def cleanup_staging(self, run_id: str) -> None:
        path = self.staging_root / run_id
        if path.exists():
            shutil.rmtree(path)
