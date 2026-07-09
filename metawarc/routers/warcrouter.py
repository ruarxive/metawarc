import os
from typing import List, Union

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from fastwarc import ArchiveIterator

from metawarc import settings
from metawarc.data.common import ErrorResponse
from metawarc.dbutil import build_record_filter, connect, query_records, query_value, require_db
from metawarc.logs import get_logger

log = get_logger(__name__)
router = APIRouter()


def _db_missing():
    raise HTTPException(status_code=404, detail="Index database not found")


def _not_found(message: str = "Object not found"):
    raise HTTPException(status_code=404, detail=message)


@router.get(
    "/warcs/list",
    name="List WARC files",
    tags=["Metawarc"],
    response_model=None,
    responses={
        404: {"model": ErrorResponse, "description": "Object not found"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def warcs_list() -> List[dict]:
    """Return list of indexed WARC files with filesize and number of records"""
    try:
        require_db()
    except FileNotFoundError:
        _db_missing()
    con = connect(read_only=True)
    try:
        return query_records(con, 'select * from files;')
    finally:
        con.close()


@router.get(
    "/records/list",
    name="List WARC records",
    tags=["Metawarc"],
    response_model=None,
    responses={
        404: {"model": ErrorResponse, "description": "Object not found"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def records_list(
    wf_id: str = Query(None, title="WARC file identifier"),
    query: str = Query(None, title="DuckDB WHERE clause fragment (advanced)"),
    mimes: str = Query(None, title="Comma-separated MIME types"),
    exts: str = Query(None, title="Comma-separated file extensions"),
    url_pattern: str = Query(None, title="Substring match on record URL"),
    start: int = Query(0, title="Starting element", le=settings.MAX_OFFSET),
    limit: int = Query(20, title="Number of results to return", le=settings.MAX_PAGE),
) -> dict:
    """List file metadata records in a single WARC file or all WARC files"""
    try:
        require_db()
    except FileNotFoundError:
        _db_missing()

    try:
        where = build_record_filter(mimes=mimes, exts=exts, query=query, url_pattern=url_pattern)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pattern = f'data/{wf_id}_records.parquet' if wf_id else 'data/*_records.parquet'
    con = connect(read_only=True)
    try:
        totals = query_value(con, f"select count(*) as c from '{pattern}'{where}")
        results = query_records(con, f"select * from '{pattern}'{where} offset {start} limit {limit}")
    finally:
        con.close()
    return {'totals': totals, 'start': start, 'limit': limit, 'items': results}


@router.get(
    "/records/get/{wf_id}/record/{record_id}",
    name="Get WARC record metadata",
    tags=["Metawarc"],
    response_model=None,
    responses={
        404: {"model": ErrorResponse, "description": "Object not found"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def records_get(
    wf_id: str = Path(description="WARC file identifier"),
    record_id: str = Path(description="WARC Record identifier"),
) -> dict:
    """Return single file metadata record by record id and WARC id"""
    try:
        require_db()
    except FileNotFoundError:
        _db_missing()

    safe_id = record_id.replace("'", "''")
    pattern = f'data/{wf_id}_records.parquet'
    con = connect(read_only=True)
    try:
        results = query_records(con, f"select * from '{pattern}' where warc_id = '{safe_id}'")
    finally:
        con.close()
    if results:
        return results[0]
    _not_found("Record not found")


@router.get(
    "/records/get/{wf_id}/headers/{record_id}",
    name="Get record HTTP headers",
    tags=["Metawarc"],
    response_model=None,
    responses={
        404: {"model": ErrorResponse, "description": "Object not found"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def records_get_headers(
    wf_id: str = Path(description="WARC file identifier"),
    record_id: str = Path(description="WARC Record identifier"),
    mode: str = Query('dict', title="Output type: records or dict"),
) -> Union[List[dict], dict]:
    """Return HTTP headers for a record by record id and WARC id"""
    try:
        require_db()
    except FileNotFoundError:
        _db_missing()

    safe_id = record_id.replace("'", "''")
    pattern = f'data/{wf_id}_headers.parquet'
    con = connect(read_only=True)
    try:
        results = query_records(con, f"select * from '{pattern}' where warc_id = '{safe_id}'")
    finally:
        con.close()
    if not results:
        _not_found("Headers not found")
    if mode == 'records':
        return results
    out = {}
    for r in results:
        out[r['key']] = r['value']
    return out


@router.get(
    "/records/get/{wf_id}/data/{record_id}",
    name="Get record data",
    tags=["Metawarc"],
    response_model=None,
    responses={
        404: {"model": ErrorResponse, "description": "Object not found"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
)
async def record_get_data(
    wf_id: str = Path(description="WARC file identifier"),
    record_id: str = Path(description="WARC Record identifier"),
) -> StreamingResponse:
    """Return record contents (data)"""
    try:
        require_db()
    except FileNotFoundError:
        _db_missing()

    safe_id = record_id.replace("'", "''")
    pattern = f'data/{wf_id}_records.parquet'
    con = connect(read_only=True)
    try:
        results = query_records(con, f"select * from '{pattern}' where warc_id = '{safe_id}'")
    finally:
        con.close()
    if not results:
        _not_found("Record not found")
    record = results[0]
    if not os.path.exists(record['source']):
        _not_found("WARC source file not found on disk")

    async def iterfile():
        with open(record['source'], "rb") as fileobj:
            fileobj.seek(record['offset'])
            it = iter(ArchiveIterator(fileobj))
            warcrec = next(it)
            f = warcrec.reader
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(iterfile(), media_type=record['content_type'])
