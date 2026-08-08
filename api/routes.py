import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from fastapi import Response
from fastapi.responses import PlainTextResponse

from . import db, media as media_lib, richtext
from .jobs import runner
from .models import (
    AddCharacter, AddCodexEntry, AddComment, AddRelationship, ChapterDetail, ChapterStages,
    CodexProposal, ContinuityExemption, ExemptFinding, BookShape, StyleSheetOut,
    ChapterSummary, CharacterSummary, CodexEntryOut, Comment, ConsequenceAccept,
    ConsequenceAcceptResult, ConsequencePreview, ConsequencePreviewRequest, ContinuityReport,
    ContinueParagraph, ContinueResult, CreateProject, CreateSnapshot, FinalDoc, FinalDocSave,
    FinalResult, FinalSave, Job, MediaOut, ProjectDetail, ProjectSummary, RelationshipOut,
    RunPhase, SearchHit, CollectionOut, CreateCollection, SetPortrait, SnapshotMeta, SnapshotText, StageDiff, StageReviewRequest,
    StageReviewResult, StudioLlmStatus, StudioLlmUpdate, UpdateComment, UpdateProject,
    BinderMoveRequest, BinderPatchRequest, SynopsisRefreshResult, UpdateMedia,
    ProjectStatistics, OutlinerMetricsRefreshResult,
)
from .services import (
    BadRequest, ChapterNotFound, NoSourceArtifact, ProjectNotFound, ProjectService,
)

router = APIRouter(prefix="/api")


def get_service() -> ProjectService:
    root = Path(os.environ.get("NOVEL_OS_PROJECTS_DIR", "./projects"))
    return ProjectService(root)


def get_media_store() -> media_lib.MediaStore:
    root = Path(os.environ.get("NOVEL_OS_MEDIA_DIR", "./media"))
    return media_lib.LocalMediaStore(root)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}


@router.get("/studio/llm", response_model=StudioLlmStatus)
def get_studio_llm():
    from core import studio_settings
    return studio_settings.llm_status()


@router.put("/studio/llm", response_model=StudioLlmStatus)
def put_studio_llm(body: StudioLlmUpdate):
    from core import studio_settings
    patch: dict = {}
    if body.preset is not None:
        if body.preset not in studio_settings.PRESETS:
            raise HTTPException(status_code=400, detail=f"Unknown preset '{body.preset}'")
        patch["preset"] = body.preset
    if body.provider is not None:
        patch["NOVEL_OS_LLM_PROVIDER"] = body.provider.strip() or None
    if body.model is not None:
        patch["NOVEL_OS_MODEL"] = body.model.strip() or None
    if body.api_key is not None:
        key = body.api_key.strip()
        patch["NOVEL_OS_API_KEY"] = key or None
        # Also stash on OpenRouter / Anthropic when those presets are used
        if body.preset == "mature" or body.provider == "openrouter":
            patch["OPENROUTER_API_KEY"] = key or None
        if body.preset == "quality" or body.provider == "anthropic":
            patch["ANTHROPIC_API_KEY"] = key or None
        if body.preset == "fast" or body.provider == "openai":
            patch["OPENAI_API_KEY"] = key or None
    if body.base_url is not None:
        patch["NOVEL_OS_BASE_URL"] = body.base_url.strip() or None
    if body.onboarding_completed is not None:
        patch["onboarding_completed"] = body.onboarding_completed
    studio_settings.save_settings(patch)
    return studio_settings.llm_status()


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(svc: ProjectService = Depends(get_service)):
    return svc.list_projects()


