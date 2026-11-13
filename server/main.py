"""Novel OS API.

    uvicorn server.main:app --port 8000 --reload

Every module in server/routers/ that defines `router` is mounted under /api.
"""

from __future__ import annotations

import asyncio
import importlib
import pkgutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from . import auth, events, routers
from .config import settings
from .db import init_db
from .recovery import recover_interrupted

VERSION = "2.0.0"


class _GZipExceptStreams(GZipMiddleware):
    """Gzip responses, but never Server-Sent Events: compression buffers the
    stream, so browsers (which always send Accept-Encoding: gzip) would see nothing."""

    async def __call__(self, scope, receive, send):  # noqa: ANN001
        if scope["type"] == "http" and scope["path"].endswith("/events"):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    recover_interrupted()
    events.bind_loop(asyncio.get_running_loop())
    yield


def _static_routes_first(app: FastAPI) -> None:
    """Routers mount alphabetically, so /codex/{entry_id} could shadow /codex/proposals.
    Within each method, try more literal paths first: fewer {params}, then longer.
    Stable sort keeps the original order for everything else."""
    def key(route) -> tuple[int, int]:
        path = getattr(route, "path", "")
        return (path.count("{"), -len(path.split("{")[0]))
    app.router.routes.sort(key=key)


def create_app() -> FastAPI:
    app = FastAPI(title="Novel OS", version=VERSION, lifespan=lifespan)
    @app.middleware("http")
    async def access_control(request: Request, call_next):
        ok, code, message = auth.allowed(
            request.url.path, request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"), request.cookies.get(auth.COOKIE))
        if not ok:
            return JSONResponse({"detail": message}, status_code=code)
        return await call_next(request)

    app.add_middleware(_GZipExceptStreams, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings().cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for mod in sorted(pkgutil.iter_modules(routers.__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{routers.__name__}.{mod.name}")
        if hasattr(module, "router"):
            app.include_router(module.router, prefix="/api")

    _static_routes_first(app)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": VERSION}

    return app


app = create_app()
