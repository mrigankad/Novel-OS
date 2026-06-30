import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import db
from .models import (
    ChapterDetail, ChapterPasteResult, ChapterStages, ChapterSummary, CharacterDetail,
    CharacterSummary, DuplicateGroupModel, DuplicatesReport, MergeResult, PlotThreadSummary,
    ProjectDetail, ProjectSummary, AutoResolveResult,
    BibleDuplicateGroupModel, BibleDuplicateMember, BibleDuplicatesReport,
    BibleDedupeMerge, BibleAutoDedupeResult,
)

# core/ modules import each other by top-level name; put core/ on the path once.
_CORE = Path(__file__).resolve().parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from state_manager import StoryState, Character, PlotThread  # noqa: E402


class ProjectNotFound(Exception):
    pass


class ChapterNotFound(Exception):
    pass


class CharacterNotFound(Exception):
    pass


class PlotThreadNotFound(Exception):
    pass


class NoSourceArtifact(Exception):
    """Raised when promoting to Final but no draft/revised exists to promote."""
    pass


class NothingToUnfinalize(Exception):
    """Raised when a chapter has no final text and is not marked complete."""
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
    "edit": lambda o, p: o.edit_chapter(
        int(p["number"]), p.get("mode", "line"), p.get("instructions", ""),
    ),
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