@router.patch("/projects/{project_id}", response_model=ProjectDetail)
def update_project(project_id: str, body: UpdateProject, svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_project(
            project_id,
            content_rating=body.content_rating,
            title=body.title,
            genre=body.genre,
            genres=body.genres,
            premise=body.premise,
            target_word_count=body.target_word_count,
            session_word_target=body.session_word_target,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects", response_model=ProjectSummary, status_code=201)
def create_project(body: CreateProject, svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_project(
            body.title, body.genre, body.author,
            genres=body.genres, premise=body.premise,
        )
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/sample", response_model=ProjectSummary, status_code=201)
def create_sample_project(svc: ProjectService = Depends(get_service)):
    """Idempotent first-run sample manuscript with Codex + chapter 1 draft."""
    try:
        return svc.create_sample_project()
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


def _continuity_report(raw: list[dict]) -> ContinuityReport:
    findings = raw
    return ContinuityReport(
        findings=findings,  # type: ignore[arg-type]
        critical=sum(1 for f in findings if f.get("severity") == "critical"),
        warning=sum(1 for f in findings if f.get("severity") == "warning"),
        info=sum(1 for f in findings if f.get("severity") == "info"),
    )


@router.get("/projects/{project_id}/continuity", response_model=ContinuityReport)
def project_continuity(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return _continuity_report(svc.continuity_findings(project_id))
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/shape", response_model=BookShape)
def book_shape(project_id: str, svc: ProjectService = Depends(get_service)):
    """The shape of the book: per-chapter movement and any sagging runs."""
    try:
        return svc.book_shape(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/continuity/exemptions",
            response_model=list[ContinuityExemption])
def list_exemptions(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_exemptions(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/continuity/exemptions",
             response_model=ContinuityExemption, status_code=201)
def exempt_finding(project_id: str, body: ExemptFinding,
                   svc: ProjectService = Depends(get_service)):
    """Mark a finding intentional so it stops being reported to anyone.

    The filter lives in the engine, so the Guardian stops raising it too - the
    AI must not argue with a call the writer has already made.
    """
    try:
        return svc.exempt_finding(project_id, body.key, body.reason)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/continuity/exemptions/{key:path}",
               status_code=204)
def unexempt_finding(project_id: str, key: str,
                     svc: ProjectService = Depends(get_service)):
    try:
        if not svc.unexempt_finding(project_id, key):
            raise HTTPException(status_code=404, detail=f"No exemption for '{key}'")
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/chapters/{number}/continuity", response_model=ContinuityReport)
def chapter_continuity(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        return _continuity_report(svc.continuity_findings(project_id, chapter=number))
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


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


@router.get("/projects/{project_id}/styles", response_model=StyleSheetOut)
def get_styles(project_id: str, svc: ProjectService = Depends(get_service)):
    """Named compile styles (P5.2), with defaults filled in."""
    try:
        return svc.get_styles(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.put("/projects/{project_id}/styles", response_model=StyleSheetOut)
def put_styles(project_id: str, body: StyleSheetOut,
               svc: ProjectService = Depends(get_service)):
    try:
        return svc.save_styles(project_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/compile")
def compile_book(project_id: str, format: str = "html",
                 svc: ProjectService = Depends(get_service)):
    """Compile the whole manuscript through the stylesheet (P6)."""
    try:
        body, content_type, ext = svc.compile_book(project_id, format)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=body,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{project_id}.{ext}"',
        },
    )


@router.get("/projects/{project_id}/statistics", response_model=ProjectStatistics)
def project_statistics(project_id: str, svc: ProjectService = Depends(get_service)):
    """Word frequency, echoes, reading time (PLAN.md P4 Style Curator)."""
    try:
        return ProjectStatistics(**svc.manuscript_statistics(project_id))
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


# ----- Tier 1: snapshots (version history) DB-backed

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


# ----- Tier 1: comments / annotations DB-backed

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

    from_pos, to_pos = body.from_pos, body.to_pos
    anchor_status = "ok"
    # Pre-P1 (and quote-only) notes: try to locate the quote in the Final so the
    # comment becomes text-anchored. Failures are kept, flagged unresolved.
    if (from_pos is None or to_pos is None) and body.quote.strip():
        try:
            doc = svc.get_final_doc(project_id, number)
            span = richtext.find_quote(doc, body.quote)
            if span:
                from_pos, to_pos = span
            else:
                anchor_status = "unresolved"
        except (ProjectNotFound, ChapterNotFound):
            anchor_status = "unresolved"

    return db.comment_add(
        project_id, number, body.body, body.quote,
        from_pos=from_pos, to_pos=to_pos, anchor_status=anchor_status,
        persona=body.persona or "author",
    )


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


@router.get("/projects/{project_id}/binder")
def binder_tree(project_id: str, svc: ProjectService = Depends(get_service)):
    """Nested document tree (PLAN.md P4). Flat chapter endpoints remain the writing path."""
    try:
        return svc.binder_tree(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/binder/move")
def binder_move(
    project_id: str,
    body: BinderMoveRequest,
    svc: ProjectService = Depends(get_service),
):
    """Reorder or reparent a binder node. Does not renumber chapters."""
    if not (body.node_id or "").strip():
        raise HTTPException(status_code=400, detail="node_id is required.")
    try:
        return svc.move_binder_node(
            project_id,
            body.node_id.strip(),
            body.parent_id,
            max(0, int(body.index)),
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/projects/{project_id}/binder/{node_id}")
def binder_patch(
    project_id: str,
    node_id: str,
    body: BinderPatchRequest,
    svc: ProjectService = Depends(get_service),
):
    """Update synopsis / title / label on a binder node (corkboard)."""
    try:
        return svc.patch_binder_node(
            project_id,
            node_id,
            body.model_dump(exclude_unset=True),
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{number}/synopsis/refresh",
    response_model=SynopsisRefreshResult,
)
def refresh_synopsis(
    project_id: str,
    number: int,
    svc: ProjectService = Depends(get_service),
):
    """Architect (or heuristic fallback) refreshes the corkboard synopsis."""
    try:
        return SynopsisRefreshResult(**svc.refresh_synopsis(project_id, number))
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/outliner/metrics/refresh",
    response_model=OutlinerMetricsRefreshResult,
)
def refresh_outliner_metrics(
    project_id: str,
    chapter: int | None = None,
    svc: ProjectService = Depends(get_service),
):
    """Compute tension / emotional intensity / pacing for outliner columns."""
    try:
        return OutlinerMetricsRefreshResult(**svc.refresh_outliner_metrics(project_id, chapter))
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


# --------------------------------------------------------------------------- media

def _media_out(m: db.Media) -> MediaOut:
    return MediaOut(
        id=m.id, project_id=m.project_id, filename=m.filename,
        content_type=m.content_type, size=m.size, width=m.width, height=m.height,
        kind=m.kind, alt=m.alt, url=f"/api/projects/{m.project_id}/media/{m.id}/raw",
        created_at=m.created_at,
    )


def _ensure_project_or_404(svc: ProjectService, project_id: str) -> None:
    try:
        svc.project_detail(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/media", response_model=list[MediaOut])
def list_media(project_id: str, kind: str | None = None,
               svc: ProjectService = Depends(get_service)):
    _ensure_project_or_404(svc, project_id)
    return [_media_out(m) for m in db.media_list(project_id, kind)]


@router.post("/projects/{project_id}/media", response_model=MediaOut, status_code=201)
async def upload_media(project_id: str,
                       file: UploadFile = File(...),
                       kind: str = Form("general"),
                       alt: str = Form(""),
                       svc: ProjectService = Depends(get_service),
                       store: media_lib.MediaStore = Depends(get_media_store)):
    _ensure_project_or_404(svc, project_id)
    data = await file.read()
    try:
        ext = media_lib.validate(data, file.content_type or "")
    except media_lib.MediaError as e:
        raise HTTPException(status_code=e.status, detail=str(e))

    sha = media_lib.digest(data)
    width, height = media_lib.dimensions(data)
    store.put(project_id, sha, ext, data)
    row = db.media_add(
        project_id=project_id, sha=sha, ext=ext,
        filename=media_lib.clean_filename(file.filename or ""),
        content_type=file.content_type or "", size=len(data),
        width=width, height=height, kind=kind, alt=alt,
    )
    return _media_out(row)


@router.get("/projects/{project_id}/media/{media_id}/raw")
def get_media_raw(project_id: str, media_id: str,
                  store: media_lib.MediaStore = Depends(get_media_store)):
    m = db.media_get(project_id, media_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Media not found")
    data = store.read(project_id, m.sha, m.ext)
    if data is None:
        raise HTTPException(status_code=404, detail="Media blob missing")
    # Content-addressed, so the bytes at this id can never change.
    return Response(
        content=data,
        media_type=m.content_type or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.delete("/projects/{project_id}/media/{media_id}", status_code=204)
def delete_media(project_id: str, media_id: str,
                 svc: ProjectService = Depends(get_service),
                 store: media_lib.MediaStore = Depends(get_media_store)):
    _ensure_project_or_404(svc, project_id)
    m = db.media_delete(project_id, media_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Media not found")
    store.delete(project_id, m.sha, m.ext)
    return Response(status_code=204)


@router.patch("/projects/{project_id}/media/{media_id}", response_model=MediaOut)
def patch_media(
    project_id: str,
    media_id: str,
    body: UpdateMedia,
    svc: ProjectService = Depends(get_service),
):
    """Update caption / kind (research moodboard notes)."""
    _ensure_project_or_404(svc, project_id)
    m = db.media_update(
        project_id, media_id,
        alt=body.alt, kind=body.kind,
    )
    if m is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return _media_out(m)


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


@router.get("/projects/{project_id}/codex", response_model=list[CodexEntryOut])
def list_codex(project_id: str, entry_type: str | None = None,
               svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_codex(project_id, entry_type)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/codex/proposals",
            response_model=list[CodexProposal])
def codex_proposals(project_id: str, min_mentions: int = 3, limit: int = 60,
                    svc: ProjectService = Depends(get_service)):
    """Codex candidates found in the manuscript (PLAN.md P2.2).

    Read-only. Accepting one is an ordinary POST to /codex, so nothing here can
    write to the world model without a human deciding to.
    """
    try:
        return svc.codex_proposals(project_id, min_mentions=min_mentions, limit=limit)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/search", response_model=list[SearchHit])
def search_project(project_id: str, q: str = "", limit: int = 24,
                   svc: ProjectService = Depends(get_service)):
    """Keyword search over Codex, chapters, and relationships (no vectors)."""
    try:
        return svc.search(project_id, q, limit=limit)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/collections", response_model=list[CollectionOut])
def list_collections(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_collections(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/collections", response_model=list[CollectionOut], status_code=201)
def create_collection(project_id: str, body: CreateCollection,
                      svc: ProjectService = Depends(get_service)):
    try:
        return svc.add_collection(
            project_id, name=body.name, query=body.query,
            kinds=body.kinds, notes=body.notes,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/collections/{collection_id}", status_code=204)
def delete_collection(project_id: str, collection_id: str,
                      svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_collection(project_id, collection_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/collections/{collection_id}/results", response_model=list[SearchHit])
def collection_results(project_id: str, collection_id: str, limit: int = 40,
                       svc: ProjectService = Depends(get_service)):
    try:
        return svc.collection_results(project_id, collection_id, limit=limit)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/projects/{project_id}/codex", response_model=list[CodexEntryOut], status_code=201)
def add_codex_entry(project_id: str, body: AddCodexEntry,
                    svc: ProjectService = Depends(get_service)):
    try:
        return svc.add_codex_entry(
            project_id, body.entry_type, body.name,
            summary=body.summary, notes=body.notes, role=body.role, tags=body.tags,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/projects/{project_id}/codex/{entry_id}/portrait", response_model=CodexEntryOut)
def set_codex_portrait(project_id: str, entry_id: str, body: SetPortrait,
                       svc: ProjectService = Depends(get_service)):
    try:
        return svc.set_portrait(project_id, entry_id, body.media_id, body.entry_type)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/relationships", response_model=list[RelationshipOut])
def list_relationships(project_id: str, entry_id: str | None = None,
                       svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_relationships(project_id, entry_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/relationships", response_model=list[RelationshipOut], status_code=201)
def add_relationship(project_id: str, body: AddRelationship,
                     svc: ProjectService = Depends(get_service)):
    try:
        return svc.add_relationship(
            project_id, body.source_id, body.target_id, body.label,
            notes=body.notes, directed=body.directed, since_chapter=body.since_chapter,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/relationships/{edge_id}", status_code=204)
def delete_relationship(project_id: str, edge_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_relationship(project_id, edge_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(status_code=204)


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


@router.get(
    "/projects/{project_id}/chapters/{number}/stages/diff",
    response_model=StageDiff,
)
def chapter_stage_diff(
    project_id: str,
    number: int,
    from_stage: str = "draft",
    to_stage: str = "revised",
    svc: ProjectService = Depends(get_service),
):
    """Compare two pipeline stages (P3.2 provenance ribbon)."""
    try:
        return svc.stage_diff(project_id, number, from_stage, to_stage)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{number}/stages/{stage}/review",
    response_model=StageReviewResult,
)
def review_stage(
    project_id: str,
    number: int,
    stage: str,
    body: StageReviewRequest,
    svc: ProjectService = Depends(get_service),
):
    """Accept or reject an AI draft/revised stage (P3.3)."""
    try:
        result = svc.review_stage(project_id, number, stage, body.decision)
        return StageReviewResult(**result)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/{number}/final/promote", response_model=FinalResult)
def promote_final(project_id: str, number: int, force: bool = False,
                  svc: ProjectService = Depends(get_service)):
    try:
        text = svc.promote_final(project_id, number, force=force)
        return FinalResult(final=text, word_count=len(text.split()))
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NoSourceArtifact:
        raise HTTPException(
            status_code=409,
            detail="Nothing to promote no draft or revised text exists yet.",
        )


@router.put("/projects/{project_id}/chapters/{number}/final", response_model=FinalResult)
def save_final(project_id: str, number: int, body: FinalSave,
               svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_final(project_id, number, body.text)
        text = svc.get_final_text(project_id, number) or ""
        return FinalResult(final=text, word_count=wc)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)


@router.post(
    "/projects/{project_id}/chapters/{number}/continue",
    response_model=ContinueResult,
)
def continue_paragraph(project_id: str, number: int, body: ContinueParagraph,
                       svc: ProjectService = Depends(get_service)):
    """Chat: author says what should happen next; Scribe returns one paragraph."""
    try:
        result = svc.continue_paragraph(project_id, number, body.instruction)
        return ContinueResult(**result)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{number}/consequence/preview",
    response_model=ConsequencePreview,
)
def consequence_preview(project_id: str, number: int, body: ConsequencePreviewRequest,
                        svc: ProjectService = Depends(get_service)):
    """Rewrite a selection and preview deterministic + predicted story ripple."""
    try:
        result = svc.preview_consequence(
            project_id, number, body.selection, body.instruction,
            before_context=body.before_context, after_context=body.after_context,
        )
        return ConsequencePreview(**result)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{number}/consequence/accept",
    response_model=ConsequenceAcceptResult,
)
def consequence_accept(project_id: str, number: int, body: ConsequenceAccept,
                       svc: ProjectService = Depends(get_service)):
    """Accept rewrite into Final and apply world-state delta together."""
    try:
        result = svc.accept_consequence(
            project_id, number, body.preview_id, body.rewritten, body.doc,
            state_delta=body.state_delta,
        )
        return ConsequenceAcceptResult(**result)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/chapters/{number}/final/doc", response_model=FinalDoc)
def get_final_doc(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    """Final as a ProseMirror document. Pre-P1 finals convert from markdown on
    read; nothing is rewritten until the writer saves."""
    try:
        d = svc.get_final_doc(project_id, number)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    markdown = richtext.to_markdown(d)
    return FinalDoc(doc=d, markdown=markdown, word_count=richtext.word_count(d))


@router.put("/projects/{project_id}/chapters/{number}/final/doc", response_model=FinalDoc)
def save_final_doc(project_id: str, number: int, body: FinalDocSave,
                   svc: ProjectService = Depends(get_service)):
    try:
        svc.save_final_doc(project_id, number, body.doc)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    markdown = richtext.to_markdown(body.doc)
    return FinalDoc(doc=body.doc, markdown=markdown, word_count=richtext.word_count(body.doc))
