import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import db
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


class BadRequest(Exception):
    pass


def build_orchestrator(project_dir: str):
    """Construct a NovelOrchestrator for a project folder. Patchable in tests."""
    from orchestrator import NovelOrchestrator  # noqa: E402 (lazy: heavy import)
    return NovelOrchestrator(project_dir)


# stage -> how to invoke it on an orchestrator with the given params
PHASES: dict[str, Callable[[object, dict], object]] = {
    "plan_outline": lambda o, p: o.plan_outline(int(p.get("chapters", 12)), int(p.get("words", 24000))),
    "plan_chapter": lambda o, p: o.plan_chapter(int(p["number"]), p.get("summary", ""), p.get("pov", "")),
    "write": lambda o, p: o.write_chapter(int(p["number"])),
    "edit": lambda o, p: o.edit_chapter(int(p["number"]), p.get("mode", "line")),
    "validate": lambda o, p: o.validate_chapter(int(p["number"])),
    "approve": lambda o, p: o.approve_chapter(int(p["number"])),
}


def _slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "untitled"


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

    def ensure_chapter(self, project_id: str, number: int) -> None:
        """Raise ProjectNotFound / ChapterNotFound if the chapter doesn't exist."""
        s = self._load(project_id)
        if number not in s.chapters:
            raise ChapterNotFound(number)

    def get_final_text(self, project_id: str, number: int) -> str | None:
        return _read(self._stage_paths(project_id, number)["final"])

    def chapter_stages(self, project_id: str, number: int) -> ChapterStages:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        # keep the DB mirror fresh with whatever the engine produced
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001 - ingest is best-effort
            pass
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
        # DB is the system-of-record for the human-owned Final
        try:
            db.upsert_artifact(project_id, number, "final", text)
        except Exception:  # noqa: BLE001
            pass
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

    # ----- Tier 0: create / edit the world

    def create_project(self, title: str, genre: str, author: str = "") -> ProjectSummary:
        title = title.strip()
        if not title:
            raise BadRequest("Title is required.")
        slug = _slugify(title)
        folder = self.root / slug
        n = 2
        while (folder / "outputs" / "state" / "story_state.json").exists():
            folder = self.root / f"{slug}-{n}"
            n += 1
        folder.mkdir(parents=True, exist_ok=True)
        build_orchestrator(str(folder)).init_project(title, genre, author)
        return ProjectSummary(
            id=folder.name, title=title, genre=genre, chapter_count=0, status="in_progress",
        )

    def add_character(self, project_id: str, name: str, role: str) -> list[CharacterSummary]:
        self._project_dir(project_id)  # 404 if missing
        if not name.strip():
            raise BadRequest("Character name is required.")
        build_orchestrator(str(self.root / project_id)).add_character(name.strip(), role)
        return self.list_characters(project_id)

    def make_phase_job(self, project_id: str, stage: str, params: dict) -> Callable[[], None]:
        """Validate inputs and return a 0-arg callable the JobRunner can run."""
        self._project_dir(project_id)  # 404 if missing
        if stage not in PHASES:
            raise BadRequest(f"Unknown stage '{stage}'. Expected one of {sorted(PHASES)}.")
        project_dir = str(self.root / project_id)

        def fn() -> None:
            orch = build_orchestrator(project_dir)
            PHASES[stage](orch, params)

        return fn

    def export_markdown(self, project_id: str) -> str:
        """Compile the manuscript, preferring the human-reviewed Final per chapter."""
        s = self._load(project_id)
        lines = [
            f"# {s.metadata.get('title', 'Untitled')}",
            "",
            f"*{s.metadata.get('genre', 'Fiction')}*",
            "",
            "---",
            "",
        ]
        for c in sorted(s.chapters.values(), key=lambda c: c.number):
            p = self._stage_paths(project_id, c.number)
            text = _read(p["final"]) or _read(p["revised"]) or _read(p["draft"])
            if text:
                lines.append(text)
                lines.append("\n\n---\n\n")
        return "\n".join(lines)
