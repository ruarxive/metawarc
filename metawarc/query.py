"""Typed, parameterized query service shared by all interfaces."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .errors import QueryValidationError, WorkspaceError
from .workspace import Workspace

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1_000
MAX_OFFSET = 100_000

SORT_FIELDS = {
    "archive_id": "archive_id",
    "warc_id": "warc_id",
    "url": "url",
    "host": "host",
    "mime": "c_type",
    "ext": "ext",
    "status": "status_code",
    "date": "rec_date",
    "size": "content_length",
    "offset": '"offset"',
}

AGGREGATE_FIELDS = {
    "mime": "c_type",
    "c_type": "c_type",
    "ext": "ext",
    "status": "status_code",
    "status_code": "status_code",
    "host": "host",
    "date": "CAST(rec_date AS DATE)",
    "size_bucket": (
        "CASE WHEN content_length < 1024 THEN '<1KiB' "
        "WHEN content_length < 1048576 THEN '1KiB-1MiB' "
        "WHEN content_length < 104857600 THEN '1MiB-100MiB' ELSE '>=100MiB' END"
    ),
}

RECORD_COLUMNS = (
    "archive_id",
    "warc_id",
    "url",
    "host",
    "content_type",
    "c_type",
    "c_type_charset",
    '"offset"',
    '"length"',
    "rec_date",
    "content_length",
    "status_code",
    "source",
    "filename",
    "ext",
    "payload_digest",
    "block_digest",
)


def _items(value: str | Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return tuple(str(item).strip() for item in value if str(item).strip())


def _coerce_timestamp(value: datetime | str) -> datetime:
    """Normalize a capture timestamp to timezone-aware UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    text = value.strip()
    if not text:
        raise QueryValidationError("timestamp must not be empty")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        if len(text) == 14 and text.isdigit():
            parsed = datetime.strptime(text, "%Y%m%d%H%M%S")
        else:
            parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise QueryValidationError(
            "timestamp must be YYYYMMDDHHMMSS or an ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class RecordQuery:
    """Allowlisted record filters and deterministic pagination."""

    archive_ids: tuple[str, ...] = field(default_factory=tuple)
    mimes: tuple[str, ...] = field(default_factory=tuple)
    exts: tuple[str, ...] = field(default_factory=tuple)
    url_pattern: str | None = None
    host_pattern: str | None = None
    status_min: int | None = None
    status_max: int | None = None
    date_from: datetime | str | None = None
    date_to: datetime | str | None = None
    size_min: int | None = None
    size_max: int | None = None
    sort_by: str = "offset"
    descending: bool = False
    offset: int = 0
    limit: int = DEFAULT_PAGE_SIZE
    unsafe_where: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        archive_ids: str | Sequence[str] | None = None,
        mimes: str | Sequence[str] | None = None,
        exts: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> RecordQuery:
        return cls(
            archive_ids=_items(archive_ids),
            mimes=_items(mimes),
            exts=_items(exts),
            **kwargs,
        )

    def validate(self, *, allow_unsafe: bool = False, max_page: int = MAX_PAGE_SIZE) -> None:
        if self.sort_by not in SORT_FIELDS:
            raise QueryValidationError(
                f"Unsupported sort field {self.sort_by!r}; choose {', '.join(SORT_FIELDS)}"
            )
        if self.offset < 0 or self.offset > MAX_OFFSET:
            raise QueryValidationError(f"offset must be between 0 and {MAX_OFFSET}")
        if self.limit < 1 or self.limit > max_page:
            raise QueryValidationError(f"limit must be between 1 and {max_page}")
        if self.status_min is not None and not 0 <= self.status_min <= 999:
            raise QueryValidationError("status_min must be between 0 and 999")
        if self.status_max is not None and not 0 <= self.status_max <= 999:
            raise QueryValidationError("status_max must be between 0 and 999")
        if (
            self.status_min is not None
            and self.status_max is not None
            and self.status_min > self.status_max
        ):
            raise QueryValidationError("status_min cannot exceed status_max")
        if self.size_min is not None and self.size_min < 0:
            raise QueryValidationError("size_min cannot be negative")
        if self.size_max is not None and self.size_max < 0:
            raise QueryValidationError("size_max cannot be negative")
        if (
            self.size_min is not None
            and self.size_max is not None
            and self.size_min > self.size_max
        ):
            raise QueryValidationError("size_min cannot exceed size_max")
        if self.unsafe_where and not allow_unsafe:
            raise QueryValidationError("raw SQL is available only in explicit trusted local mode")


class QueryService:
    """Compile typed queries and return catalog-scoped record data."""

    def __init__(self, workspace: Workspace, *, max_page: int = MAX_PAGE_SIZE) -> None:
        self.workspace = workspace
        self.max_page = max_page

    def list_archives(self) -> list[dict[str, Any]]:
        return self.workspace.list_archives()

    def _paths(
        self, archive_ids: Sequence[str] | None = None, *, kind: str = "records"
    ) -> list[str]:
        if archive_ids:
            for archive_id in archive_ids:
                self.workspace.get_archive(archive_id)
        paths = self.workspace.active_sidecar_paths(kind, archive_ids)
        if not paths:
            if archive_ids:
                raise WorkspaceError(f"No active {kind} sidecars for selected archives")
            return []
        return paths

    def _compile(
        self,
        query: RecordQuery,
        *,
        allow_unsafe: bool = False,
        max_page: int | None = None,
    ) -> tuple[str, list[Any]]:
        query.validate(
            allow_unsafe=allow_unsafe,
            max_page=self.max_page if max_page is None else max_page,
        )
        clauses: list[str] = []
        params: list[Any] = []

        def in_clause(column: str, values: Sequence[str]) -> None:
            if values:
                clauses.append(f"{column} IN ({','.join('?' for _ in values)})")
                params.extend(values)

        in_clause("c_type", query.mimes)
        in_clause("ext", query.exts)
        if query.url_pattern:
            clauses.append("url ILIKE ?")
            params.append(f"%{query.url_pattern}%")
        if query.host_pattern:
            clauses.append("host ILIKE ?")
            params.append(f"%{query.host_pattern}%")
        if query.status_min is not None:
            clauses.append("status_code >= ?")
            params.append(query.status_min)
        if query.status_max is not None:
            clauses.append("status_code <= ?")
            params.append(query.status_max)
        if query.date_from is not None:
            clauses.append("rec_date >= ?")
            params.append(query.date_from)
        if query.date_to is not None:
            clauses.append("rec_date <= ?")
            params.append(query.date_to)
        if query.size_min is not None:
            clauses.append("content_length >= ?")
            params.append(query.size_min)
        if query.size_max is not None:
            clauses.append("content_length <= ?")
            params.append(query.size_max)
        if query.unsafe_where:
            clauses.append(f"({query.unsafe_where})")
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    def list_records(
        self,
        query: RecordQuery,
        *,
        allow_unsafe: bool = False,
    ) -> tuple[int, list[dict[str, Any]]]:
        total = self.count_records(query, allow_unsafe=allow_unsafe)
        paths = self._paths(query.archive_ids)
        if not paths:
            return 0, []
        where, values = self._compile(query, allow_unsafe=allow_unsafe)
        sort_column = SORT_FIELDS[query.sort_by]
        direction = "DESC" if query.descending else "ASC"
        sql = (
            f"SELECT {','.join(RECORD_COLUMNS)} FROM read_parquet(?)"
            f'{where} ORDER BY {sort_column} {direction}, archive_id ASC, "offset" ASC '
            "LIMIT ? OFFSET ?"
        )
        cursor = self.workspace.con.execute(
            sql,
            [paths, *values, query.limit, query.offset],
        )
        columns = [item[0] for item in cursor.description]
        return total, [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def count_records(self, query: RecordQuery, *, allow_unsafe: bool = False) -> int:
        """Count matching records without materializing the selected rows."""
        paths = self._paths(query.archive_ids)
        if not paths:
            return 0
        where, values = self._compile(query, allow_unsafe=allow_unsafe)
        total_row = self.workspace.con.execute(
            f"SELECT COUNT(*) FROM read_parquet(?){where}",
            [paths, *values],
        ).fetchone()
        if total_row is None:
            raise WorkspaceError("Record count query returned no result")
        return int(total_row[0])

    def iter_records(
        self,
        query: RecordQuery,
        *,
        allow_unsafe: bool = False,
        fetch_size: int = 256,
        export_limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        query.validate(allow_unsafe=allow_unsafe, max_page=max(self.max_page, query.limit))
        paths = self._paths(query.archive_ids)
        if not paths:
            return
        where, values = self._compile(
            query,
            allow_unsafe=allow_unsafe,
            max_page=max(self.max_page, query.limit),
        )
        limit = export_limit if export_limit is not None else query.limit
        if limit < 1:
            return
        sql = (
            f"SELECT {','.join(RECORD_COLUMNS)} FROM read_parquet(?)"
            f'{where} ORDER BY source ASC, "offset" ASC LIMIT ? OFFSET ?'
        )
        cursor = self.workspace.con.execute(sql, [paths, *values, limit, query.offset])
        columns = [item[0] for item in cursor.description]
        while rows := cursor.fetchmany(fetch_size):
            for row in rows:
                yield dict(zip(columns, row, strict=True))

    def get_record(
        self,
        file_id: str,
        *,
        archive_id: str | None = None,
    ) -> dict[str, Any] | None:
        paths = self._paths((archive_id,) if archive_id else None)
        if not paths:
            return None
        cursor = self.workspace.con.execute(
            f"""
            SELECT {",".join(RECORD_COLUMNS)} FROM read_parquet(?)
            WHERE warc_id = ? OR url = ?
            ORDER BY archive_id, \"offset\" LIMIT 1
            """,
            [paths, file_id, file_id],
        )
        row = cursor.fetchone()
        return (
            dict(zip([item[0] for item in cursor.description], row, strict=True)) if row else None
        )

    def find_capture(
        self,
        url: str,
        timestamp: datetime | str,
        *,
        policy: str = "closest",
        archive_ids: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        """Select one response record by exact URL and timestamp policy.

        Policies:
        - ``closest``: minimum absolute ``rec_date`` distance; ties break by earlier
          ``rec_date``, then ``archive_id``, then ``offset``.
        - ``exact``: require an exact ``rec_date`` match.
        """
        if policy not in {"closest", "exact"}:
            raise QueryValidationError("timestamp policy must be 'closest' or 'exact'")
        target = _coerce_timestamp(timestamp)
        paths = self._paths(archive_ids)
        if not paths:
            return None
        if policy == "exact":
            sql = (
                f"SELECT {','.join(RECORD_COLUMNS)} FROM read_parquet(?) "
                "WHERE url = ? AND rec_date = ? "
                'ORDER BY archive_id ASC, "offset" ASC LIMIT 1'
            )
            params: list[Any] = [paths, url, target]
        else:
            sql = (
                f"SELECT {','.join(RECORD_COLUMNS)} FROM read_parquet(?) "
                "WHERE url = ? "
                "ORDER BY abs(epoch_ms(rec_date) - epoch_ms(?::TIMESTAMPTZ)), "
                'rec_date ASC, archive_id ASC, "offset" ASC LIMIT 1'
            )
            params = [paths, url, target]
        cursor = self.workspace.con.execute(sql, params)
        row = cursor.fetchone()
        return (
            dict(zip([item[0] for item in cursor.description], row, strict=True)) if row else None
        )

    def get_headers(self, archive_id: str, record_id: str) -> list[dict[str, Any]]:
        paths = self._paths((archive_id,), kind="headers")
        cursor = self.workspace.con.execute(
            """
            SELECT archive_id, warc_id, key, value, source FROM read_parquet(?)
            WHERE warc_id = ? ORDER BY key
            """,
            [paths, record_id],
        )
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def aggregate(
        self,
        dimension: str,
        *,
        archive_ids: Sequence[str] | None = None,
        query: RecordQuery | None = None,
        top: int | None = None,
    ) -> list[dict[str, Any]]:
        if dimension not in AGGREGATE_FIELDS:
            raise QueryValidationError(
                f"Unsupported dimension {dimension!r}; choose {', '.join(AGGREGATE_FIELDS)}"
            )
        selected = query or RecordQuery(archive_ids=tuple(archive_ids or ()), limit=1)
        paths = self._paths(selected.archive_ids)
        if not paths:
            return []
        where, values = self._compile(selected)
        expression = AGGREGATE_FIELDS[dimension]
        limit_sql = ""
        params: list[Any] = [paths, *values]
        if top is not None:
            if top < 1 or top > 100_000:
                raise QueryValidationError("top must be between 1 and 100000")
            limit_sql = " LIMIT ?"
            params.append(top)
        cursor = self.workspace.con.execute(
            f"""
            SELECT {expression} AS dimension, SUM(content_length) AS bytes,
                   COUNT(*) AS count
            FROM read_parquet(?) {where}
            GROUP BY dimension ORDER BY bytes DESC NULLS LAST, dimension ASC{limit_sql}
            """,
            params,
        )
        key = dimension if dimension in {"c_type", "ext", "status_code", "host"} else dimension
        return [
            {key: row[0], "bytes": int(row[1] or 0), "count": int(row[2])}
            for row in cursor.fetchall()
        ]


__all__ = [
    "AGGREGATE_FIELDS",
    "DEFAULT_PAGE_SIZE",
    "MAX_OFFSET",
    "MAX_PAGE_SIZE",
    "QueryService",
    "RecordQuery",
    "SORT_FIELDS",
]
