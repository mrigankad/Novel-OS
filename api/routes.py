import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .models import ChapterSummary, ProjectDetail, ProjectSummary
from .services import ProjectNotFound, ProjectService

router = APIRouter(prefix="/api")


def get_service() -> ProjectService:
    root = Path(os.environ.get("NOVEL_OS_PROJECTS_DIR", "./projects"))
    return ProjectService(root)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(svc: ProjectService = Depends(get_service)):
    return svc.list_projects()


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def project_detail(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.project_detail(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterSummary])
def list_chapters(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_chapters(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
