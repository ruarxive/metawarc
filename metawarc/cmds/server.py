import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response as StarletteResponse
from structlog.contextvars import bind_contextvars, clear_contextvars

from metawarc import settings
from metawarc.logs import configure_logging, get_logger
from metawarc.routers import warcrouter

log = get_logger("metawarcapi")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    configure_logging(level=settings.LOG_LEVEL)
    log.info("Starting Metawarc API", port=settings.PORT)
    yield
    log.info("Shutting down Metawarc API")


async def request_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> StarletteResponse:
    start_time = time.time()
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    client_ip = request.headers.get('X-Real-IP') or request.headers.get('X-Forwarded-For')

    bind_contextvars(trace_id=trace_id, client_ip=client_ip)
    try:
        response = await call_next(request)
    except Exception as exc:
        log.exception("Exception during request: %s" % type(exc))
        response = JSONResponse(status_code=500, content={"status": "error"})
    time_delta = time.time() - start_time
    response.headers["x-trace-id"] = trace_id
    log.info(
        str(request.url.path),
        action="request",
        method=request.method,
        path=request.url.path,
        query=request.url.query,
        agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
        code=response.status_code,
        took=time_delta,
    )
    clear_contextvars()
    return response


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.TITLE,
        description=settings.DESCRIPTION,
        summary=settings.SUMMARY,
        version=settings.VERSION,
        contact=settings.CONTACT,
        openapi_tags=settings.TAGS,
        openapi_url=settings.OPEN_API_PUBLIC_URL,
        redoc_url=None,
        lifespan=app_lifespan,
    )
    app.middleware("http")(request_middleware)
    app.include_router(warcrouter.router)

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    async def redoc_html(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="redoc.html",
            context={
                "openapi_url": settings.OPEN_API_PUBLIC_URL,
                "title": settings.TITLE + " - ReDoc",
            },
        )

    return app


app = create_app()
