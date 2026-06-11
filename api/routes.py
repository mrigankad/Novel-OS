import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from fastapi import Response
from fastapi.responses import PlainTextResponse

from . import db
from .jobs import runner
from .models import (
    AddCharacter, AddComment, ChapterDetail, ChapterStages, ChapterSummary, CharacterSummary,
    Comment, CreateProject, CreateSnapshot, FinalResult, FinalSave, Job, ProjectDetail,
    ProjectSummary, RunPhase, SnapshotMeta, SnapshotText, UpdateComment,
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


# ----- Tier 1: snapshots (version history) — DB-backed

def _ensure_chapter_or_404(svc: ProjectService, project_id: str, number: int):
    try:
        svc.ensure_chapter(project_id, number)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)


@router.get("/projects/{project_id}/chapters/{number}/snapshots", response_model=list[SnapshotMeta])
def list_snapshots(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    return db.snapshots_list(project_id, number)


@router.post("/projects/{project_id}/chapters/{number}/snapshots", response_model=SnapshotMeta, status_code=201)
def create_snapshot(project_id: str, number: int, body: CreateSnapshot,
                    svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    text = svc.get_final_text(project_id, number)
    if text is None:
        raise HTTPException(status_code=409, detail="No Final to snapshot yet.")
    return db.snapshot_create(project_id, number, text, body.label, "final")


@router.get("/projects/{project_id}/chapters/{number}/snapshots/{snap_id}", response_model=SnapshotText)
def get_snapshot(project_id: str, number: int, snap_id: str,
                 svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    snap = db.snapshot_get(project_id, number, snap_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@router.post("/projects/{project_id}/chapters/{number}/snapshots/{snap_id}/restore", response_model=FinalResult)
def restore_snapshot(project_id: str, number: int, snap_id: str,
                     svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    snap = db.snapshot_get(project_id, number, snap_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    current = svc.get_final_text(project_id, number)
    if current is not None:
        db.snapshot_create(project_id, number, current, "Before restore", "final")
    wc = svc.save_final(project_id, number, snap.text)
    return FinalResult(final=snap.text, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/snapshots/{snap_id}", status_code=204)
def delete_snapshot(project_id: str, number: int, snap_id: str,
                    svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    if not db.snapshot_delete(project_id, number, snap_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return Response(status_code=204)


# ----- Tier 1: comments / annotations — DB-backed

@router.get("/projects/{project_id}/chapters/{number}/comments", response_model=list[Comment])
def list_comments(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    return db.comments_list(project_id, number)


@router.post("/projects/{project_id}/chapters/{number}/comments", response_model=Comment, status_code=201)
def add_comment(project_id: str, number: int, body: AddComment,
                svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    if not body.body.strip():
        raise HTTPException(status_code=400, detail="Comment body is required.")
    return db.comment_add(project_id, number, body.body, body.quote)


@router.patch("/projects/{project_id}/chapters/{number}/comments/{cid}", response_model=Comment)
def update_comment(project_id: str, number: int, cid: str, body: UpdateComment,
                   svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    c = db.comment_update(project_id, number, cid, body.resolved)
    if c is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return c


@router.delete("/projects/{project_id}/chapters/{number}/comments/{cid}", status_code=204)
def delete_comment(project_id: str, number: int, cid: str,
                   svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    if not db.comment_delete(project_id, number, cid):
        raise HTTPException(status_code=404, detail="Comment not found")
    return Response(status_code=204)


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
