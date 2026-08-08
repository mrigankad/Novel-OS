from typing import Optional

from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    chapter_count: int
    status: str
    author: str = ""
    word_count: int = 0
    drafted_count: int = 0
    content_rating: str = "general"  # general | mature
    updated_at: str | None = None
    genres: list[str] = []
    premise: str = ""
    target_word_count: int = 80000
    session_word_target: int = 1000


class ProjectDetail(BaseModel):
    id: str
    title: str
    genre: str
    author: str
    chapter_count: int
    status: str
    style: dict
    content_rating: str = "general"
    word_count: int = 0
    genres: list[str] = []
    premise: str = ""
    target_word_count: int = 80000
    session_word_target: int = 1000


class UpdateProject(BaseModel):
    content_rating: str | None = None
    title: str | None = None
    genre: str | None = None
    genres: list[str] | None = None
    premise: str | None = None
    target_word_count: int | None = None
    session_word_target: int | None = None


class StudioLlmUpdate(BaseModel):
    preset: str | None = None
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    onboarding_completed: bool | None = None


class StudioLlmStatus(BaseModel):
    configured: bool
    provider: str
    model: str
    preset: str | None = None
    mature_capable: bool = False
    error: str | None = None
    presets: list[dict]
    onboarding_completed: bool = False


class ContinuityFinding(BaseModel):
    severity: str
    category: str
    message: str
    suggestion: str = ""
    chapter: int | None = None
    entity_id: str | None = None
    # Stable identity of the fact, for marking it intentional. Excludes the
    # message and chapter so a dismissal survives rewordings and re-sightings.
    key: str = ""


class ContinuityReport(BaseModel):
    findings: list[ContinuityFinding]
    critical: int = 0
    warning: int = 0
    info: int = 0


class ChapterSummary(BaseModel):
    number: int
    title: str
    status: str
    word_count: int
    pov: str
    target_word_count: int = 2500


class ChapterDetail(ChapterSummary):
    outline: str | None
    draft: str | None


class CharacterSummary(BaseModel):
    id: str
    full_name: str
    role: str
    portrait_media_id: str = ""
    portrait_url: str | None = None


class CodexEntryOut(BaseModel):
    id: str
    entry_type: str
    name: str
    summary: str = ""
    notes: str = ""
    tags: list[str] = []
    portrait_media_id: str = ""
    portrait_url: str | None = None
    role: str = ""
    fields: dict = {}


class SearchHit(BaseModel):
    """Keyword search hit over the project world model + chapter titles."""
    kind: str  # character | location | worldbuilding | item | chapter | relationship
    id: str
    label: str
    subtitle: str = ""
    chapter: int | None = None
    score: int = 0


class CollectionOut(BaseModel):
    id: str
    name: str
    query: str
    kinds: list[str] = []
    notes: str = ""


class CreateCollection(BaseModel):
    name: str = ""
    query: str
    kinds: list[str] = []
    notes: str = ""


class AddCodexEntry(BaseModel):
    entry_type: str
    name: str
    summary: str = ""
    notes: str = ""
    role: str = "supporting"
    tags: list[str] = []


class StyleOut(BaseModel):
    """One named appearance. Typography only - it can never change a word."""
    font: str = "serif"
    size_pt: float = 12.0
    line_height: float = 1.5
    align: str = "left"
    bold: bool = False
    italic: bool = False
    small_caps: bool = False
    first_line_indent_em: float = 0.0
    space_before_em: float = 0.0
    space_after_em: float = 0.0
    page_break_before: bool = False


class StyleSheetOut(BaseModel):
    styles: dict[str, StyleOut] = {}
    scene_break_marker: str = "* * *"


class ChapterActivity(BaseModel):
    """What measurably changed in one chapter - the shape strip's unit."""
    number: int
    title: str = ""
    pov: str = ""
    written: bool = False
    plot_advances: int = 0
    character_development: int = 0
    emotional_beats: int = 0
    new_information: int = 0
    threads_touched: int = 0
    word_count: int = 0
    movement: int = 0
    flat: bool = False


class StallRun(BaseModel):
    start: int
    end: int
    reason: str = ""
    chapters: list[int] = []
    length: int = 0


class BookShape(BaseModel):
    chapters: list[ChapterActivity] = []
    stalls: list[StallRun] = []


class ExemptFinding(BaseModel):
    """Mark a continuity finding intentional. `key` identifies the fact."""
    key: str
    reason: str = ""


class ContinuityExemption(BaseModel):
    key: str
    reason: str = ""
    at: str = ""


class CodexProposal(BaseModel):
    """A candidate Codex entry extracted from prose, awaiting confirmation."""
    name: str
    entry_type: str
    mentions: int
    evidence: str
    chapters: list[int] = []
    excerpt: str = ""


class SetPortrait(BaseModel):
    media_id: str
    entry_type: str = "character"


class RelationshipOut(BaseModel):
    id: str
    source_id: str
    target_id: str
    label: str
    kind: str = "character_character"
    strength: float = 0.5
    status: str = "active"
    since_chapter: int = 0
    notes: str = ""
    directed: bool = False
    source_name: str = ""
    target_name: str = ""


class AddRelationship(BaseModel):
    source_id: str
    target_id: str
    label: str = "unknown"
    notes: str = ""
    directed: bool = False
    since_chapter: int = 0


