"""Optional authenticated read-only FastAPI adapter."""

from __future__ import annotations

import asyncio
import logging
import secrets
import uuid
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from .. import __version__
from ..api_models import (
    ArchiveResponse,
    ErrorResponse,
    HeaderResponse,
    HealthResponse,
    RecordPage,
    RecordResponse,
)
from ..cmds.dump import iter_payload, safe_record_token
from ..errors import QueryValidationError, WorkspaceError
from ..query import QueryService, RecordQuery
from ..replay import ReplayError, ReplayService, replay_url, wayback_timestamp
from ..settings import ServerSettings
from ..workspace import SCHEMA_VERSION, Workspace

LOGGER = logging.getLogger("metawarc.api")


def create_app(settings: ServerSettings | None = None) -> FastAPI:
    """Create a REST app without mutating module-global database settings."""
    config = settings or ServerSettings.from_env()
    app = FastAPI(
        title="Metawarc API",
        description="Read-only typed access to a versioned WARC index workspace.",
        version=__version__,
    )
    semaphore = asyncio.Semaphore(config.max_concurrency)

    async def authorize(authorization: Annotated[str | None, Header()] = None) -> None:
        if config.token is None:
            return
        expected = f"Bearer {config.token}"
        if authorization is None or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Missing or invalid bearer token")

    @app.middleware("http")
    async def bounded_request(request: Request, call_next: Any) -> Any:
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
        if request.url.path == "/records/list":
            allowed = {
                "archive_ids",
                "mimes",
                "exts",
                "url_pattern",
                "host_pattern",
                "status_min",
                "status_max",
                "size_min",
                "size_max",
                "sort_by",
                "descending",
                "offset",
                "limit",
            }
            unexpected = sorted(set(request.query_params) - allowed)
            if unexpected:
                response = JSONResponse(
                    status_code=422,
                    content={
                        "detail": f"Unsupported query parameter(s): {', '.join(unexpected)}",
                        "trace_id": trace_id,
                    },
                )
                response.headers["x-trace-id"] = trace_id
                return response
        try:
            async with semaphore:
                response = await asyncio.wait_for(
                    call_next(request), timeout=config.request_timeout_seconds
                )
        except asyncio.TimeoutError:
            response = JSONResponse(
                status_code=504,
                content={"detail": "Request time limit exceeded", "trace_id": trace_id},
            )
        except Exception:
            LOGGER.exception(
                "Unhandled API request error trace_id=%s method=%s path=%s",
                trace_id,
                request.method,
                request.url.path,
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "trace_id": trace_id},
            )
        response.headers["x-trace-id"] = trace_id
        LOGGER.info(
            "request trace_id=%s method=%s path=%s status=%s",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    @app.exception_handler(WorkspaceError)
    async def workspace_error(request: Request, exc: WorkspaceError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(QueryValidationError)
    async def query_error(request: Request, exc: QueryValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ReplayError)
    async def replay_error(request: Request, exc: ReplayError) -> JSONResponse:
        detail = str(exc)
        status = 404 if detail.startswith("No capture") else 409
        return JSONResponse(status_code=status, content={"detail": detail})

    @app.get(
        "/health",
        response_model=HealthResponse,
        responses={404: {"model": ErrorResponse}},
    )
    def health(_: None = Depends(authorize)) -> HealthResponse:
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            return HealthResponse(
                status="ok", schema_version=SCHEMA_VERSION, revision=ws.revision()
            )

    @app.get(
        "/warcs/list",
        response_model=list[ArchiveResponse],
        responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    def list_archives(_: None = Depends(authorize)) -> list[dict[str, Any]]:
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            return QueryService(ws).list_archives()

    @app.get(
        "/records/list",
        response_model=RecordPage,
        responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    )
    def list_records(
        archive_ids: Annotated[str | None, Query(description="Comma-separated archive IDs")] = None,
        mimes: Annotated[str | None, Query(description="Comma-separated MIME values")] = None,
        exts: Annotated[str | None, Query(description="Comma-separated extensions")] = None,
        url_pattern: str | None = None,
        host_pattern: str | None = None,
        status_min: int | None = Query(None, ge=0, le=999),
        status_max: int | None = Query(None, ge=0, le=999),
        size_min: int | None = Query(None, ge=0),
        size_max: int | None = Query(None, ge=0),
        sort_by: str = "offset",
        descending: bool = False,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1),
        _: None = Depends(authorize),
    ) -> RecordPage:
        selected = RecordQuery.from_values(
            archive_ids=archive_ids,
            mimes=mimes,
            exts=exts,
            url_pattern=url_pattern,
            host_pattern=host_pattern,
            status_min=status_min,
            status_max=status_max,
            size_min=size_min,
            size_max=size_max,
            sort_by=sort_by,
            descending=descending,
            offset=offset,
            limit=limit,
        )
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            total, rows = QueryService(ws, max_page=config.max_page).list_records(selected)
            return RecordPage(
                total=total,
                offset=offset,
                limit=limit,
                revision=ws.revision(),
                items=[RecordResponse.model_validate(item) for item in rows],
            )

    @app.get(
        "/records/get/{archive_id}/record/{record_id}",
        response_model=RecordResponse,
        responses={404: {"model": ErrorResponse}},
    )
    def get_record(
        archive_id: Annotated[str, Path(description="Catalog archive ID")],
        record_id: Annotated[str, Path(description="WARC record ID")],
        _: None = Depends(authorize),
    ) -> RecordResponse:
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            record = QueryService(ws).get_record(record_id, archive_id=archive_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Record not found")
            return RecordResponse.model_validate(record)

    @app.get(
        "/records/get/{archive_id}/headers/{record_id}",
        response_model=list[HeaderResponse],
        responses={404: {"model": ErrorResponse}},
    )
    def get_headers(
        archive_id: str,
        record_id: str,
        _: None = Depends(authorize),
    ) -> list[HeaderResponse]:
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            rows = QueryService(ws).get_headers(archive_id, record_id)
            if not rows:
                raise HTTPException(status_code=404, detail="Headers not found")
            return [HeaderResponse(key=item["key"], value=item["value"]) for item in rows]

    @app.get(
        "/records/get/{archive_id}/data/{record_id}",
        response_class=StreamingResponse,
        responses={404: {"model": ErrorResponse}},
    )
    def get_payload(
        archive_id: str,
        record_id: str,
        _: None = Depends(authorize),
    ) -> StreamingResponse:
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            record = QueryService(ws).get_record(record_id, archive_id=archive_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        filename = safe_record_token(record["warc_id"])
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return StreamingResponse(
            iter_payload(record, max_bytes=config.max_payload_bytes),
            media_type=record.get("content_type") or "application/octet-stream",
            headers=headers,
        )

    def _replay_home(_: None = Depends(authorize)) -> Response:
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            body = ReplayService(ws, max_payload_bytes=config.max_payload_bytes).home_page()
        return Response(content=body, media_type="text/html; charset=utf-8")

    @app.get("/", response_class=Response, include_in_schema=False)
    def root_home(_: None = Depends(authorize)) -> Response:
        return _replay_home(_)

    @app.get("/replay", response_class=Response, include_in_schema=False)
    @app.get("/replay/", response_class=Response, include_in_schema=False)
    def replay_home(_: None = Depends(authorize)) -> Response:
        return _replay_home(_)

    @app.get(
        "/replay/sites",
        responses={401: {"model": ErrorResponse}},
        operation_id="list_replay_sites",
    )
    def list_replay_sites(
        limit: Annotated[int, Query(ge=1, le=10_000)] = 500,
        _: None = Depends(authorize),
    ) -> list[dict[str, Any]]:
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            sites = []
            for site in ReplayService(ws).list_sites(limit=limit):
                stamp = wayback_timestamp(site["last_date"])
                sites.append(
                    {
                        "host": site["host"],
                        "entry_url": site["entry_url"],
                        "captures": int(site["captures"]),
                        "first_date": wayback_timestamp(site["first_date"]),
                        "last_date": stamp,
                        "replay_path": replay_url(f"{stamp}mp_", site["entry_url"]),
                    }
                )
            return sites

    @app.get(
        "/replay/{stamp}/{url_path:path}",
        response_class=Response,
        responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
        operation_id="replay_capture",
    )
    def replay_capture(
        stamp: Annotated[str, Path(description="YYYYMMDDHHMMSS with optional id_/mp_")],
        url_path: Annotated[str, Path(description="Archived absolute URL")],
        request: Request,
        policy: Annotated[str, Query(description="closest or exact")] = "closest",
        _: None = Depends(authorize),
    ) -> Response:
        from urllib.parse import parse_qsl, urlencode

        target = url_path
        if target.startswith("http:/") and not target.startswith("http://"):
            target = target.replace("http:/", "http://", 1)
        elif target.startswith("https:/") and not target.startswith("https://"):
            target = target.replace("https:/", "https://", 1)
        archived_query = [
            (key, value)
            for key, value in parse_qsl(request.url.query, keep_blank_values=True)
            if key != "policy"
        ]
        if archived_query:
            target = f"{target}?{urlencode(archived_query)}"
        with Workspace(
            config.db_path, data_dir=config.data_dir, read_only=True, create=False
        ) as ws:
            service = ReplayService(ws, max_payload_bytes=config.max_payload_bytes)
            prepared = service.prepare(target, stamp, policy=policy)
            headers = prepared["headers"]
            content = b""
            if request.method != "HEAD":
                if prepared["stream"]:
                    content = b"".join(service.iter_body(prepared))
                else:
                    content = prepared["body"] or b""
            return Response(
                content=content,
                status_code=prepared["status_code"],
                media_type=prepared["content_type"],
                headers=headers,
            )

    return app


__all__ = ["create_app"]
