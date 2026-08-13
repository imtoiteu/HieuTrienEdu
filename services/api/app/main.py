"""HieuTrienEducation API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.api.v1.admin.media import MEDIA_ROOT, PUBLIC_PREFIX
from app.core.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("hietedu.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s API (env=%s, db=%s)",
        settings.platform_name,
        settings.environment,
        "sqlite" if settings.is_sqlite else "postgresql",
    )
    yield
    logger.info("Shutting down %s API", settings.platform_name)


app = FastAPI(
    title=f"{settings.platform_name} API",
    description=(
        "Mathematics and Physics learning platform for grades 6-9 — curriculum, adaptive "
        "practice, tutoring and class management."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a JSON error rather than an HTML traceback page.

    The frontend always parses JSON; an HTML 500 makes the client throw a confusing parse error
    that hides the real problem. In debug the message is included, in production it is not.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": str(exc) if settings.debug else "Internal server error",
            "path": request.url.path,
        },
    )


@app.get("/health", tags=["meta"])
def health() -> dict[str, object]:
    """Liveness probe used by Docker Compose and deployment health checks."""
    return {
        "status": "ok",
        "platform": settings.platform_name,
        "environment": settings.environment,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "integrations": {
            "ai_provider": settings.ai_provider,
            "live_class_provider": settings.live_class_provider,
            "payment_provider": settings.payment_provider,
            "storage_provider": settings.storage_provider,
            "geogebra_enabled": settings.geogebra_enabled,
        },
    }


app.include_router(api_router, prefix=settings.api_v1_prefix)


# Serve files uploaded through the admin media library.
#
# Mounted only when no external base URL is configured: with STORAGE_PUBLIC_BASE_URL set, the
# asset URLs point at a CDN or object store and serving the same bytes from the API as well would
# be a second, unversioned copy. The directory is created eagerly so the mount never fails on a
# fresh checkout that has not uploaded anything yet.
if not settings.storage_public_base_url:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount(PUBLIC_PREFIX, StaticFiles(directory=MEDIA_ROOT), name="media")
