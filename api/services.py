import sys
from pathlib import Path

from .models import (
    ChapterDetail, ChapterSummary, CharacterSummary, ProjectDetail, ProjectSummary,
)

# core/ modules import each other by top-level name; put core/ on the path once.
_CORE = Path(__file__).resolve().parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from state_manager import StoryState  # noqa: E402


class ProjectNotFound(Exception):
    pass


class ChapterNotFound(Exception):
    pass


class ProjectService:
    """Reads Novel OS projects (folders containing outputs/state/story_state.json)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    # --- discovery
    def _project_dir(self, project_id: str) -> Path:
        d = self.root / project_id
        if not (d / "outputs" / "state" / "story_state.json").exists():
            raise ProjectNotFound(project_id)
        return d

    def _load(self, project_id: str) -> StoryState:
        return StoryState(str(self._project_dir(project_id)))

    def list_projects(self) -> list[ProjectSummary]:
        out: list[ProjectSummary] = []
        if not self.root.exists():
            return out
        for child in sorted(self.root.iterdir()):
            state_file = child / "outputs" / "state" / "story_state.json"
            if not state_file.exists():
                continue
            s = StoryState(str(child))
            out.append(ProjectSummary(
                id=child.name,
                title=s.metadata.get("title", child.name),
                genre=s.metadata.get("genre", ""),
                chapter_count=len(s.chapters),
                status=s.metadata.get("status", "in_progress"),
            ))
        return out

    def project_detail(self, project_id: str) -> ProjectDetail:
        s = self._load(project_id)
        return ProjectDetail(
            id=project_id,
            title=s.metadata.get("title", project_id),
            genre=s.metadata.get("genre", ""),
            author=s.metadata.get("author", ""),
            chapter_count=len(s.chapters),
            status=s.metadata.get("status", "in_progress"),
            style={
                "tone": s.style_profile.tone,
                "point_of_view": s.style_profile.point_of_view,
                "prose_style": s.style_profile.prose_style,
            },
        )

    def list_chapters(self, project_id: str) -> list[ChapterSummary]:
        s = self._load(project_id)
        return [
            ChapterSummary(
                number=c.number,
                title=c.title or "",
                status=c.status,
                word_count=c.word_count,
                pov=c.pov_character or "",
            )
            for c in sorted(s.chapters.values(), key=lambda c: c.number)
        ]
