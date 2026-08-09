import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .media import LocalMediaStore
from .routes import router, get_media_store, get_service
from .services import ProjectService


#: Vite's default, and the next port it falls back to when that one is taken -
#: which is exactly when a developer hits an unexplained "Failed to fetch".
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://localhost:5174")


def _cors_origins() -> list[str]:
    """Browser origins allowed to call the API.

    Configurable because the origin was hardcoded to a single dev port: run the
    frontend anywhere else - a second checkout, a LAN address, a port Vite
    picked because 5173 was busy - and every request failed with a CORS error
    that says nothing about CORS.
    """
    raw = os.environ.get("NOVEL_OS_CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


def create_app(projects_root: Optional[Path] = None, db_url: Optional[str] = None,
               media_root: Optional[Path] = None) -> FastAPI:
    db.configure(db_url or os.environ.get("NOVEL_OS_DB") or "sqlite:///./novel_os.db")

    # Apply Studio LLM settings (if any) before first agent job.
    try:
        from core import studio_settings
        studio_settings.apply_to_environ(studio_settings.load_settings())
    except Exception:
        pass

    app = FastAPI(title="Novel OS API", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    if projects_root is not None:
        app.dependency_overrides[get_service] = lambda: ProjectService(projects_root)
    if media_root is not None:
        app.dependency_overrides[get_media_store] = lambda: LocalMediaStore(media_root)
    return app


app = create_app()
