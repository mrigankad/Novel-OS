import os
import subprocess
import sys
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from fastapi import Response
from fastapi.responses import PlainTextResponse

from . import db
from .jobs import runner
from .models import (
    AddCharacter, AddComment, ChapterDetail, ChapterPasteResult, ChapterStages, ChapterSummary,
    CharacterDetail, CharacterGeneratePreview, CharacterSummary, Comment, CreateChapter,
    CreatePlotThread, CreateProject, GenerateCharacter,
    CreateSnapshot, DraftResult, DraftSave, RevisedResult, RevisedSave, FinalResult, FinalSave, UnfinalizeResult, ImportStory, Job,
    PasteChapter, PlotThreadSummary, ProjectDetail, ProjectSummary, ReassignChapter,
    ReassignChapterResult, RunPhase, SnapshotMeta,
    SnapshotText,     StoryBible, UpdateChapter, UpdateCharacter, UpdateComment, UpdatePlotThread,
    UpdateStoryBible, ExtractBackground, ExtractBackgroundResult,
    RegenerateChapter, RegeneratePreview, RegenerateApply, RegenerateApplyResult,
    DuplicateGroupModel, DuplicatesReport, EntityDedupStatus, MergeEntities, MergeResult, AutoResolveResult,
    BibleDuplicatesReport, BibleDedupeMerge, BibleAutoDedupeResult, BibleDedupStatus,
    BackupsReport, BackupActionResult, CreateNamedBackup, NamedBackupMeta, ReorderPlotThreads,
    NestPlotThreads, SystemPromptSettings, LlmQueueEntry, RunningJobEntry, LlmQueueSettings, LlmQueueSettingsUpdate, LlmQueueFlushResult, LlmQueueReorder, LlmQueueMove,
    RestartResult,
    PlotPanelIssuesReport, ResolvePlotPanelIssue, PlotPanelResolveResult, PlotPanelAutoResolveResult,
    GeneratePlotThread, PlotGeneratePreview,
)
from .services import (
    BadRequest, ChapterNotFound, CharacterNotFound, NoSourceArtifact, NothingToUnfinalize,
    PlotThreadNotFound, ProjectNotFound, ProjectService,
)

