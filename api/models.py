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


class ChapterDetail(ChapterSummary):
    outline: str | None
    draft: str | None


class CharacterSummary(BaseModel):
    id: str
    full_name: str
    role: str


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


class CreateProject(BaseModel):
    title: str
    genre: str = ""
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
    created_at: str
    resolved: bool = False


class AddComment(BaseModel):
    body: str
    quote: str = ""


class UpdateComment(BaseModel):
    resolved: bool
