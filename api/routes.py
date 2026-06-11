import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from fastapi.responses import PlainTextResponse

from .jobs import runner
from .models import (
    AddCharacter, ChapterDetail, ChapterStages, ChapterSummary, CharacterSummary,
    CreateProject, FinalResult, FinalSave, Job, ProjectDetail, ProjectSummary, RunPhase,
)
from .services import (
    BadRequest, ChapterNotFound, NoSourceArtifact, ProjectNotFound, ProjectService,
)

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


@router.post("/projects", response_model=ProjectSummary, status_code=201)
def create_project(body: CreateProject, svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_project(body.title, body.genre, body.author)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/characters", response_model=list[CharacterSummary], status_code=201)
def add_character(project_id: str, body: AddCharacter, svc: ProjectService = Depends(get_service)):
    try:
        return svc.add_character(project_id, body.name, body.role)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/run", response_model=Job, status_code=202)
def run_phase(project_id: str, body: RunPhase, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_phase_job(project_id, body.stage, body.params)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(body.stage, fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/projects/{project_id}/export", response_class=PlainTextResponse)
def export_markdown(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.export_markdown(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


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


@router.get("/projects/{project_id}/chapters/{number}", response_model=ChapterDetail)
def chapter_detail(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        return svc.chapter_detail(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.get("/projects/{project_id}/characters", response_model=list[CharacterSummary])
def list_characters(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_characters(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/state")
def raw_state(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.raw_state(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


# ----- M2: pipeline stages + editable Final

def _not_found(project_id: str, number: int, e: Exception):
    if isinstance(e, ProjectNotFound):
        return HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.get("/projects/{project_id}/chapters/{number}/stages", response_model=ChapterStages)
def chapter_stages(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        return svc.chapter_stages(project_id, number)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)


@router.post("/projects/{project_id}/chapters/{number}/final/promote", response_model=FinalResult)
def promote_final(project_id: str, number: int, force: bool = False,
                  svc: ProjectService = Depends(get_service)):
    try:
        text = svc.promote_final(project_id, number, force=force)
        return FinalResult(final=text, word_count=len(text.split()))
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except NoSourceArtifact:
        raise HTTPException(
            status_code=409,
            detail="Nothing to promote — no draft or revised text exists yet.",
        )


@router.put("/projects/{project_id}/chapters/{number}/final", response_model=FinalResult)
def save_final(project_id: str, number: int, body: FinalSave,
               svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_final(project_id, number, body.text)
        return FinalResult(final=body.text, word_count=wc)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