def _has_stage_content(path: Path) -> bool:
    text = _read(path)
    return bool(text and text.strip())


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

    def _chapter_pipeline_step(self, project_id: str, number: int, status: str) -> str:
        """Furthest completed pipeline milestone (for chapter status lights).

        Green (final) requires a saved Final manuscript. Pink (approved) is Approve
        without Final yet — distinct from orchestrator status ``complete``.
        """
        p = self._stage_paths(project_id, number)
        if _has_stage_content(p["final"]):
            return "final"
        try:
            db_text = db.get_artifact_text(project_id, number, "final")
            if db_text and db_text.strip():
                return "final"
        except Exception:  # noqa: BLE001
            pass
        if status == "complete":
            return "approved"
        if status == "validated":
            return "validated"
        if _has_stage_content(p["revised"]) or status in ("edited", "editing"):
            return "revised"
        if _has_stage_content(p["draft"]) or status in ("drafted", "drafting"):
            return "drafted"
        return "none"

    def _chapter_summary(self, project_id: str, c) -> ChapterSummary:
        return ChapterSummary(
            number=c.number,
            title=c.title or "",
            status=c.status,
            word_count=c.word_count,
            pov=c.pov_character or "",
            pipeline_step=self._chapter_pipeline_step(project_id, c.number, c.status),
        )

    def list_chapters(self, project_id: str) -> list[ChapterSummary]:
        s = self._load(project_id)
        return [
            self._chapter_summary(project_id, c)
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
            CharacterSummary(id=c.id, full_name=c.full_name, role=c.role, aliases=list(c.aliases))
            for c in s.get_all_characters()
        ]

    def _plot_thread_summary(self, t: PlotThread) -> PlotThreadSummary:
        return PlotThreadSummary(
            id=t.id,
            name=t.name,
            description=t.description,
            thread_type=t.thread_type,
            status=t.status,
            priority=t.priority,
            sort_order=t.sort_order,
            subplots=list(t.subplots or []),
        )

    def list_plot_threads(self, project_id: str) -> list[PlotThreadSummary]:
        s = self._load(project_id)
        return [self._plot_thread_summary(t) for t in s.get_ordered_plot_threads()]

    def reorder_plot_threads(self, project_id: str, ordered_ids: list[str]) -> list[PlotThreadSummary]:
        s = self._load(project_id)
        missing = [tid for tid in ordered_ids if tid not in s.plot_threads]
        if missing:
            raise BadRequest(f"Unknown plot thread id(s): {', '.join(missing)}")
        if len(ordered_ids) != len(s.plot_threads):
            raise BadRequest("ordered_ids must include every plot thread exactly once.")
        s.reorder_plot_threads(ordered_ids)
        s.save_state()
        return self.list_plot_threads(project_id)

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

    def unfinalize_chapter(self, project_id: str, number: int) -> ChapterStages:
        """Remove Final and roll back validate/approve so Revise can run again."""
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        p = self._stage_paths(project_id, number)
        final_text = _read(p["final"])
        if final_text is None:
            try:
                final_text = db.get_artifact_text(project_id, number, "final")
            except Exception:  # noqa: BLE001
                pass
        has_final = bool(final_text and final_text.strip())
        post_revise = c.status in ("complete", "validated") or has_final
        if not post_revise:
            raise NothingToUnfinalize(number)

        if has_final and final_text:
            _atomic_write(p["draft"], final_text)
            _atomic_write(p["revised"], final_text)
            try:
                db.upsert_artifact(project_id, number, "draft", final_text)
                db.upsert_artifact(project_id, number, "revised", final_text)
                db.delete_artifact(project_id, number, "final")
            except Exception:  # noqa: BLE001
                pass
            if p["final"].exists():
                p["final"].unlink()
            c.word_count = len(final_text.split())

        c.status = "edited"
        c.continuity_checks = {}
        c.last_modified = datetime.now(timezone.utc).isoformat()
        s.save_state()
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return self.chapter_stages(project_id, number)

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

    def make_import_job(
        self,
        chapters_dir: str,
        *,
        title: str = "",
        genre: str = "",
        author: str = "",
        project_id: str = "",
        synthesize: bool = True,
        no_extract: bool = False,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
    ) -> tuple[Callable[[], None], str]:
        """Return (callable, project_id) for a background import job."""
        from import_pipeline import ImportPipeline  # noqa: E402

        src = Path(chapters_dir).expanduser()
        if not src.is_dir():
            raise BadRequest(f"Chapters directory not found: {chapters_dir}")

        if project_id:
            proj_path = str(self._project_dir(project_id))
            resolved_id = project_id
        else:
            if not title.strip() or not genre.strip():
                raise BadRequest("Title and genre are required for a new import.")
            summary = self.create_project(title.strip(), genre.strip(), author.strip())
            resolved_id = summary.id
            proj_path = str(self.root / resolved_id)

        def fn() -> None:
            pipe = ImportPipeline(proj_path)
            pipe.import_directory(
                src,
                chapter_from=from_chapter,
                chapter_to=to_chapter,
                extract=not no_extract,
                dry_run=False,
                on_progress=lambda msg: print(msg, flush=True),
            )
            if synthesize and not no_extract:
                pipe.synthesize_structure(on_progress=lambda msg: print(msg, flush=True))
            pipe.write_character_profiles()
            try:
                db.ingest_project(self.root, resolved_id)
            except Exception:  # noqa: BLE001
                pass

        return fn, resolved_id

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

    # ----- Manual edit: chapters, characters, plots, story bible

    def _character_detail(self, char: Character) -> CharacterDetail:
        return CharacterDetail(**char.to_dict())

    def get_character(self, project_id: str, character_id: str) -> CharacterDetail:
        s = self._load(project_id)
        char = s.get_character(character_id)
        if char is None:
            raise CharacterNotFound(character_id)
        return self._character_detail(char)

    def update_character(self, project_id: str, character_id: str, updates: dict) -> CharacterDetail:
        s = self._load(project_id)
        if s.get_character(character_id) is None:
            raise CharacterNotFound(character_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if filtered:
            s.update_character(character_id, filtered)
            s.save_state()
        return self.get_character(project_id, character_id)

    def create_plot_thread(self, project_id: str, name: str, description: str = "",
                           thread_type: str = "main", priority: int = 3,
                           status: str = "active", subplots: list[str] | None = None) -> PlotThreadSummary:
        s = self._load(project_id)
        if not name.strip():
            raise BadRequest("Plot thread name is required.")
        n = len(s.plot_threads) + 1
        tid = f"plot_{n:03d}"
        while tid in s.plot_threads:
            n += 1
            tid = f"plot_{n:03d}"
        thread = PlotThread(
            id=tid, name=name.strip(), description=description.strip(),
            thread_type=thread_type, priority=priority, status=status,
            subplots=list(subplots or []),
        )
        s.add_plot_thread(thread)
        s.save_state()
        return self._plot_thread_summary(thread)

    def update_plot_thread(self, project_id: str, thread_id: str, updates: dict) -> PlotThreadSummary:
        s = self._load(project_id)
        thread = s.get_plot_thread(thread_id)
        if thread is None:
            raise PlotThreadNotFound(thread_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if filtered:
            s.update_plot_thread(thread_id, filtered)
            s.save_state()
            thread = s.get_plot_thread(thread_id)
        return self._plot_thread_summary(thread)

    def get_story_bible(self, project_id: str) -> dict:
        return self._load(project_id).story_bible

    def update_story_bible_section(self, project_id: str, section: str, content) -> dict:
        s = self._load(project_id)
        s.update_story_bible(section, content)
        s.save_state()
        return s.story_bible

    def create_chapter(self, project_id: str, number: int, title: str = "",
                       text: str = "", extract: bool = False) -> ChapterPasteResult | tuple[Callable, str, int]:
        """Create chapter. Returns sync result or (job_fn, project_id, number) if extract."""
        self._project_dir(project_id)
        if number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        s = self._load(project_id)
        if number in s.chapters and text.strip():
            raise BadRequest(f"Chapter {number} already exists — open it to edit or pick another number.")
        if not text.strip():
            s.create_chapter(number, title.strip())
            if title.strip():
                s.update_chapter(number, {"title": title.strip()})
            s.save_state()
            ch = s.get_chapter(number)
            return ChapterPasteResult(number=number, word_count=ch.word_count if ch else 0)

        if extract:
            proj_path = str(self._project_dir(project_id))
            def fn() -> None:
                from import_pipeline import ImportPipeline  # noqa: E402
                ImportPipeline(proj_path).import_chapter_text(
                    number, text, title=title, extract=True,
                    on_progress=lambda msg: print(msg, flush=True),
                )
                try:
                    db.ingest_project(self.root, project_id)
                except Exception:  # noqa: BLE001
                    pass
            return fn, project_id, number

        from import_pipeline import ImportPipeline  # noqa: E402
        wc, changes = ImportPipeline(str(self._project_dir(project_id))).import_chapter_text(
            number, text, title=title, extract=False,
        )
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return ChapterPasteResult(number=number, word_count=wc, changes=changes)

    def update_chapter(self, project_id: str, number: int, updates: dict) -> ChapterSummary:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if filtered:
            s.update_chapter(number, filtered)
            s.save_state()
            c = s.chapters[number]
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
        return self._chapter_summary(project_id, c)

    def save_draft(self, project_id: str, number: int, text: str) -> int:
        s = self._load(project_id)
        if number not in s.chapters:
            s.create_chapter(number)
            s.save_state()
        draft_path = self._stage_paths(project_id, number)["draft"]
        _atomic_write(draft_path, text)
        wc = len(text.split())
        s.update_chapter(number, {"word_count": wc, "status": "drafted"})
        s.save_state()
        try:
            db.upsert_artifact(project_id, number, "draft", text)
        except Exception:  # noqa: BLE001
            pass
        return wc

    def save_revised(self, project_id: str, number: int, text: str) -> int:
        s = self._load(project_id)
        if number not in s.chapters:
            raise ChapterNotFound(number)
        _atomic_write(self._stage_paths(project_id, number)["revised"], text)
        wc = len(text.split())
        status = s.chapters[number].status
        if status in ("validated", "complete"):
            status = "edited"
        elif status not in ("editing", "edited"):
            status = "edited"
        s.update_chapter(number, {"word_count": wc, "status": status})
        s.save_state()
        try:
            db.upsert_artifact(project_id, number, "revised", text)
        except Exception:  # noqa: BLE001
            pass
        return wc

    @staticmethod
    def _chapter_files(proj: Path, number: int) -> list[Path]:
        nnn = f"{number:03d}"
        out = proj / "outputs"
        files: list[Path] = []
        outline = out / f"chapter_{nnn}_outline.md"
        if outline.exists():
            files.append(outline)
        for sub, pattern in (
            ("manuscript", f"chapter_{nnn}_*.md"),
            ("sources", f"chapter_{nnn}*"),
            ("feedback", f"chapter_{nnn}_*"),
        ):
            d = out / sub
            if d.is_dir():
                files.extend(sorted(d.glob(pattern)))
        return files

    @staticmethod
    def _rename_chapter_files(proj: Path, from_num: int, to_num: int) -> None:
        if from_num == to_num:
            return
        for path in ProjectService._chapter_files(proj, from_num):
            dest = path.parent / path.name.replace(f"chapter_{from_num:03d}", f"chapter_{to_num:03d}")
            if dest.exists():
                raise BadRequest(f"File collision renaming chapter {from_num} → {to_num}: {dest.name}")
            path.rename(dest)

    def reassign_chapter(self, project_id: str, from_number: int, to_number: int) -> dict:
        if from_number < 1 or to_number < 1:
            raise BadRequest("Chapter numbers must be at least 1.")
        s = self._load(project_id)
        if from_number not in s.chapters:
            raise ChapterNotFound(from_number)
        if from_number == to_number:
            c = s.chapters[from_number]
            return {
                "action": "unchanged",
                "from_number": from_number,
                "to_number": to_number,
                "chapter": self._chapter_summary(project_id, c),
            }
        proj = self._project_dir(project_id)
        swap = to_number in s.chapters
        if swap:
            sentinel = max(s.chapters.keys()) + 10000
            self._rename_chapter_files(proj, from_number, sentinel)
            self._rename_chapter_files(proj, to_number, from_number)
            self._rename_chapter_files(proj, sentinel, to_number)
        else:
            self._rename_chapter_files(proj, from_number, to_number)
        action = s.reassign_chapter(from_number, to_number)
        s.save_state()
        try:
            db.chapter_reassign(project_id, from_number, to_number, swap=swap)
        except Exception:  # noqa: BLE001
            pass
        c = s.chapters[to_number]
        other = s.chapters.get(from_number) if swap else None
        result = {
            "action": action,
            "from_number": from_number,
            "to_number": to_number,
            "chapter": self._chapter_summary(project_id, c),
        }
        if other is not None:
            result["swapped_with"] = self._chapter_summary(project_id, other)
        return result

    def paste_chapter(self, project_id: str, number: int, text: str,
                      title: str = "", extract: bool = False) -> ChapterPasteResult | tuple[Callable, str, int]:
        s = self._load(project_id)
        if number not in s.chapters:
            s.create_chapter(number, title.strip())
            s.save_state()
        if extract:
            proj_path = str(self._project_dir(project_id))
            def fn() -> None:
                from import_pipeline import ImportPipeline  # noqa: E402
                ImportPipeline(proj_path).import_chapter_text(
                    number, text, title=title, extract=True,
                    on_progress=lambda msg: print(msg, flush=True),
                )
                try:
                    db.ingest_project(self.root, project_id)
                except Exception:  # noqa: BLE001
                    pass
            return fn, project_id, number
        from import_pipeline import ImportPipeline  # noqa: E402
        wc, changes = ImportPipeline(str(self._project_dir(project_id))).import_chapter_text(
            number, text, title=title, extract=False,
        )
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return ChapterPasteResult(number=number, word_count=wc, changes=changes)

    def make_extract_job(self, project_id: str, number: int) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        proj_path = str(self._project_dir(project_id))
        def fn() -> None:
            from import_pipeline import ImportPipeline  # noqa: E402
            ImportPipeline(proj_path).extract_chapter_from_draft(
                number, on_progress=lambda msg: print(msg, flush=True),
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
        return fn

    def make_mine_job(
        self,
        project_id: str,
        number: int,
        kind: str,
        *,
        source: str = "draft",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        if kind not in ("plots", "characters", "bible"):
            raise BadRequest("kind must be plots, characters, or bible")
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_miner import ChapterMiner  # noqa: WPS433
            ChapterMiner(proj_path).mine(
                number, kind, source=source,
                on_progress=lambda msg: print(msg, flush=True),
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def make_background_extract_job(
        self, project_id: str, text: str, label: str = "Background",
    ) -> Callable[[], None]:
        self._project_dir(project_id)
        if not text.strip():
            raise BadRequest("Background text is required.")
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from background_extractor import BackgroundExtractor  # noqa: E402
            BackgroundExtractor(proj_path).extract(
                text.strip(), label=label.strip() or "Background",
                on_progress=lambda msg: print(msg, flush=True),
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    # ----- Character profile generation (preview → merge in UI)

    def _character_generator(self, project_id: str):
        from character_generator import CharacterGenerator  # noqa: E402
        return CharacterGenerator(str(self._project_dir(project_id)))

    def get_character_generate_preview(self, project_id: str) -> dict | None:
        self._project_dir(project_id)
        path = self._character_generator(project_id).preview_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def make_character_generate_job(
        self,
        project_id: str,
        prompt: str,
        *,
        character_id: str | None = None,
        hint_name: str = "",
        hint_role: str = "",
    ) -> Callable[[], None]:
        self._project_dir(project_id)
        if not prompt.strip():
            raise BadRequest("Character prompt is required.")
        if character_id:
            s = self._load(project_id)
            if s.get_character(character_id) is None:
                raise CharacterNotFound(character_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from character_generator import CharacterGenerator  # noqa: E402
            CharacterGenerator(proj_path).generate(
                prompt.strip(),
                character_id=character_id,
                hint_name=hint_name,
                hint_role=hint_role,
                on_progress=lambda msg: print(msg, flush=True),
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def discard_character_generate_preview(self, project_id: str) -> None:
        path = self._character_generator(project_id).preview_path()
        if path.exists():
            path.unlink()

    # ----- Plot thread description generation (preview → apply in UI)

    def _plot_generator(self, project_id: str):
        from plot_generator import PlotGenerator  # noqa: E402
        return PlotGenerator(str(self._project_dir(project_id)))

    def get_plot_generate_preview(self, project_id: str, thread_id: str) -> dict | None:
        self._project_dir(project_id)
        path = self._plot_generator(project_id).preview_path(thread_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def make_plot_generate_job(
        self,
        project_id: str,
        thread_id: str,
        prompt: str = "",
    ) -> Callable[[], None]:
        self._project_dir(project_id)
        s = self._load(project_id)
        if thread_id not in s.plot_threads:
            raise PlotThreadNotFound(thread_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from plot_generator import PlotGenerator  # noqa: E402
            PlotGenerator(proj_path).generate(
                thread_id,
                prompt=prompt,
                on_progress=lambda msg: print(msg, flush=True),
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def discard_plot_generate_preview(self, project_id: str, thread_id: str) -> None:
        path = self._plot_generator(project_id).preview_path(thread_id)
        if path.exists():
            path.unlink()

    # ----- Plot panel dedup (subplots vs threads on plots page)

    def _plot_panel_issue_model(self, issue) -> "PlotPanelIssueModel":
        from api.models import PlotPanelIssueModel, PlotPanelLocation  # noqa: E402
        return PlotPanelIssueModel(
            issue_id=issue.issue_id,
            kind=issue.kind,
            confidence=issue.confidence,
            reason=issue.reason,
            subplot_line=issue.subplot_line,
            locations=[PlotPanelLocation(**loc) for loc in issue.locations],
            thread_id=issue.thread_id,
            thread_name=issue.thread_name,
            suggested_parent_id=issue.suggested_parent_id,
            suggested_parent_name=issue.suggested_parent_name,
            suggested_action=issue.suggested_action,
        )

    def get_plot_panel_issues(self, project_id: str):
        from api.models import PlotPanelIssuesReport  # noqa: E402
        from entity_dedup import find_plot_panel_issues  # noqa: E402

        s = self._load(project_id)
        issues = find_plot_panel_issues(s)
        return PlotPanelIssuesReport(
            issues=[self._plot_panel_issue_model(i) for i in issues],
        )

    def resolve_plot_panel_issue(self, project_id: str, issue_id: str):
        from api.models import PlotPanelResolveResult  # noqa: E402
        from entity_dedup import find_plot_panel_issues, resolve_plot_panel_issue  # noqa: E402

        s = self._load(project_id)
        issues = find_plot_panel_issues(s)
        try:
            log = resolve_plot_panel_issue(s, issue_id, issues=issues)
        except ValueError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return PlotPanelResolveResult(issue_id=issue_id, log=log)

    def auto_resolve_plot_panel_issues(self, project_id: str):
        from api.models import PlotPanelAutoResolveResult  # noqa: E402
        from entity_dedup import auto_resolve_plot_panel_issues, find_plot_panel_issues  # noqa: E402

        s = self._load(project_id)
        before = len(find_plot_panel_issues(s))
        log = auto_resolve_plot_panel_issues(s)
        after = len(find_plot_panel_issues(s))
        if log:
            s.save_state()
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
        return PlotPanelAutoResolveResult(resolved=max(0, before - after), log=log)

    # ----- Chapter regenerate (preview → keep / discard)

    def _regenerator(self, project_id: str):
        from chapter_regenerator import ChapterRegenerator  # noqa: E402
        return ChapterRegenerator(str(self._project_dir(project_id)))

    def get_regenerate_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        reg = self._regenerator(project_id)
        preview_path = reg.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = reg.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": meta.get("instructions", ""),
        }

    def make_regenerate_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        reg = self._regenerator(project_id)
        reg.read_source(number, source)  # validate before starting job
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_regenerator import ChapterRegenerator  # noqa: E402
            ChapterRegenerator(proj_path).regenerate(
                number,
                source=source,
                instructions=instructions,
                on_progress=lambda msg: print(msg, flush=True),
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_regenerate_preview(
        self,
        project_id: str,
        number: int,
        text: str,
        target: str | None = None,
    ) -> tuple[str, int]:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        reg = self._regenerator(project_id)
        if not reg.preview_path(number).exists():
            raise BadRequest("No regenerate preview to apply.")
        meta_path = reg.meta_path(number)
        meta: dict = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stage = (target or meta.get("source") or "draft").lower()
        if stage not in ("draft", "revised", "final"):
            raise BadRequest("target must be draft, revised, or final")
        if stage == "draft":
            wc = self.save_draft(project_id, number, text)
        elif stage == "final":
            wc = self.save_final(project_id, number, text)
        else:
            wc = self.save_revised(project_id, number, text)
        self.discard_regenerate_preview(project_id, number)
        return stage, wc

    def discard_regenerate_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        reg = self._regenerator(project_id)
        for path in (reg.preview_path(number), reg.meta_path(number)):
            if path.exists():
                path.unlink()

    # ----- Expand [[expand: …]] placeholders (preview → keep / discard)

    def _expander(self, project_id: str):
        from chapter_expander import ChapterExpander  # noqa: E402
        return ChapterExpander(str(self._project_dir(project_id)))

    def get_expand_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        exp = self._expander(project_id)
        preview_path = exp.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = exp.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": meta.get("instructions", ""),
            "placeholder_count": meta.get("placeholder_count"),
        }

    def make_expand_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        exp = self._expander(project_id)
        text = exp.read_source(number, source)
        from chapter_expander import find_placeholders  # noqa: E402
        if not find_placeholders(text):
            raise BadRequest(
                "No [[expand: …]] placeholders in this chapter. "
                "Add markers like [[expand: describe the crowd at the market]]."
            )
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_expander import ChapterExpander  # noqa: E402
            ChapterExpander(proj_path).expand(
                number,
                source=source,
                instructions=instructions,
                on_progress=lambda msg: print(msg, flush=True),
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_expand_preview(
        self,
        project_id: str,
        number: int,
        text: str,
        target: str | None = None,
    ) -> tuple[str, int]:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        exp = self._expander(project_id)
        if not exp.preview_path(number).exists():
            raise BadRequest("No expand preview to apply.")
        meta_path = exp.meta_path(number)
        meta: dict = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stage = (target or meta.get("source") or "draft").lower()
        if stage not in ("draft", "revised", "final"):
            raise BadRequest("target must be draft, revised, or final")
        if stage == "draft":
            wc = self.save_draft(project_id, number, text)
        elif stage == "final":
            wc = self.save_final(project_id, number, text)
        else:
            wc = self.save_revised(project_id, number, text)
        self.discard_expand_preview(project_id, number)
        return stage, wc

    def discard_expand_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        exp = self._expander(project_id)
        for path in (exp.preview_path(number), exp.meta_path(number)):
            if path.exists():
                path.unlink()

    # ----- Generate outline from chapter prose (preview → keep / discard)

    def _outline_generator(self, project_id: str):
        from chapter_outline_generator import ChapterOutlineGenerator  # noqa: WPS433
        return ChapterOutlineGenerator(str(self._project_dir(project_id)))

    def save_outline(self, project_id: str, number: int, text: str) -> int:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Outline text is empty.")
        _atomic_write(self._stage_paths(project_id, number)["outline"], text)
        wc = len(text.split())
        try:
            db.upsert_artifact(project_id, number, "outline", text)
        except Exception:  # noqa: BLE001
            pass
        return wc

    def get_outline_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        gen = self._outline_generator(project_id)
        preview_path = gen.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = gen.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": meta.get("instructions", ""),
        }

    def make_generate_outline_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        gen = self._outline_generator(project_id)
        if source == "notes":
            if not instructions.strip():
                raise BadRequest("Outline notes / direction are required.")
        else:
            gen._reader.read_source(number, source)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_outline_generator import ChapterOutlineGenerator  # noqa: WPS433
            ChapterOutlineGenerator(proj_path).generate(
                number,
                source=source,
                instructions=instructions,
                on_progress=lambda msg: print(msg, flush=True),
            )

        return fn

    def apply_outline_preview(self, project_id: str, number: int, text: str) -> int:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        gen = self._outline_generator(project_id)
        if not gen.preview_path(number).exists():
            raise BadRequest("No outline preview to apply.")
        wc = self.save_outline(project_id, number, text)
        self.discard_outline_preview(project_id, number)
        return wc

    def discard_outline_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        gen = self._outline_generator(project_id)
        for path in (gen.preview_path(number), gen.meta_path(number)):
            if path.exists():
                path.unlink()

    # ----- Duplicate detection & merge

    def _dedup_suggestions_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "outputs" / "dedup" / "suggestions.json"

    def _group_to_model(self, g) -> DuplicateGroupModel:
        return DuplicateGroupModel(
            kind=g.kind,
            confidence=g.confidence,
            reason=g.reason,
            suggested_keep_id=g.suggested_keep_id,
            members=g.members,
        )

    def _ai_group_to_model(self, g: dict) -> DuplicateGroupModel | None:
        from api.models import DuplicateMember  # noqa: E402

        members = []
        for m in g.get("members") or []:
            if not isinstance(m, dict) or not m.get("id"):
                continue
            members.append(DuplicateMember(
                id=str(m["id"]),
                label=str(m.get("label") or m["id"]),
                role=m.get("role"),
                thread_type=m.get("thread_type"),
            ))
        if len(members) < 2:
            return None
        return DuplicateGroupModel(
            kind=str(g.get("kind", "character")),
            confidence=float(g.get("confidence", 0.85)),
            reason=str(g.get("reason", "AI suggested merge")),
            suggested_keep_id=str(g.get("suggested_keep_id", "")),
            members=members,
        )

    def _sync_entity_dedup_file(self, project_id: str, s, data: dict) -> dict:
        from entity_dedup import filter_stale_entity_groups  # noqa: E402

        ai_path = self._dedup_suggestions_path(project_id)
        chars = filter_stale_entity_groups(s, data.get("characters") or [], "character")
        plots = filter_stale_entity_groups(s, data.get("plot_threads") or [], "plot_thread")
        if chars == (data.get("characters") or []) and plots == (data.get("plot_threads") or []):
            return data
        data = dict(data)
        data["characters"] = chars
        data["plot_threads"] = plots
        if chars or plots or data.get("scanned_at"):
            ai_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        else:
            ai_path.unlink(missing_ok=True)
        return data

    def get_duplicates(self, project_id: str, *, prefer_ai: bool = False) -> DuplicatesReport:
        from entity_dedup import scan_duplicates  # noqa: E402

        s = self._load(project_id)
        ai_path = self._dedup_suggestions_path(project_id)
        if prefer_ai and ai_path.exists():
            data = json.loads(ai_path.read_text(encoding="utf-8"))
            data = self._sync_entity_dedup_file(project_id, s, data)
            char_models = [
                m for g in data.get("characters") or []
                if (m := self._ai_group_to_model(g)) is not None
            ]
            plot_models = [
                m for g in data.get("plot_threads") or []
                if (m := self._ai_group_to_model(g)) is not None
            ]
            return DuplicatesReport(
                characters=char_models,
                plot_threads=plot_models,
                source="ai",
                ai_scan_completed=bool(data.get("scanned_at")),
                scanned_at=data.get("scanned_at"),
            )
        report = scan_duplicates(s)
        return DuplicatesReport(
            characters=[self._group_to_model(g) for g in report["characters"]],
            plot_threads=[self._group_to_model(g) for g in report["plot_threads"]],
            source="heuristic",
        )

    def make_ai_duplicate_scan_job(self, project_id: str) -> Callable[[], None]:
        self._project_dir(project_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from datetime import datetime, timezone

            from entity_dedup import ai_suggest_duplicate_groups  # noqa: E402
            from llm_client import LLMClient  # noqa: E402
            from state_manager import StoryState  # noqa: E402

            state = StoryState(proj_path)
            report = ai_suggest_duplicate_groups(state, LLMClient())
            out_path = Path(proj_path) / "outputs" / "dedup" / "suggestions.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "scanned_at": datetime.now(timezone.utc).isoformat(),
                "characters": [g.__dict__ for g in report["characters"]],
                "plot_threads": [g.__dict__ for g in report["plot_threads"]],
            }
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(
                f"AI duplicate scan: {len(payload['characters'])} character groups, "
                f"{len(payload['plot_threads'])} plot groups",
                flush=True,
            )

        return fn

    def _prune_dedup_suggestions(
        self, project_id: str, affected_ids: set[str],
    ) -> None:
        path = self._dedup_suggestions_path(project_id)
        if not path.exists() or not affected_ids:
            return
        data = json.loads(path.read_text(encoding="utf-8"))

        def touched(group: dict) -> bool:
            member_ids = {str(m.get("id", "")) for m in group.get("members") or []}
            return bool(member_ids & affected_ids)

        for key in ("characters", "plot_threads"):
            data[key] = [g for g in data.get(key, []) if not touched(g)]
        if not data.get("characters") and not data.get("plot_threads"):
            if data.get("scanned_at"):
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                path.unlink()
        else:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def merge_entities(
        self,
        project_id: str,
        kind: str,
        keep_id: str,
        merge_ids: list[str],
        *,
        mode: str = "parallel",
        label_override: str = "",
    ) -> MergeResult:
        from entity_dedup import merge_characters, merge_plot_threads, nest_plot_threads  # noqa: E402

        s = self._load(project_id)
        merge_ids = [m for m in merge_ids if m != keep_id]
        if not merge_ids:
            raise BadRequest("Nothing to merge.")
        override = label_override.strip()
        if kind == "character":
            if mode != "parallel":
                raise BadRequest("Characters only support parallel merge.")
            log = merge_characters(s, keep_id, merge_ids, label_override=override)
            keep_label = s.characters[keep_id].full_name if keep_id in s.characters else override
        elif kind == "plot_thread":
            if mode == "nest":
                log = nest_plot_threads(s, keep_id, merge_ids, label_override=override)
            else:
                log = merge_plot_threads(s, keep_id, merge_ids, label_override=override)
            keep_label = s.plot_threads[keep_id].name if keep_id in s.plot_threads else override
        else:
            raise BadRequest("kind must be character or plot_thread")
        s.save_state()
        affected = {keep_id, *merge_ids}
        self._prune_dedup_suggestions(project_id, affected)
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return MergeResult(
            kind=kind, keep_id=keep_id, merged=merge_ids, log=log, mode=mode,
            keep_label=keep_label or override,
        )

    def nest_plot_threads(self, project_id: str, parent_id: str, child_ids: list[str]) -> MergeResult:
        return self.merge_entities(
            project_id, "plot_thread", parent_id, child_ids, mode="nest",
        )

    def auto_resolve_duplicates(self, project_id: str) -> AutoResolveResult:
        from entity_dedup import auto_resolve_duplicates  # noqa: E402

        s = self._load(project_id)
        before_c = len(s.characters)
        before_p = len(s.plot_threads)
        log = auto_resolve_duplicates(s)
        s.save_state()
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return AutoResolveResult(
            merged_characters=before_c - len(s.characters),
            merged_plot_threads=before_p - len(s.plot_threads),
            log=log,
        )

    def clear_ai_duplicate_suggestions(self, project_id: str) -> None:
        path = self._dedup_suggestions_path(project_id)
        if path.exists():
            path.unlink()

    # ----- Story bible deduplication

    def _bible_dedup_suggestions_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "outputs" / "dedup" / "bible_suggestions.json"

    def _bible_group_to_model(self, g) -> BibleDuplicateGroupModel:
        return BibleDuplicateGroupModel(
            section=g.section,
            confidence=g.confidence,
            reason=g.reason,
            suggested_keep_index=g.suggested_keep_index,
            members=[BibleDuplicateMember(**m) for m in g.members],
        )

    def get_bible_duplicates(self, project_id: str, *, prefer_ai: bool = False) -> BibleDuplicatesReport:
        from bible_dedup import filter_stale_bible_groups, find_bible_duplicate_groups  # noqa: E402

        s = self._load(project_id)
        ai_path = self._bible_dedup_suggestions_path(project_id)
        if prefer_ai and ai_path.exists():
            data = json.loads(ai_path.read_text(encoding="utf-8"))
            raw_groups = filter_stale_bible_groups(s.story_bible, data.get("groups", []))
            if raw_groups != data.get("groups", []):
                if raw_groups:
                    data["groups"] = raw_groups
                    ai_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                else:
                    ai_path.unlink(missing_ok=True)
            return BibleDuplicatesReport(
                groups=[BibleDuplicateGroupModel(**g) for g in raw_groups],
                source="ai",
            )
        groups = find_bible_duplicate_groups(s.story_bible)
        return BibleDuplicatesReport(
            groups=[self._bible_group_to_model(g) for g in groups],
            source="heuristic",
        )

    def get_bible_dedup_status(self, project_id: str):
        from api.models import BibleDedupStatus  # noqa: E402

        ai_path = self._bible_dedup_suggestions_path(project_id)
        if not ai_path.exists():
            return BibleDedupStatus(ai_suggestions_ready=False, ai_group_count=0)
        try:
            data = json.loads(ai_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return BibleDedupStatus(ai_suggestions_ready=False, ai_group_count=0)
        groups = data.get("groups") or []
        return BibleDedupStatus(ai_suggestions_ready=bool(groups), ai_group_count=len(groups))

    def get_duplicates_status(self, project_id: str):
        from api.models import EntityDedupStatus  # noqa: E402

        ai_path = self._dedup_suggestions_path(project_id)
        if not ai_path.exists():
            return EntityDedupStatus(
                ai_suggestions_ready=False,
                ai_group_count=0,
                has_ai_file=False,
                ai_scan_completed=False,
            )
        try:
            data = json.loads(ai_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return EntityDedupStatus(
                ai_suggestions_ready=False,
                ai_group_count=0,
                has_ai_file=True,
                ai_scan_completed=False,
            )
        char_count = len(data.get("characters") or [])
        plot_count = len(data.get("plot_threads") or [])
        count = char_count + plot_count
        scanned_at = data.get("scanned_at")
        return EntityDedupStatus(
            ai_suggestions_ready=count > 0,
            ai_group_count=count,
            has_ai_file=True,
            ai_scan_completed=bool(scanned_at),
            character_group_count=char_count,
            plot_thread_group_count=plot_count,
        )

    def make_bible_ai_dedup_job(self, project_id: str) -> Callable[[], None]:
        self._project_dir(project_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from bible_dedup import ai_suggest_bible_duplicate_groups  # noqa: E402
            from llm_client import LLMClient  # noqa: E402
            from state_manager import StoryState  # noqa: E402

            state = StoryState(proj_path)
            groups = ai_suggest_bible_duplicate_groups(state.story_bible, LLMClient())
            out_path = Path(proj_path) / "outputs" / "dedup" / "bible_suggestions.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"groups": [g.__dict__ for g in groups]}
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"AI bible dedup: {len(groups)} group(s)", flush=True)

        return fn

    def merge_bible_duplicates(self, project_id: str, body: BibleDedupeMerge) -> BibleAutoDedupeResult:
        from bible_dedup import apply_bible_group_members, prune_bible_suggestion_groups, section_items  # noqa: E402

        s = self._load(project_id)
        members = [m.model_dump() for m in body.members]
        if len(members) < 2:
            raise BadRequest("Need at least two bible entries to merge.")
        try:
            log = apply_bible_group_members(
                s.story_bible,
                members,
                body.keep_section,
                body.keep_index,
                text_override=body.text_override,
            )
        except ValueError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        from bible_dedup import bible_match_score  # noqa: E402

        keep_text = body.text_override.strip()
        if not keep_text:
            items = section_items(s.story_bible, body.keep_section)
            keep_label = next(
                (
                    str(m["label"])
                    for m in members
                    if m["section"] == body.keep_section and m["index"] == body.keep_index
                ),
                "",
            )
            for item in items:
                if keep_label and bible_match_score(item, keep_label) >= 0.85:
                    keep_text = item
                    break
            if not keep_text and items:
                keep_text = items[0]
        affected = {str(m.get("id", "")) for m in members if m.get("id")}
        ai_path = self._bible_dedup_suggestions_path(project_id)
        if ai_path.exists() and affected:
            data = json.loads(ai_path.read_text(encoding="utf-8"))
            remaining = prune_bible_suggestion_groups(data.get("groups", []), affected)
            if remaining:
                data["groups"] = remaining
                ai_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                ai_path.unlink(missing_ok=True)
        return BibleAutoDedupeResult(removed=len(log), log=log, keep_text=keep_text)

    def auto_dedupe_bible(self, project_id: str) -> BibleAutoDedupeResult:
        from bible_dedup import auto_dedupe_bible  # noqa: E402

        s = self._load(project_id)
        log = auto_dedupe_bible(s.story_bible)
        if log:
            s.save_state()
        return BibleAutoDedupeResult(removed=len(log), log=log)

    # ----- Project backups

    def _backup_hooks(self, project_id: str):
        from project_backup import BACKUP_VERSION  # noqa: WPS433

        def prepare_export() -> dict:
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
            data = db.export_project_data(project_id)
            data["version"] = BACKUP_VERSION
            return data

        def import_db(data: dict) -> None:
            db.import_project_data(project_id, data)

        def sync_artifacts() -> None:
            db.sync_artifacts_to_files(self.root, project_id)

        return prepare_export, import_db, sync_artifacts

    def list_backups(self, project_id: str) -> dict:
        from project_backup import list_backups  # noqa: WPS433

        proj = self._project_dir(project_id)
        report = list_backups(proj)
        return report

    def create_named_backup(self, project_id: str, label: str) -> dict:
        from project_backup import create_named_backup  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, _, _ = self._backup_hooks(project_id)
        entry = create_named_backup(proj, label, db_export=prepare())
        return entry

    def restore_named_backup(self, project_id: str, backup_id: str) -> dict:
        from project_backup import restore_named_backup  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, import_db, sync_artifacts = self._backup_hooks(project_id)
        return restore_named_backup(
            proj, backup_id,
            import_db=import_db,
            sync_artifacts=sync_artifacts,
        )

    def delete_named_backup(self, project_id: str, backup_id: str) -> None:
        from project_backup import delete_named_backup  # noqa: WPS433

        proj = self._project_dir(project_id)
        if not delete_named_backup(proj, backup_id):
            raise BadRequest(f"Backup {backup_id!r} not found.")

    def quick_save_backup(self, project_id: str) -> dict:
        from project_backup import quick_save  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, _, _ = self._backup_hooks(project_id)
        return quick_save(proj, db_export=prepare())

    def quick_restore_backup(self, project_id: str) -> dict:
        from project_backup import quick_restore  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, import_db, sync_artifacts = self._backup_hooks(project_id)
        return quick_restore(
            proj,
            db_export=prepare(),
            import_db=import_db,
            sync_artifacts=sync_artifacts,
        )

    def undo_backup_restore(self, project_id: str) -> dict:
        from project_backup import undo_quick_restore  # noqa: WPS433

        proj = self._project_dir(project_id)
        _, import_db, sync_artifacts = self._backup_hooks(project_id)
        return undo_quick_restore(
            proj,
            import_db=import_db,
            sync_artifacts=sync_artifacts,
        )

    # ----- Portable export / import

    def export_project_package(self, project_id: str) -> tuple[str, bytes]:
        from project_portable import build_package_bytes  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, _, _ = self._backup_hooks(project_id)
        db_data = prepare()
        s = self._load(project_id)
        title = s.metadata.get("title", project_id)
        data = build_package_bytes(proj, db_data, project_id=project_id, title=title)
        filename = f"{_slugify(title)}.novel-os.zip"
        return filename, data

    def import_project_package(self, zip_bytes: bytes) -> ProjectSummary:
        from project_portable import import_package_bytes  # noqa: WPS433

        def import_db(new_id: str, data: dict) -> None:
            db.import_project_data(new_id, data, allow_id_mismatch=True, remap_ids=True)

        def sync_artifacts(new_id: str) -> None:
            db.sync_artifacts_to_files(self.root, new_id)

        project_id, title = import_package_bytes(
            self.root,
            zip_bytes,
            import_db=import_db,
            sync_artifacts=sync_artifacts,
            slugify=_slugify,
        )
        s = self._load(project_id)
        return ProjectSummary(
            id=project_id,
            title=s.metadata.get("title", title),
            genre=s.metadata.get("genre", ""),
            chapter_count=len(s.chapters),
            status=s.metadata.get("status", "in_progress"),
        )

    # ----- Delete operations

    def delete_project(self, project_id: str) -> None:
        proj = self._project_dir(project_id)
        try:
            db.project_delete(project_id)
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(proj)

    def delete_chapter(self, project_id: str, number: int) -> None:
        s = self._load(project_id)
        if number not in s.chapters:
            raise ChapterNotFound(number)
        proj = self._project_dir(project_id)
        nnn = f"{number:03d}"
        for stage, path in self._stage_paths(project_id, number).items():
            if path.exists():
                path.unlink()
        for subdir, pattern in (
            ("sources", f"chapter_{nnn}.*"),
            ("feedback", f"chapter_{nnn}_*"),
        ):
            d = proj / "outputs" / subdir
            if d.is_dir():
                for f in d.glob(pattern):
                    f.unlink()
        s.delete_chapter(number)
        s.save_state()
        try:
            db.chapter_delete_all(project_id, number)
        except Exception:  # noqa: BLE001
            pass

    def delete_character(self, project_id: str, character_id: str) -> None:
        s = self._load(project_id)
        char = s.get_character(character_id)
        if char is None:
            raise CharacterNotFound(character_id)
        name = char.full_name
        s.delete_character(character_id)
        s.save_state()
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        prof = self._project_dir(project_id) / "outputs" / "characters" / f"{slug}.md"
        if prof.exists():
            prof.unlink()

    def delete_plot_thread(self, project_id: str, thread_id: str) -> None:
        s = self._load(project_id)
        if s.get_plot_thread(thread_id) is None:
            raise PlotThreadNotFound(thread_id)
        s.delete_plot_thread(thread_id)
        s.save_state()
