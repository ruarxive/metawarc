"""Shared DuckDB helpers for metawarc."""

import os
import re
from typing import List, Optional

import duckdb

from metawarc import settings

_UNSAFE_SQL = re.compile(
    r"(;|--|/\*|\*/|\b(drop|delete|insert|update|create|alter|attach|copy|pragma)\b)",
    re.IGNORECASE,
)


def db_path(dbfile: Optional[str] = None) -> str:
    return dbfile or settings.DB_PATH


def connect(dbfile: Optional[str] = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = db_path(dbfile)
    if read_only:
        return duckdb.connect(path, read_only=True)
    return duckdb.connect(path)


def require_db(dbfile: Optional[str] = None) -> str:
    path = db_path(dbfile)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return path


def list_wf_ids(con: duckdb.DuckDBPyConnection, warcfileids: Optional[str] = None) -> List[str]:
    if warcfileids is None:
        return [row[0] for row in con.sql("select id from files;").fetchall()]
    return [item.strip() for item in warcfileids.split(",") if item.strip()]


def records_table_path(con: duckdb.DuckDBPyConnection, wf_id: str) -> Optional[str]:
    row = con.sql(
        f"select path from tables where type = 'records' and wf_id = '{wf_id}';"
    ).fetchone()
    return row[0] if row else None


def metadata_table_path(
    con: duckdb.DuckDBPyConnection, wf_id: str, metadata_type: str
) -> Optional[str]:
    row = con.sql(
        f"select path from tables where type = '{metadata_type}' and wf_id = '{wf_id}';"
    ).fetchone()
    return row[0] if row else None


def query_records(con: duckdb.DuckDBPyConnection, sql: str) -> List[dict]:
    rel = con.sql(sql)
    columns = list(rel.columns)
    return [dict(zip(columns, row)) for row in rel.fetchall()]


def query_value(con: duckdb.DuckDBPyConnection, sql: str):
    row = con.sql(sql).fetchone()
    return row[0] if row else None


def validate_where_clause(query: Optional[str]) -> Optional[str]:
    """Reject obviously unsafe SQL fragments used as WHERE clauses."""
    if query is None:
        return None
    clause = query.strip()
    if not clause:
        return None
    if _UNSAFE_SQL.search(clause):
        raise ValueError("Query contains disallowed SQL constructs")
    return clause


def build_record_filter(
    mimes: Optional[str] = None,
    exts: Optional[str] = None,
    query: Optional[str] = None,
    url_pattern: Optional[str] = None,
) -> str:
    parts = []
    if mimes:
        values = ",".join(f"'{m.strip()}'" for m in mimes.split(",") if m.strip())
        parts.append(f"c_type in ({values})")
    if exts:
        values = ",".join(f"'{e.strip()}'" for e in exts.split(",") if e.strip())
        parts.append(f"ext in ({values})")
    if url_pattern:
        safe = url_pattern.replace("'", "''")
        parts.append(f"url like '%{safe}%'")
    if query:
        parts.append(validate_where_clause(query))
    if not parts:
        return ""
    return " where " + " and ".join(parts)
