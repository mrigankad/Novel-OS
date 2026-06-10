import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    ChapterDetail, ChapterStages, ChapterSummary, CharacterSummary,
    ProjectDetail, ProjectSummary,
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


class NoSourceArtifact(Exception):
    """Raised when promoting to Final but no draft/revised exists to promote."""
    pass


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _atomic_write(path: Path, text: str) -> None:
    """Write via temp file + os.replace so a Final is never left half-written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


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

    def chapter_detail(self, project_id: str, number: int) -> ChapterDetail:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        proj = self._project_dir(project_id)
        nnn = f"{number:03d}"
        outline_path = proj / "outputs" / f"chapter_{nnn}_outline.md"
        draft_path = proj / "outputs" / "manuscript" / f"chapter_{nnn}_draft.md"
        return ChapterDetail(
            number=c.number,
            title=c.title or "",
            status=c.status,
            word_count=c.word_count,
            pov=c.pov_character or "",
            outline=outline_path.read_text(encoding="utf-8") if outline_path.exists() else None,
            draft=draft_path.read_text(encoding="utf-8") if draft_path.exists() else None,
        )

    def list_characters(self, project_id: str) -> list[CharacterSummary]:
        s = self._load(project_id)
        return [
            CharacterSummary(id=c.id, full_name=c.full_name, role=c.role)
            for c in s.get_all_characters()
        ]

    def raw_state(self, project_id: str) -> dict:
        import json as _json
        sf = self._project_dir(project_id) / "outputs" / "state" / "story_state.json"
        return _json.loads(sf.read_text(encoding="utf-8"))

    # ----- M2: pipeline stages + editable Final

    def _stage_paths(self, project_id: str, number: int) -> dict[str, Path]:
        proj = self._project_dir(project_id)
        nnn = f"{number:03d}"
        return {
            "outline": proj / "outputs" / f"chapter_{nnn}_outline.md",
            "draft": proj / "outputs" / "manuscript" / f"chapter_{nnn}_draft.md",
            "revised": proj / "outputs" / "manuscript" / f"chapter_{nnn}_revised.md",
            "final": proj / "outputs" / "manuscript" / f"chapter_{nnn}_final.md",
        }

    def chapter_stages(self, project_id: str, number: int) -> ChapterStages:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        p = self._stage_paths(project_id, number)
        return ChapterStages(
            number=number,
            status=c.status,
            outline=_read(p["outline"]),
            draft=_read(p["draft"]),
            revised=_read(p["revised"]),
            final=_read(p["final"]),
            continuity=c.continuity_checks or None,
        )

    def _commit_final(self, project_id: str, number: int, text: str) -> int:
        """Write final.md atomically, update chapter word_count + timestamp, persist."""
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        _atomic_write(self._stage_paths(project_id, number)["final"], text)
        wc = len(text.split())
        c.word_count = wc
        c.last_modified = datetime.now(timezone.utc).isoformat()
        s.save_state()
        return wc

    def promote_final(self, project_id: str, number: int, force: bool = False) -> str:
        """Seed Final from revised||draft. Idempotent: never clobbers a human edit unless forced."""
        p = self._stage_paths(project_id, number)
        if p["final"].exists() and not force:
            return p["final"].read_text(encoding="utf-8")
        source = _read(p["revised"]) if p["revised"].exists() else _read(p["draft"])
        if source is None:
            raise NoSourceArtifact(number)
        self._commit_final(project_id, number, source)
        return source

    def save_final(self, project_id: str, number: int, text: str) -> int:
        return self._commit_final(project_id, number, text)
