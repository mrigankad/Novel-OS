from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    chapter_count: int
    status: str


class ChapterSummary(BaseModel):
    number: int
    title: str
    status: str
    word_count: int
    pov: str
    pipeline_step: str = "none"  # none | drafted | revised | validated | approved | final


class ChapterDetail(ChapterSummary):
    outline: str | None
    draft: str | None


class CharacterSummary(BaseModel):
    id: str
    full_name: str
    role: str
    aliases: list[str] = []


class PlotThreadSummary(BaseModel):
    id: str
    name: str
    description: str
    thread_type: str
    status: str
    priority: int
    sort_order: int = 0
    subplots: list[str] = []


class ProjectDetail(BaseModel):
    id: str
    title: str
    genre: str
    author: str
    chapter_count: int
    status: str
    style: dict


class ChapterStages(BaseModel):
    """The pipeline lineage of a chapter: how outline → draft → revised → final."""
    number: int
    status: str
    outline: str | None
    draft: str | None
    revised: str | None
    final: str | None
    continuity: dict | None


class FinalSave(BaseModel):
    text: str


class FinalResult(BaseModel):
    final: str
    word_count: int


class UnfinalizeResult(BaseModel):
    """Chapter reopened for revision — final removed, validate/approve cleared."""
    number: int
    status: str
    outline: str | None
    draft: str | None
    revised: str | None
    final: str | None
    word_count: int


class CreateProject(BaseModel):
    title: str
    genre: str = ""
    author: str = ""


class AddCharacter(BaseModel):
    name: str
    role: str = "supporting"


class GenerateCharacter(BaseModel):
    prompt: str
    character_id: str | None = None
    hint_name: str = ""
    hint_role: str = ""


class CharacterGeneratePreview(BaseModel):
    character_id: str | None = None
    prompt: str
    hint_name: str = ""
    hint_role: str = ""
    updates: dict
    generated_at: str | None = None


class RunPhase(BaseModel):
    stage: str
    params: dict = {}


class SystemPromptSettings(BaseModel):
    prefix: str = ""
    agents_dir: str = ""


class LlmQueueEntry(BaseModel):
    id: str
    label: str
    submitted_at: str
    chapter: int | None = None
    project_id: str | None = None
    function: str | None = None


class LlmQueueReorder(BaseModel):
    order: list[str]


class LlmQueueMove(BaseModel):
    position: str  # first | last


class RunningJobEntry(BaseModel):
    job_id: str
    kind: str
    label: str
    started_at: str
    project_id: str | None = None
    chapter: int | None = None
    screen: str = "App"


class LlmQueueSettings(BaseModel):
    max_concurrent: int = 2
    active: int = 0
    queued: int = 0
    flushed: bool = False
    active_items: list[LlmQueueEntry] = []
    queued_items: list[LlmQueueEntry] = []
    running_jobs: list[RunningJobEntry] = []


class LlmQueueSettingsUpdate(BaseModel):
    max_concurrent: int


class LlmQueueFlushResult(BaseModel):
    cancelled_jobs: int
    queue: LlmQueueSettings
    message: str


class RestartResult(BaseModel):
    status: str
    message: str


class ImportStory(BaseModel):
    chapters_dir: str
    title: str = ""
    genre: str = ""
    author: str = ""
    project_id: str = ""
    synthesize: bool = True
    no_extract: bool = False
    from_chapter: int | None = None
    to_chapter: int | None = None


class Job(BaseModel):
    job_id: str
    kind: str
    status: str
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    project_id: str | None = None


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
    created_at: str
    resolved: bool = False


class AddComment(BaseModel):
    body: str
    quote: str = ""


class UpdateComment(BaseModel):
    resolved: bool


class CreateChapter(BaseModel):
    number: int
    title: str = ""
    text: str = ""
    extract: bool = False


class UpdateChapter(BaseModel):
    title: str | None = None
    status: str | None = None
    pov_character: str | None = None
    location: str | None = None
    time: str | None = None


class ReassignChapter(BaseModel):
    to_number: int


class ReassignChapterResult(BaseModel):
    action: str
    from_number: int
    to_number: int
    chapter: ChapterSummary
    swapped_with: ChapterSummary | None = None


class PasteChapter(BaseModel):
    text: str
    title: str = ""
    extract: bool = False


class DraftSave(BaseModel):
    text: str


class DraftResult(BaseModel):
    draft: str
    word_count: int


class RevisedSave(BaseModel):
    text: str


class RevisedResult(BaseModel):
    revised: str
    word_count: int


class ChapterPasteResult(BaseModel):
    number: int
    word_count: int
    changes: list[str] = []


class CharacterDetail(BaseModel):
    id: str
    full_name: str
    role: str
    age: int | None = None
    physical_description: str = ""
    internal_desire: str = ""
    external_goal: str = ""
    fear: str = ""
    weakness: str = ""
    strength: str = ""
    secret: str = ""
    arc_stage: str = "beginning"
    arc_progress: int = 0
    current_location: str = ""
    emotional_state: str = ""
    notes: str = ""
    aliases: list[str] = []
    last_appearance_chapter: int = 0


class UpdateCharacter(BaseModel):
    full_name: str | None = None
    role: str | None = None
    age: int | None = None
    physical_description: str | None = None
    internal_desire: str | None = None
    external_goal: str | None = None
    fear: str | None = None
    weakness: str | None = None
    strength: str | None = None
    secret: str | None = None
    arc_stage: str | None = None
    arc_progress: int | None = None
    current_location: str | None = None
    emotional_state: str | None = None
    notes: str | None = None
    aliases: list[str] | None = None
    last_appearance_chapter: int | None = None


