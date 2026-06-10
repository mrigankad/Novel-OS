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