class StageProvenance(BaseModel):
    """Who produced / reviewed a pipeline stage (PLAN.md P3.2)."""
    produced_by_agent: str = ""
    produced_by_model: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""
    updated_at: str = ""
    word_count: int = 0


class ChapterStages(BaseModel):
    """The pipeline lineage of a chapter: how outline → draft → revised → final."""
    number: int
    status: str
    outline: str | None
    draft: str | None
    revised: str | None
    final: str | None
    continuity: dict | None
    provenance: dict[str, StageProvenance] = {}


class StageDiff(BaseModel):
    """Simple textual diff between two pipeline stages."""
    from_stage: str
    to_stage: str
    from_words: int
    to_words: int
    added_lines: list[str] = []
    removed_lines: list[str] = []
    summary: str = ""


class StageReviewRequest(BaseModel):
    """Accept or reject an AI stage (PLAN.md P3.3)."""
    decision: str  # accept | reject


class StageReviewResult(BaseModel):
    stage: str
    decision: str
    reviewed_by: str = ""
    reviewed_at: str = ""
    promoted_final: bool = False
    message: str = ""


class BinderMoveRequest(BaseModel):
    """Reorder or reparent a binder node (PLAN.md P4)."""
    node_id: str
    parent_id: Optional[str] = None
    index: int = 0


class BinderPatchRequest(BaseModel):
    """Patch binder metadata (corkboard / outliner)."""
    synopsis: Optional[str] = None
    title: Optional[str] = None
    label: Optional[str] = None
    status: Optional[str] = None
    pov: Optional[str] = None
    target_words: Optional[int] = None


class SynopsisRefreshResult(BaseModel):
    chapter: int
    node_id: str
    synopsis: str
    source: str = "architect"  # architect | heuristic
    model: str = ""


class ChapterMetrics(BaseModel):
    chapter: int
    node_id: str = ""
    tension: int
    emotional_intensity: int
    pacing: int
    source: str = "heuristic"
    word_count: int = 0


class OutlinerMetricsRefreshResult(BaseModel):
    chapters: list[ChapterMetrics]
    source: str = "heuristic"


class FinalSave(BaseModel):
    text: str


class FinalResult(BaseModel):
    final: str
    word_count: int


class ContinueParagraph(BaseModel):
    instruction: str


class ContinueResult(BaseModel):
    paragraph: str
    instruction: str
    word_count: int


class ConsequencePreviewRequest(BaseModel):
    """Select a span → rewrite with instruction → preview story ripple."""
    selection: str
    instruction: str
    before_context: str = ""
    after_context: str = ""


class PredictedConsequence(BaseModel):
    """AI-inferred ripple never treat as fact (PLAN.md P3.1)."""
    message: str
    kind: str = "predicted"


class ConsequencePreview(BaseModel):
    preview_id: str
    selection: str
    instruction: str
    rewritten: str
    state_delta: dict = {}
    changelog: list[str] = []
    deterministic: list[ContinuityFinding] = []
    predicted: list[PredictedConsequence] = []
    word_count: int = 0


class ConsequenceAccept(BaseModel):
    """Apply rewrite to Final and world state in one transaction."""
    preview_id: str
    rewritten: str
    doc: dict
    state_delta: dict = {}


class FinalDoc(BaseModel):
    """The Final as a ProseMirror document (PLAN.md P1). `markdown` is the
    projection agents read; it is derived, never edited directly."""
    doc: dict
    markdown: str
    word_count: int


class ConsequenceAcceptResult(BaseModel):
    final: FinalDoc
    changelog: list[str] = []
    continuity: ContinuityReport


class FinalDocSave(BaseModel):
    doc: dict


class CreateProject(BaseModel):
    title: str
    genre: str = ""
    genres: list[str] = []
    premise: str = ""
    author: str = ""


class AddCharacter(BaseModel):
    name: str
    role: str = "supporting"


class RunPhase(BaseModel):
    stage: str
    params: dict = {}


class Job(BaseModel):
    job_id: str
    kind: str
    status: str
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class SnapshotMeta(BaseModel):
    id: str
    label: str
    created_at: str
    word_count: int
    source: str


class SnapshotText(SnapshotMeta):
    text: str


class CreateSnapshot(BaseModel):
    label: str = "Manual"


class Comment(BaseModel):
    id: str
    body: str
    quote: str = ""
    from_pos: Optional[int] = None
    to_pos: Optional[int] = None
    anchor_status: str = "ok"
    persona: str = "author"
    created_at: str
    resolved: bool = False


class AddComment(BaseModel):
    body: str
    quote: str = ""
    from_pos: Optional[int] = None
    to_pos: Optional[int] = None
    persona: str = "author"


class MediaOut(BaseModel):
    id: str
    project_id: str
    filename: str
    content_type: str
    size: int
    width: int
    height: int
    kind: str
    alt: str
    url: str
    created_at: str


class UpdateMedia(BaseModel):
    alt: Optional[str] = None
    kind: Optional[str] = None


class WordFreq(BaseModel):
    word: str
    count: int


class EchoHit(BaseModel):
    word: str
    count: int
    close_pairs: int


class ProjectStatistics(BaseModel):
    word_count: int
    chapter_count: int
    chapters_with_prose: int
    reading_minutes: int
    avg_sentence_length: float
    unique_content_words: int
    top_words: list[WordFreq]
    echoes: list[EchoHit]


class UpdateComment(BaseModel):
    resolved: bool
