from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router, get_service
from .services import ProjectService


def create_app(projects_root: Optional[Path] = None) -> FastAPI:
    app = FastAPI(title="Novel OS API", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    if projects_root is not None:
        app.dependency_overrides[get_service] = lambda: ProjectService(projects_root)
    return app


app = create_app()