router = APIRouter(prefix="/api")
_CORE = Path(__file__).resolve().parent.parent / "core"


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


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_project(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


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


@router.post("/import", response_model=Job, status_code=202)
def import_story(body: ImportStory, svc: ProjectService = Depends(get_service)):
    """Import .txt chapters from a local folder into a new or existing project."""
    try:
        fn, project_id = svc.make_import_job(
            body.chapters_dir,
            title=body.title,
            genre=body.genre,
            author=body.author,
            project_id=body.project_id,
            synthesize=body.synthesize,
            no_extract=body.no_extract,
            from_chapter=body.from_chapter,
            to_chapter=body.to_chapter,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{body.project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("import", fn, meta={"project_id": project_id})
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


@router.get("/projects/{project_id}/export-package")
def export_project_package(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        filename, data = svc.export_project_package(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/projects/import-package", response_model=ProjectSummary, status_code=201)
async def import_project_package(
    request: Request,
    svc: ProjectService = Depends(get_service),
):
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Empty request body.")
    try:
        return svc.import_project_package(content)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.delete("/projects/{project_id}/chapters/{number}", status_code=204)
def delete_chapter(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_chapter(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/characters", response_model=list[CharacterSummary])
def list_characters(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_characters(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.delete("/projects/{project_id}/characters/{character_id}", status_code=204)
def delete_character(project_id: str, character_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_character(project_id, character_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/plot-threads", response_model=list[PlotThreadSummary])
def list_plot_threads(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_plot_threads(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.delete("/projects/{project_id}/plot-threads/{thread_id}", status_code=204)
def delete_plot_thread(project_id: str, thread_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_plot_thread(project_id, thread_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except PlotThreadNotFound:
        raise HTTPException(status_code=404, detail=f"Plot thread '{thread_id}' not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/characters/{character_id}", response_model=CharacterDetail)
def get_character(project_id: str, character_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_character(project_id, character_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.patch("/projects/{project_id}/characters/{character_id}", response_model=CharacterDetail)
def update_character(project_id: str, character_id: str, body: UpdateCharacter,
                     svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_character(project_id, character_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.post("/projects/{project_id}/characters/generate", response_model=Job, status_code=202)
def generate_character_profile(project_id: str, body: GenerateCharacter,
                               svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_character_generate_job(
            project_id,
            body.prompt,
            character_id=body.character_id,
            hint_name=body.hint_name,
            hint_role=body.hint_role,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{body.character_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "character_generate",
        fn,
        meta={"project_id": project_id, "character_id": body.character_id},
    )
    return runner.get(job_id)


@router.get("/projects/{project_id}/characters/generate/preview",
            response_model=CharacterGeneratePreview)
def get_character_generate_preview(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_character_generate_preview(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No character generate preview")
    return preview


@router.delete("/projects/{project_id}/characters/generate/preview", status_code=204)
def discard_character_generate_preview(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_character_generate_preview(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


@router.put("/projects/{project_id}/plot-threads/reorder", response_model=list[PlotThreadSummary])
def reorder_plot_threads(project_id: str, body: ReorderPlotThreads,
                         svc: ProjectService = Depends(get_service)):
    try:
        return svc.reorder_plot_threads(project_id, body.ordered_ids)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/plot-threads", response_model=PlotThreadSummary, status_code=201)
def create_plot_thread(project_id: str, body: CreatePlotThread, svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_plot_thread(
            project_id, body.name, body.description, body.thread_type, body.priority, body.status,
            subplots=body.subplots,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/projects/{project_id}/plot-threads/{thread_id}", response_model=PlotThreadSummary)
def update_plot_thread(project_id: str, thread_id: str, body: UpdatePlotThread,
                       svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_plot_thread(project_id, thread_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except PlotThreadNotFound:
        raise HTTPException(status_code=404, detail=f"Plot thread '{thread_id}' not found")


@router.get("/projects/{project_id}/plot-threads/panel-issues", response_model=PlotPanelIssuesReport)
def list_plot_panel_issues(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_plot_panel_issues(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/plot-threads/panel-issues/resolve",
             response_model=PlotPanelResolveResult)
def resolve_plot_panel_issue(project_id: str, body: ResolvePlotPanelIssue,
                             svc: ProjectService = Depends(get_service)):
    try:
        return svc.resolve_plot_panel_issue(project_id, body.issue_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/plot-threads/panel-issues/auto-resolve",
             response_model=PlotPanelAutoResolveResult)
def auto_resolve_plot_panel_issues(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.auto_resolve_plot_panel_issues(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/plot-threads/{thread_id}/generate", response_model=Job,
             status_code=202)
def generate_plot_thread(project_id: str, thread_id: str, body: GeneratePlotThread,
                         svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_plot_generate_job(project_id, thread_id, body.prompt)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except PlotThreadNotFound:
        raise HTTPException(status_code=404, detail=f"Plot thread '{thread_id}' not found")
    job_id = runner.submit(
        "plot_generate",
        fn,
        meta={"project_id": project_id, "thread_id": thread_id},
    )
    return runner.get(job_id)


@router.get("/projects/{project_id}/plot-threads/{thread_id}/generate/preview",
            response_model=PlotGeneratePreview)
def get_plot_generate_preview(project_id: str, thread_id: str,
                              svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_plot_generate_preview(project_id, thread_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No plot generate preview")
    return preview


@router.delete("/projects/{project_id}/plot-threads/{thread_id}/generate/preview", status_code=204)
def discard_plot_generate_preview(project_id: str, thread_id: str,
                                  svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_plot_generate_preview(project_id, thread_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/story-bible", response_model=StoryBible)
def get_story_bible(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return StoryBible(data=svc.get_story_bible(project_id))
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.patch("/projects/{project_id}/story-bible", response_model=StoryBible)
def update_story_bible(project_id: str, body: UpdateStoryBible, svc: ProjectService = Depends(get_service)):
    try:
        data = svc.update_story_bible_section(project_id, body.section, body.content)
        return StoryBible(data=data)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/story-bible/duplicates/status", response_model=BibleDedupStatus)
def bible_dedup_status(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_bible_dedup_status(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/story-bible/duplicates", response_model=BibleDuplicatesReport)
def list_bible_duplicates(project_id: str, ai: bool = False, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_bible_duplicates(project_id, prefer_ai=ai)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/story-bible/duplicates/ai-scan", response_model=Job, status_code=202)
def ai_scan_bible_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_bible_ai_dedup_job(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    job_id = runner.submit("bible_dedup_ai", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/projects/{project_id}/story-bible/duplicates/auto-resolve", response_model=BibleAutoDedupeResult)
def auto_resolve_bible_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.auto_dedupe_bible(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/story-bible/duplicates/merge", response_model=BibleAutoDedupeResult)
def merge_bible_duplicates(project_id: str, body: BibleDedupeMerge, svc: ProjectService = Depends(get_service)):
    try:
        return svc.merge_bible_duplicates(project_id, body)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/extract-background", response_model=Job, status_code=202)
def extract_background(project_id: str, body: ExtractBackground,
                       svc: ProjectService = Depends(get_service)):
    """Run Lorekeeper on a background/worldbuilding text block (story-level extraction)."""
    try:
        fn = svc.make_background_extract_job(project_id, body.text, body.label)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("extract_background", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/projects/{project_id}/chapters")
def create_chapter(project_id: str, body: CreateChapter, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.create_chapter(
            project_id, body.number, body.title, body.text, body.extract,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(result, tuple):
        fn, pid, num = result
        job_id = runner.submit("extract", fn, meta={"project_id": pid, "chapter": num})
        return runner.get(job_id)
    return result


@router.patch("/projects/{project_id}/chapters/{number}", response_model=ChapterSummary)
def update_chapter(project_id: str, number: int, body: UpdateChapter,
                   svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_chapter(project_id, number, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.post("/projects/{project_id}/chapters/{number}/reassign", response_model=ReassignChapterResult)
def reassign_chapter(project_id: str, number: int, body: ReassignChapter,
                     svc: ProjectService = Depends(get_service)):
    try:
        return svc.reassign_chapter(project_id, number, body.to_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/{number}/paste")
def paste_chapter(project_id: str, number: int, body: PasteChapter,
                  svc: ProjectService = Depends(get_service)):
    try:
        result = svc.paste_chapter(project_id, number, body.text, body.title, body.extract)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(result, tuple):
        fn, pid, num = result
        job_id = runner.submit("extract", fn, meta={"project_id": pid, "chapter": num})
        return runner.get(job_id)
    return result


@router.put("/projects/{project_id}/chapters/{number}/draft", response_model=DraftResult)
def save_draft(project_id: str, number: int, body: DraftSave,
               svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_draft(project_id, number, body.text)
        return DraftResult(draft=body.text, word_count=wc)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.put("/projects/{project_id}/chapters/{number}/revised", response_model=RevisedResult)
def save_revised(project_id: str, number: int, body: RevisedSave,
                 svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_revised(project_id, number, body.text)
        return RevisedResult(revised=body.text, word_count=wc)
    except (ProjectNotFound, ChapterNotFound) as e:
        if isinstance(e, ProjectNotFound):
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.post("/projects/{project_id}/chapters/{number}/extract", response_model=Job, status_code=202)
def extract_chapter(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_extract_job(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("extract", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.post("/projects/{project_id}/chapters/{number}/mine/{kind}", response_model=Job, status_code=202)
def mine_chapter(
    project_id: str,
    number: int,
    kind: str,
    source: str = "draft",
    svc: ProjectService = Depends(get_service),
):
    """Mine chapter prose for plots, characters, or story bible (focused extract)."""
    try:
        fn = svc.make_mine_job(project_id, number, kind, source=source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(f"mine_{kind}", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.post("/projects/{project_id}/chapters/{number}/regenerate", response_model=Job, status_code=202)
def regenerate_chapter(project_id: str, number: int, body: RegenerateChapter,
                       svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_regenerate_job(
            project_id, number, source=body.source, instructions=body.instructions,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except (BadRequest, ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("regenerate", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/regenerate/preview",
            response_model=RegeneratePreview)
def get_regenerate_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_regenerate_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No regenerate preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/regenerate/apply",
             response_model=RegenerateApplyResult)
def apply_regenerate_preview(project_id: str, number: int, body: RegenerateApply,
                             svc: ProjectService = Depends(get_service)):
    try:
        target, wc = svc.apply_regenerate_preview(
            project_id, number, body.text, target=body.target,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target=target, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/regenerate/preview", status_code=204)
def discard_regenerate_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_regenerate_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/expand-placeholders", response_model=Job, status_code=202)
def expand_placeholders(project_id: str, number: int, body: RegenerateChapter,
                        svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_expand_job(
            project_id, number, source=body.source, instructions=body.instructions,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("expand_placeholders", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/expand/preview",
            response_model=RegeneratePreview)
def get_expand_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_expand_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No expand preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/expand/apply",
             response_model=RegenerateApplyResult)
def apply_expand_preview(project_id: str, number: int, body: RegenerateApply,
                         svc: ProjectService = Depends(get_service)):
    try:
        target, wc = svc.apply_expand_preview(
            project_id, number, body.text, target=body.target,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target=target, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/expand/preview", status_code=204)
def discard_expand_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_expand_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/generate-outline", response_model=Job, status_code=202)
def generate_outline_from_text(project_id: str, number: int, body: RegenerateChapter,
                             svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_generate_outline_job(
            project_id, number, source=body.source, instructions=body.instructions,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except (BadRequest, ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("generate_outline", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/generate-outline/preview",
             response_model=RegeneratePreview)
def get_outline_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_outline_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No outline preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/generate-outline/apply",
             response_model=RegenerateApplyResult)
def apply_outline_preview(project_id: str, number: int, body: RegenerateApply,
                          svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.apply_outline_preview(project_id, number, body.text)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target="outline", word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/generate-outline/preview", status_code=204)
def discard_outline_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_outline_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/duplicates/status", response_model=EntityDedupStatus)
def duplicates_status(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_duplicates_status(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/duplicates", response_model=DuplicatesReport)
def list_duplicates(project_id: str, ai: bool = False, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_duplicates(project_id, prefer_ai=ai)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/duplicates/ai-scan", response_model=Job, status_code=202)
def ai_scan_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_ai_duplicate_scan_job(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    job_id = runner.submit("dedup_ai", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/projects/{project_id}/duplicates/auto-resolve", response_model=AutoResolveResult)
def auto_resolve_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.auto_resolve_duplicates(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/plot-threads/nest", response_model=MergeResult)
def nest_plot_threads(project_id: str, body: NestPlotThreads, svc: ProjectService = Depends(get_service)):
    try:
        return svc.nest_plot_threads(project_id, body.parent_id, body.child_ids)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/duplicates/merge", response_model=MergeResult)
def merge_duplicate_entities(project_id: str, body: MergeEntities, svc: ProjectService = Depends(get_service)):
    try:
        return svc.merge_entities(
            project_id, body.kind, body.keep_id, body.merge_ids,
            mode=body.mode, label_override=body.label_override,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/duplicates/ai-suggestions", status_code=204)
def clear_ai_duplicate_suggestions(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.clear_ai_duplicate_suggestions(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


# ----- Project backups (full story state)

@router.get("/projects/{project_id}/backups", response_model=BackupsReport)
def list_project_backups(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_backups(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/backups", response_model=NamedBackupMeta, status_code=201)
def create_project_backup(project_id: str, body: CreateNamedBackup,
                          svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_named_backup(project_id, body.label)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/backups/{backup_id}/restore", response_model=BackupActionResult)
def restore_project_backup(project_id: str, backup_id: str, svc: ProjectService = Depends(get_service)):
    try:
        entry = svc.restore_named_backup(project_id, backup_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(message=f"Restored backup: {entry.get('label', backup_id)}")


@router.delete("/projects/{project_id}/backups/{backup_id}", status_code=204)
def delete_project_backup(project_id: str, backup_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_named_backup(project_id, backup_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(status_code=204)


@router.post("/projects/{project_id}/backups/quick-save", response_model=BackupActionResult)
def quick_save_project_backup(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.quick_save_backup(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(
        message="Quick save complete",
        quick=result.get("quick"),
    )


@router.post("/projects/{project_id}/backups/quick-restore", response_model=BackupActionResult)
def quick_restore_project_backup(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.quick_restore_backup(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(
        message="Restored from quick save (current state saved as pre-restore snapshot)",
        quick=result.get("quick"),
    )


@router.post("/projects/{project_id}/backups/undo-restore", response_model=BackupActionResult)
def undo_project_backup_restore(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.undo_backup_restore(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(
        message="Undid restore — reverted to pre-restore snapshot",
        quick=result.get("quick"),
    )


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


@router.post("/projects/{project_id}/chapters/{number}/final/unfinalize", response_model=UnfinalizeResult)
def unfinalize_chapter(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        stages = svc.unfinalize_chapter(project_id, number)
        ch = svc.chapter_detail(project_id, number)
        return UnfinalizeResult(
            number=stages.number,
            status=stages.status,
            outline=stages.outline,
            draft=stages.draft,
            revised=stages.revised,
            final=stages.final,
            word_count=ch.word_count,
        )
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except NothingToUnfinalize:
        raise HTTPException(
            status_code=409,
            detail="Nothing to reopen — chapter is not validated, approved, or finalized.",
        )


# ----- Install settings (global, not per-project)

@router.get("/settings/system-prompt", response_model=SystemPromptSettings)
def get_system_prompt_settings():
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import read_global_system_prefix  # noqa: WPS433

    agents = Path(__file__).resolve().parent.parent / "agents"
    return SystemPromptSettings(
        prefix=read_global_system_prefix(),
        agents_dir=str(agents),
    )


@router.put("/settings/system-prompt", response_model=SystemPromptSettings)
def put_system_prompt_settings(body: SystemPromptSettings):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import write_global_system_prefix, read_global_system_prefix  # noqa: WPS433

    write_global_system_prefix(body.prefix)
    agents = Path(__file__).resolve().parent.parent / "agents"
    return SystemPromptSettings(prefix=read_global_system_prefix(), agents_dir=str(agents))


def _llm_queue_settings() -> LlmQueueSettings:
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    s = get_llm_queue().status()
    running = runner.list_running()
    return LlmQueueSettings(
        max_concurrent=int(s["max_concurrent"]),
        active=int(s["active"]),
        queued=int(s["queued"]),
        flushed=bool(s["flushed"]),
        active_items=[LlmQueueEntry(**e) for e in s.get("active_items") or []],
        queued_items=[LlmQueueEntry(**e) for e in s.get("queued_items") or []],
        running_jobs=[RunningJobEntry(**j) for j in running],
    )


@router.get("/settings/llm-queue", response_model=LlmQueueSettings)
def get_llm_queue_settings():
    return _llm_queue_settings()


@router.put("/settings/llm-queue", response_model=LlmQueueSettings)
def put_llm_queue_settings(body: LlmQueueSettingsUpdate):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import write_max_concurrent_llm  # noqa: WPS433
    from llm_queue import configure_llm_queue  # noqa: WPS433

    n = write_max_concurrent_llm(body.max_concurrent)
    configure_llm_queue(n)
    return _llm_queue_settings()


@router.post("/settings/llm-queue/reorder", response_model=LlmQueueSettings)
def reorder_llm_queue(body: LlmQueueReorder):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    try:
        get_llm_queue().reorder_queued(body.order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _llm_queue_settings()


@router.post("/settings/llm-queue/{entry_id}/move", response_model=LlmQueueSettings)
def move_llm_queue_entry(entry_id: str, body: LlmQueueMove):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    try:
        get_llm_queue().move_queued(entry_id, body.position)
    except KeyError:
        raise HTTPException(status_code=404, detail="Queued entry not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _llm_queue_settings()


@router.delete("/settings/llm-queue/{entry_id}", response_model=LlmQueueSettings)
def cancel_llm_queue_entry(entry_id: str):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    try:
        get_llm_queue().cancel_queued(entry_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Queued entry not found") from None
    return _llm_queue_settings()


def _flush_llm_work(reason: str) -> LlmQueueFlushResult:
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import flush_llm_queue  # noqa: WPS433

    cancelled_jobs = runner.flush(reason)
    queue_status = flush_llm_queue(reason)
    return LlmQueueFlushResult(
        cancelled_jobs=cancelled_jobs,
        queue=LlmQueueSettings(
            max_concurrent=int(queue_status["max_concurrent"]),
            active=int(queue_status["active"]),
            queued=int(queue_status["queued"]),
            flushed=bool(queue_status["flushed"]),
            active_items=[LlmQueueEntry(**e) for e in queue_status.get("active_items") or []],
            queued_items=[LlmQueueEntry(**e) for e in queue_status.get("queued_items") or []],
            running_jobs=[RunningJobEntry(**j) for j in runner.list_running()],
        ),
        message=reason,
    )


@router.post("/settings/llm-queue/flush", response_model=LlmQueueFlushResult)
def flush_llm_queue_endpoint():
    return _flush_llm_work("Queue flushed")


@router.post("/system/restart", response_model=RestartResult)
def restart_novel_os():
    _flush_llm_work("Cancelled by restart")
    install = Path(os.environ.get("NOVEL_OS_HOME", Path.home() / ".local/share/novel-os"))
    script = install / "bin" / "novel-os-restart.sh"
    if not script.is_file():
        raise HTTPException(status_code=500, detail=f"Restart script not found: {script}")
    subprocess.Popen(  # noqa: S603
        ["/bin/bash", str(script)],
        cwd=str(install),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return RestartResult(
        status="restarting",
        message="Restarting Novel OS — queued LLM requests cancelled and in-flight API calls stopped.",
    )
