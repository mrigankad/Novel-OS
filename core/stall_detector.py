"""Detect a sagging middle deterministically (design spec §4.3).

Middles are where books die. The published craft advice is consistent about
why: writers have a clear sense of where a story begins and ends and much less
of how to get between them, and the failure has a shape - **the protagonist goes
reactive**, things happen *to* them and they stop pursuing anything, while act
two is supposed to raise pressure and deepen character at the same time.

"Sagging middle" sounds subjective, but it decomposes into signals this project
already stores per chapter: `plot_advances`, `character_development`,
`emotional_beats`, `new_information`, and each thread's `last_updated_chapter`.
A chapter that changes none of them did not move the story, and a *run* of them
is the sag.

Deterministic on purpose. No model is asked whether the book drags - the engine
measures what changed, and any AI involvement is confined to writing the
sentence that explains a flagged run, labelled as interpretation. That
distinction is the whole reason this is trustworthy enough to show.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from state_manager import StoryState

# Chapters that must be flat in a row before it counts as a sag. Two flat
# chapters is a breather; three is a pattern the reader feels.
STALL_RUN_LENGTH = 3

# Statuses that mean a chapter actually exists as prose. An unwritten chapter
# has no activity by definition and must never be reported as a stall.
WRITTEN_STATUSES = ("drafted", "editing", "edited", "validated", "complete")


@dataclass
class ChapterActivity:
    """What measurably changed in one chapter."""
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

    @property
    def movement(self) -> int:
        """Total measurable story movement. Zero means nothing changed."""
        return (
            self.plot_advances
            + self.character_development
            + self.emotional_beats
            + self.new_information
            + self.threads_touched
        )

    @property
    def is_flat(self) -> bool:
        return self.written and self.movement == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "pov": self.pov,
            "written": self.written,
            "plot_advances": self.plot_advances,
            "character_development": self.character_development,
            "emotional_beats": self.emotional_beats,
            "new_information": self.new_information,
            "threads_touched": self.threads_touched,
            "word_count": self.word_count,
            "movement": self.movement,
            "flat": self.is_flat,
        }


@dataclass
class StallRun:
    """A consecutive stretch of chapters where nothing moved."""
    start: int
    end: int
    reason: str
    chapters: List[int] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.chapters)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "reason": self.reason,
            "chapters": list(self.chapters),
            "length": self.length,
        }


def _threads_touched_in(state: "StoryState", number: int) -> int:
    return sum(
        1 for t in state.plot_threads.values()
        if getattr(t, "last_updated_chapter", 0) == number
    )


def chapter_activity(state: "StoryState", number: int) -> ChapterActivity:
    """Measure what changed in a single chapter."""
    chapter = state.chapters.get(number)
    if chapter is None:
        return ChapterActivity(number=number)
    return ChapterActivity(
        number=number,
        title=getattr(chapter, "title", "") or "",
        pov=getattr(chapter, "pov_character", "") or "",
        written=getattr(chapter, "status", "planned") in WRITTEN_STATUSES,
        plot_advances=len(getattr(chapter, "plot_advances", []) or []),
        character_development=len(getattr(chapter, "character_development", {}) or {}),
        emotional_beats=len(getattr(chapter, "emotional_beats", []) or []),
        new_information=len(getattr(chapter, "new_information", []) or []),
        threads_touched=_threads_touched_in(state, number),
        word_count=int(getattr(chapter, "word_count", 0) or 0),
    )


def book_shape(state: "StoryState") -> List[ChapterActivity]:
    """Per-chapter activity in reading order - the data behind the shape strip."""
    return [chapter_activity(state, n) for n in sorted(state.chapters)]


def find_stalls(
    state: "StoryState",
    *,
    run_length: int = STALL_RUN_LENGTH,
) -> List[StallRun]:
    """Consecutive written chapters in which nothing measurably moved.

    Only written chapters count, and only *consecutive* ones: an unwritten
    chapter in between breaks the run rather than extending it, because the sag
    might simply not be drafted yet.
    """
    runs: List[StallRun] = []
    current: List[ChapterActivity] = []

    def flush() -> None:
        if len(current) >= run_length:
            runs.append(StallRun(
                start=current[0].number,
                end=current[-1].number,
                chapters=[a.number for a in current],
                reason=_describe(current),
            ))
        current.clear()

    for activity in book_shape(state):
        if activity.is_flat:
            current.append(activity)
        else:
            flush()
    flush()
    return runs


def _describe(run: List[ChapterActivity]) -> str:
    """Name the failure in the writer's own terms, not the data model's."""
    povs = {a.pov for a in run if a.pov}
    if len(povs) == 1:
        who = next(iter(povs))
        return (
            f"{who} carries {len(run)} chapters in a row without advancing a "
            f"thread or changing - the protagonist has gone reactive"
        )
    return (
        f"{len(run)} chapters in a row with no plot advance, no new "
        f"information and no thread touched"
    )


def check_stalled_middle(
    state: "StoryState",
    as_of_chapter: Optional[int] = None,
) -> List:
    """Continuity check: report sagging runs (design spec §4.3).

    Imported lazily by `continuity_engine` so this module stays independently
    testable and the engine keeps its single Finding definition.
    """
    from continuity_engine import Finding  # local import avoids a cycle

    findings: List = []
    for run in find_stalls(state):
        if as_of_chapter is not None and run.start > as_of_chapter:
            continue
        findings.append(Finding(
            severity="warning",
            category="stalled_middle",
            message=(
                f"Chapters {run.start}-{run.end}: {run.reason}."
            ),
            suggestion=(
                "Give the POV character something they actively want in this "
                "stretch, or fold these chapters together."
            ),
            chapter=run.start,
            entity_id=f"ch{run.start}-{run.end}",
        ))
    return findings