class CreatePlotThread(BaseModel):
    name: str
    description: str = ""
    thread_type: str = "main"
    priority: int = 3
    status: str = "active"
    subplots: list[str] = []


class UpdatePlotThread(BaseModel):
    name: str | None = None
    description: str | None = None
    thread_type: str | None = None
    priority: int | None = None
    status: str | None = None
    subplots: list[str] | None = None


class NestPlotThreads(BaseModel):
    parent_id: str
    child_ids: list[str]


class ReorderPlotThreads(BaseModel):
    ordered_ids: list[str]


class StoryBible(BaseModel):
    data: dict


class UpdateStoryBible(BaseModel):
    section: str
    content: str | list | dict


class ExtractBackground(BaseModel):
    text: str
    label: str = "Background"


class ExtractBackgroundResult(BaseModel):
    label: str
    changes: list[str]
    characters: int
    plot_threads: int


class RegenerateChapter(BaseModel):
    source: str = "draft"  # draft | revised | final
    instructions: str = ""


class RegeneratePreview(BaseModel):
    text: str
    source: str
    original_word_count: int
    preview_word_count: int
    generated_at: str | None = None
    instructions: str = ""
    placeholder_count: int | None = None


class RegenerateApply(BaseModel):
    text: str
    target: str | None = None  # defaults to source stage from preview meta


class RegenerateApplyResult(BaseModel):
    target: str
    word_count: int


class DuplicateMember(BaseModel):
    id: str
    label: str
    role: str | None = None
    thread_type: str | None = None


class DuplicateGroupModel(BaseModel):
    kind: str
    confidence: float
    reason: str
    suggested_keep_id: str
    members: list[DuplicateMember]


class DuplicatesReport(BaseModel):
    characters: list[DuplicateGroupModel]
    plot_threads: list[DuplicateGroupModel]
    source: str = "heuristic"
    ai_scan_completed: bool = False
    scanned_at: str | None = None


class PlotPanelLocation(BaseModel):
    parent_id: str
    parent_name: str
    index: int
    line: str


class PlotPanelIssueModel(BaseModel):
    issue_id: str
    kind: str
    confidence: float
    reason: str
    subplot_line: str
    locations: list[PlotPanelLocation]
    thread_id: str | None = None
    thread_name: str | None = None
    suggested_parent_id: str = ""
    suggested_parent_name: str = ""
    suggested_action: str = "remove_duplicates"


class PlotPanelIssuesReport(BaseModel):
    issues: list[PlotPanelIssueModel]
    source: str = "heuristic"


class ResolvePlotPanelIssue(BaseModel):
    issue_id: str


class PlotPanelResolveResult(BaseModel):
    issue_id: str
    log: list[str]


class PlotPanelAutoResolveResult(BaseModel):
    resolved: int
    log: list[str]


class GeneratePlotThread(BaseModel):
    thread_id: str
    prompt: str = ""


class PlotGeneratePreview(BaseModel):
    thread_id: str
    thread_name: str
    prompt: str
    description: str
    previous_description: str
    bible_suggestions: list[str]
    generated_at: str | None = None


class MergeEntities(BaseModel):
    kind: str  # character | plot_thread
    keep_id: str
    merge_ids: list[str]
    mode: str = "parallel"  # parallel | nest (plot_thread only)
    label_override: str = ""


class MergeResult(BaseModel):
    kind: str
    keep_id: str
    merged: list[str]
    log: list[str]
    mode: str = "parallel"
    keep_label: str = ""


class AutoResolveResult(BaseModel):
    merged_characters: int
    merged_plot_threads: int
    log: list[str]


class BibleDuplicateMember(BaseModel):
    id: str
    section: str
    index: int
    label: str


class BibleDuplicateGroupModel(BaseModel):
    section: str
    confidence: float
    reason: str
    suggested_keep_index: int
    members: list[BibleDuplicateMember]


class BibleDuplicatesReport(BaseModel):
    groups: list[BibleDuplicateGroupModel]
    source: str = "heuristic"


class BibleDedupeMerge(BaseModel):
    keep_section: str
    keep_index: int
    members: list[BibleDuplicateMember]
    text_override: str = ""


class BibleAutoDedupeResult(BaseModel):
    removed: int
    log: list[str]
    keep_text: str = ""


class BibleDedupStatus(BaseModel):
    ai_suggestions_ready: bool
    ai_group_count: int


class EntityDedupStatus(BaseModel):
    ai_suggestions_ready: bool
    ai_group_count: int
    has_ai_file: bool = False
    ai_scan_completed: bool = False
    character_group_count: int = 0
    plot_thread_group_count: int = 0


class QuickSlotMeta(BaseModel):
    created_at: str
    size_bytes: int


class QuickBackupMeta(BaseModel):
    current: QuickSlotMeta | None = None
    previous: QuickSlotMeta | None = None
    pre_restore: QuickSlotMeta | None = None


class NamedBackupMeta(BaseModel):
    id: str
    label: str
    created_at: str
    filename: str
    size_bytes: int = 0


class BackupsReport(BaseModel):
    named: list[NamedBackupMeta]
    quick: QuickBackupMeta


class CreateNamedBackup(BaseModel):
    label: str = ""


class BackupActionResult(BaseModel):
    ok: bool = True
    message: str = ""
    quick: QuickBackupMeta | None = None
    backup: NamedBackupMeta | None = None
