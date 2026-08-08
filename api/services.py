import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import db, richtext, tenancy
from .models import (
    ChapterDetail, ChapterStages, ChapterSummary, CharacterSummary, CodexEntryOut,
    ProjectDetail, ProjectSummary, RelationshipOut, StageDiff, StageProvenance,
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


# Job stage → (manuscript stage key, agent name)
# Approve only flips chapter status - it must never stamp Final (P3.3).
_PHASE_ARTIFACT: dict[str, tuple[str, str]] = {
    "plan_chapter": ("outline", "architect"),
    "write": ("draft", "scribe"),
    "edit": ("revised", "editor"),
}

# stage -> how to invoke it on an orchestrator with the given params
PHASES: dict[str, Callable[[object, dict], object]] = {
    "plan_outline": lambda o, p: o.plan_outline(int(p.get("chapters", 12)), int(p.get("words", 24000))),
    "plan_chapter": lambda o, p: o.plan_chapter(int(p["number"]), p.get("summary", ""), p.get("pov", "")),
    "write": lambda o, p: o.write_chapter(int(p["number"])),
    "edit": lambda o, p: o.edit_chapter(int(p["number"]), p.get("mode", "line")),
    "validate": lambda o, p: o.validate_chapter(int(p["number"])),
    "approve": lambda o, p: o.approve_chapter(int(p["number"])),
}


def _current_model_label() -> str:
    try:
        from core import studio_settings  # noqa: E402
        st = studio_settings.llm_status()
        return f"{st.get('provider', '')}:{st.get('model', '')}".strip(":")
    except Exception:  # noqa: BLE001
        return os.environ.get("NOVEL_OS_MODEL", "") or ""


def _slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "untitled"


def _genre_label(genres: list[str] | None, fallback: str = "") -> str:
    parts = [g.strip() for g in (genres or []) if g and g.strip()]
    if parts:
        return " · ".join(parts)
    return (fallback or "").strip()


def _normalize_genres(genres: list[str] | None, genre: str = "") -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for g in genres or []:
        t = g.strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    if not out and genre.strip():
        for part in genre.replace("/", "·").split("·"):
            t = part.strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                out.append(t)
    return out


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

    def __init__(self, root: Path, workspace: "db.Workspace | None" = None):
        self.root = Path(root)
        # None means the default workspace, whose projects live directly under
        # root exactly as they did before tenancy existed (PLAN.md P0.5).
        self.workspace = workspace

    @property
    def base_dir(self) -> Path:
        return tenancy.workspace_dir(self.root, self.workspace)

    # --- discovery
    def _project_dir(self, project_id: str) -> Path:
        try:
            d = tenancy.project_dir(self.root, project_id, self.workspace)
        except tenancy.TenancyError:
            # A malformed or escaping id is indistinguishable from a missing
            # project as far as a caller is concerned and leaks less.
            raise ProjectNotFound(project_id)
        if not (d / "outputs" / "state" / "story_state.json").exists():
            raise ProjectNotFound(project_id)
        return d

    def _load(self, project_id: str) -> StoryState:
        return StoryState(str(self._project_dir(project_id)))

    def list_projects(self) -> list[ProjectSummary]:
        out: list[ProjectSummary] = []
        base = self.base_dir
        if not base.exists():
            return out
        for child in sorted(base.iterdir()):
            state_file = child / "outputs" / "state" / "story_state.json"
            if not state_file.exists():
                continue
            s = StoryState(str(child))
            out.append(self._summary(child.name, s, state_file))
        return out

    def _summary(self, project_id: str, s: StoryState, state_file: Path | None = None) -> ProjectSummary:
        chapters = list(s.chapters.values())
        words = sum(c.word_count for c in chapters)
        drafted = sum(1 for c in chapters if c.status != "planned")
        updated = None
        if state_file and state_file.exists():
            updated = datetime.fromtimestamp(state_file.stat().st_mtime).isoformat()
        rating = s.metadata.get("content_rating", "general")
        if rating not in ("general", "mature"):
            rating = "general"
        genres = _normalize_genres(s.metadata.get("genres"), s.metadata.get("genre", ""))
        premise = str(s.metadata.get("premise") or s.story_bible.get("premise") or "")
        target = int(s.metadata.get("target_word_count") or 80000)
        session_target = int(s.metadata.get("session_word_target") or 1000)
        return ProjectSummary(
            id=project_id,
            title=s.metadata.get("title", project_id),
            genre=s.metadata.get("genre", "") or _genre_label(genres),
            chapter_count=len(chapters),
            status=s.metadata.get("status", "in_progress"),
            author=s.metadata.get("author", ""),
            word_count=words,
            drafted_count=drafted,
            content_rating=rating,
            updated_at=updated,
            genres=genres,
            premise=premise,
            target_word_count=max(0, target),
            session_word_target=max(0, session_target),
        )

    def project_detail(self, project_id: str) -> ProjectDetail:
        s = self._load(project_id)
        chapters = list(s.chapters.values())
        rating = s.metadata.get("content_rating", "general")
        if rating not in ("general", "mature"):
            rating = "general"
        genres = _normalize_genres(s.metadata.get("genres"), s.metadata.get("genre", ""))
        premise = str(s.metadata.get("premise") or s.story_bible.get("premise") or "")
        target = int(s.metadata.get("target_word_count") or 80000)
        session_target = int(s.metadata.get("session_word_target") or 1000)
        return ProjectDetail(
            id=project_id,
            title=s.metadata.get("title", project_id),
            genre=s.metadata.get("genre", "") or _genre_label(genres),
            author=s.metadata.get("author", ""),
            chapter_count=len(chapters),
            status=s.metadata.get("status", "in_progress"),
            style={
                "tone": s.style_profile.tone,
                "point_of_view": s.style_profile.point_of_view,
                "prose_style": s.style_profile.prose_style,
            },
            content_rating=rating,
            word_count=sum(c.word_count for c in chapters),
            genres=genres,
            premise=premise,
            target_word_count=max(0, target),
            session_word_target=max(0, session_target),
        )

    def update_project(self, project_id: str, *, content_rating: str | None = None,
                       title: str | None = None, genre: str | None = None,
                       genres: list[str] | None = None, premise: str | None = None,
                       target_word_count: int | None = None,
                       session_word_target: int | None = None) -> ProjectDetail:
        s = self._load(project_id)
        if content_rating is not None:
            if content_rating not in ("general", "mature"):
                raise BadRequest("content_rating must be 'general' or 'mature'")
            s.set_metadata("content_rating", content_rating)
        if title is not None and title.strip():
            s.set_metadata("title", title.strip())
        if genres is not None:
            normalized = _normalize_genres(genres)
            s.set_metadata("genres", normalized)
            s.set_metadata("genre", _genre_label(normalized, genre or ""))
            s.update_story_bible("genre", _genre_label(normalized, genre or ""))
        elif genre is not None:
            s.set_metadata("genre", genre.strip())
            s.set_metadata("genres", _normalize_genres(None, genre))
            s.update_story_bible("genre", genre.strip())
        if premise is not None:
            s.set_metadata("premise", premise.strip())
            s.update_story_bible("premise", premise.strip())
        if target_word_count is not None:
            if target_word_count < 0:
                raise BadRequest("target_word_count must be >= 0")
            s.set_metadata("target_word_count", int(target_word_count))
        if session_word_target is not None:
            if session_word_target < 0:
                raise BadRequest("session_word_target must be >= 0")
            s.set_metadata("session_word_target", int(session_word_target))
        s.save_state()
        return self.project_detail(project_id)

    def list_chapters(self, project_id: str) -> list[ChapterSummary]:
        s = self._load(project_id)
        return [
            ChapterSummary(
                number=c.number,
                title=c.title or "",
                status=c.status,
                word_count=c.word_count,
                pov=c.pov_character or "",
                target_word_count=int(c.target_word_count or 2500),
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
            target_word_count=int(c.target_word_count or 2500),
            outline=outline_path.read_text(encoding="utf-8") if outline_path.exists() else None,
            draft=draft_path.read_text(encoding="utf-8") if draft_path.exists() else None,
        )

    def list_characters(self, project_id: str) -> list[CharacterSummary]:
        s = self._load(project_id)
        return [
            CharacterSummary(
                id=c.id,
                full_name=c.full_name,
                role=c.role,
                portrait_media_id=getattr(c, "portrait_media_id", "") or "",
                portrait_url=(
                    f"/api/projects/{project_id}/media/{c.portrait_media_id}/raw"
                    if getattr(c, "portrait_media_id", "") else None
                ),
            )
            for c in s.get_all_characters()
        ]

    def list_codex(self, project_id: str, entry_type: str | None = None) -> list[CodexEntryOut]:
        """Unified Codex: characters + non-character entries, optional type filter."""
        from state_manager import CODEX_TYPES  # noqa: E402

        if entry_type and entry_type not in CODEX_TYPES:
            raise BadRequest(f"entry_type must be one of {CODEX_TYPES}")
        out: list[CodexEntryOut] = []
        if entry_type in (None, "character"):
            for c in self.list_characters(project_id):
                out.append(CodexEntryOut(
                    id=c.id,
                    entry_type="character",
                    name=c.full_name,
                    role=c.role,
                    portrait_media_id=c.portrait_media_id,
                    portrait_url=c.portrait_url,
                    summary="",
                    notes="",
                ))
        if entry_type != "character":
            s = self._load(project_id)
            for e in s.get_codex_entries(None if entry_type is None else entry_type):
                if e.entry_type == "character":
                    continue  # characters live in characters dict
                out.append(CodexEntryOut(
                    id=e.id,
                    entry_type=e.entry_type,
                    name=e.name,
                    summary=e.summary,
                    notes=e.notes,
                    tags=list(e.tags),
                    portrait_media_id=e.portrait_media_id,
                    portrait_url=(
                        f"/api/projects/{project_id}/media/{e.portrait_media_id}/raw"
                        if e.portrait_media_id else None
                    ),
                    fields=dict(e.fields),
                ))
        out.sort(key=lambda x: (x.entry_type, x.name.lower()))
        return out

    def search(self, project_id: str, q: str, *, limit: int = 24) -> list:
        """Keyword search over Codex + chapter titles (no embeddings).

        Scores exact/prefix/substring matches. Story state remains canonical;
        this is intentionally portable to Postgres FTS later behind the same API.
        """
        from .models import SearchHit  # local to avoid circulars at import time

        needle = (q or "").strip().lower()
        if len(needle) < 2:
            return []
        s = self._load(project_id)
        hits: list[SearchHit] = []

        def score_text(text: str) -> int:
            t = (text or "").lower()
            if not t:
                return 0
            if t == needle:
                return 100
            if t.startswith(needle):
                return 80
            if needle in t:
                return 60
            # token overlap
            tokens = [w for w in needle.split() if len(w) >= 2]
            if tokens and all(tok in t for tok in tokens):
                return 50
            return 0

        for c in s.get_all_characters():
            sc = max(score_text(c.full_name), score_text(c.role), score_text(c.notes[:200]))
            if sc:
                hits.append(SearchHit(
                    kind="character", id=c.id, label=c.full_name,
                    subtitle=c.role or "character", score=sc,
                ))

        for e in s.get_codex_entries():
            sc = max(score_text(e.name), score_text(e.summary), score_text(e.notes[:200]))
            if sc:
                hits.append(SearchHit(
                    kind=e.entry_type, id=e.id, label=e.name,
                    subtitle=(e.summary or e.entry_type)[:80], score=sc,
                ))

        for n, ch in s.chapters.items():
            num = int(n) if not isinstance(n, int) else n
            title = ch.title or f"Chapter {num}"
            sc = max(score_text(title), score_text(ch.pov_character or ""))
            binder = getattr(s, "binder", None)
            if binder is not None and hasattr(binder, "chapter_node"):
                node = binder.chapter_node(num)
                if node is not None:
                    sc = max(sc, score_text(getattr(node, "synopsis", "") or ""))
            if sc:
                hits.append(SearchHit(
                    kind="chapter", id=f"ch-{num}", label=title,
                    subtitle=f"Chapter {num}" + (f" · {ch.pov_character}" if ch.pov_character else ""),
                    chapter=num, score=sc,
                ))

        for edge in getattr(s, "relationships", {}).values():
            a = s.characters.get(edge.source_id)
            b = s.characters.get(edge.target_id)
            an = a.full_name if a else edge.source_id
            bn = b.full_name if b else edge.target_id
            label = f"{an} · {edge.label} · {bn}"
            sc = max(score_text(edge.label), score_text(an), score_text(bn), score_text(edge.notes[:120]))
            if sc:
                hits.append(SearchHit(
                    kind="relationship", id=edge.id, label=label,
                    subtitle="relationship", score=sc,
                ))

        hits.sort(key=lambda h: (-h.score, h.kind, h.label.lower()))
        return hits[: max(1, min(limit, 50))]

    def list_collections(self, project_id: str) -> list:
        from .models import CollectionOut
        s = self._load(project_id)
        return [
            CollectionOut(
                id=c.id, name=c.name, query=c.query,
                kinds=list(c.kinds), notes=c.notes,
            )
            for c in s.list_collections()
        ]

    def add_collection(
        self, project_id: str, name: str, query: str,
        kinds: list[str] | None = None, notes: str = "",
    ) -> list:
        q = (query or "").strip()
        if len(q) < 2:
            raise BadRequest("Query must be at least 2 characters.")
        s = self._load(project_id)
        s.add_collection(name=name or q, query=q, kinds=kinds or [], notes=notes)
        return self.list_collections(project_id)

    def delete_collection(self, project_id: str, collection_id: str) -> None:
        s = self._load(project_id)
        if not s.delete_collection(collection_id):
            raise BadRequest(f"Collection '{collection_id}' not found")

    def collection_results(self, project_id: str, collection_id: str, *, limit: int = 40) -> list:
        s = self._load(project_id)
        col = s.collections.get(collection_id)
        if not col:
            raise BadRequest(f"Collection '{collection_id}' not found")
        hits = self.search(project_id, col.query, limit=limit)
        if col.kinds:
            allowed = {k.lower() for k in col.kinds}
            hits = [h for h in hits if h.kind.lower() in allowed]
        return hits

    def add_codex_entry(self, project_id: str, entry_type: str, name: str,
                        summary: str = "", notes: str = "", role: str = "supporting",
                        tags: list[str] | None = None) -> list[CodexEntryOut]:
        name = name.strip()
        if not name:
            raise BadRequest("Name is required.")
        from state_manager import CODEX_TYPES, CodexEntry  # noqa: E402

        if entry_type not in CODEX_TYPES:
            raise BadRequest(f"entry_type must be one of {CODEX_TYPES}")
        if entry_type == "character":
            self.add_character(project_id, name, role)
            return self.list_codex(project_id, "character")

        s = self._load(project_id)
        n = len(s.codex) + 1
        eid = f"{entry_type[:3]}-{n:03d}"
        while eid in s.codex:
            n += 1
            eid = f"{entry_type[:3]}-{n:03d}"
        s.add_codex_entry(CodexEntry(
            id=eid,
            entry_type=entry_type,
            name=name,
            summary=summary.strip(),
            notes=notes.strip(),
            tags=list(tags or []),
        ))
        return self.list_codex(project_id, entry_type)

    def codex_proposals(self, project_id: str, min_mentions: int = 3,
                        limit: int = 60) -> list[dict]:
        """Candidate Codex entries found in the manuscript (PLAN.md P2.2).

        Read-only by construction: this proposes, it never writes. Accepting a
        proposal goes through the ordinary `add_codex_entry` path so there is
        exactly one way an entry can come into being.

        Extraction is deterministic text analysis, so importing a finished
        manuscript is instant and free - the friction it removes is having to
        re-type a cast the draft already contains.
        """
        from codex_extract import extract_proposals, known_names_from_state  # noqa: E402

        s = self._load(project_id)
        chapters: dict[int, str] = {}
        for number in sorted(s.chapters):
            paths = self._stage_paths(project_id, number)
            # Prefer the most finished prose available for this chapter.
            for stage in ("final", "revised", "draft"):
                text = _read(paths[stage])
                if text:
                    chapters[number] = text
                    break

        if not chapters:
            return []
        return [
            p.to_dict() for p in extract_proposals(
                chapters,
                known_names=known_names_from_state(s),
                min_mentions=max(1, min_mentions),
                limit=max(1, min(limit, 200)),
            )
        ]

    def set_portrait(self, project_id: str, entry_id: str, media_id: str,
                     entry_type: str = "character") -> CodexEntryOut:
        """Attach a media id as portrait, or clear when media_id is empty."""
        media_id = (media_id or "").strip()
        if media_id:
            m = db.media_get(project_id, media_id)
            if m is None:
                raise BadRequest("Media not found for this project.")

        s = self._load(project_id)
        if entry_type == "character" or entry_id in s.characters:
            char = s.set_character_portrait(entry_id, media_id)
            if char is None:
                raise BadRequest("Character not found.")
            return next(e for e in self.list_codex(project_id, "character") if e.id == entry_id)

        entry = s.codex.get(entry_id)
        if entry is None:
            raise BadRequest("Codex entry not found.")
        s.update_codex_entry(entry_id, portrait_media_id=media_id)
        return next(e for e in self.list_codex(project_id, entry.entry_type) if e.id == entry_id)

    def _entry_name(self, project_id: str, entry_id: str) -> str:
        s = self._load(project_id)
        if entry_id in s.characters:
            return s.characters[entry_id].full_name
        e = s.codex.get(entry_id)
        return e.name if e else entry_id

    def list_relationships(self, project_id: str, entry_id: str | None = None) -> list[RelationshipOut]:
        s = self._load(project_id)
        out: list[RelationshipOut] = []
        for e in s.list_relationships(entry_id):
            out.append(RelationshipOut(
                id=e.id,
                source_id=e.source_id,
                target_id=e.target_id,
                label=e.label,
                kind=e.kind,
                strength=e.strength,
                status=e.status,
                since_chapter=e.since_chapter,
                notes=e.notes,
                directed=e.directed,
                source_name=self._entry_name(project_id, e.source_id),
                target_name=self._entry_name(project_id, e.target_id),
            ))
        return out

    def add_relationship(self, project_id: str, source_id: str, target_id: str,
                         label: str = "unknown", notes: str = "",
                         directed: bool = False, since_chapter: int = 0) -> list[RelationshipOut]:
        s = self._load(project_id)
        known = set(s.characters) | set(s.codex)
        if source_id not in known or target_id not in known:
            raise BadRequest("Both ends must be Codex entries (characters or typed entries).")
        try:
            s.add_relationship(
                source_id, target_id, label,
                notes=notes, directed=directed, since_chapter=since_chapter,
            )
        except ValueError as e:
            raise BadRequest(str(e)) from e
        return self.list_relationships(project_id)

    def delete_relationship(self, project_id: str, edge_id: str) -> None:
        s = self._load(project_id)
        if not s.delete_relationship(edge_id):
            raise BadRequest("Relationship not found.")

    def binder_tree(self, project_id: str) -> list[dict]:
        """The document tree, nested (PLAN.md P0.4 / P4).

        Projects predating the binder migrate on load. Flat chapter endpoints
        stay authoritative for the writing path (chapter numbers unchanged).
        """
        return self._load(project_id).binder.to_tree()

    def move_binder_node(
        self,
        project_id: str,
        node_id: str,
        parent_id: str | None,
        index: int,
    ) -> list[dict]:
        """Move a binder node among siblings (or to a new parent). Persists order."""
        from document_tree import BinderError  # noqa: E402

        s = self._load(project_id)
        try:
            s.binder.move(node_id, parent_id, index=index)
        except BinderError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        return s.binder.to_tree()

    def patch_binder_node(self, project_id: str, node_id: str, fields: dict) -> list[dict]:
        """Patch corkboard/outliner metadata on a binder node."""
        from document_tree import BinderError  # noqa: E402

        allowed = {"synopsis", "title", "label", "status", "pov", "target_words"}
        patch = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not patch:
            raise BadRequest("No updatable fields provided.")

        s = self._load(project_id)
        try:
            s.binder.update(node_id, **patch)
        except BinderError as e:
            raise BadRequest(str(e)) from e

        # Keep flat chapter title/pov in sync when chapter nodes change.
        node = s.binder.get(node_id)
        if node is not None and node.type == "chapter" and node.chapter_number is not None:
            ch = s.chapters.get(node.chapter_number)
            if ch is not None:
                if "title" in patch:
                    ch.title = str(patch["title"])
                if "pov" in patch:
                    ch.pov_character = str(patch["pov"])
                if "status" in patch and patch["status"]:
                    # Binder status is Scrivener-ish; map lightly onto chapter status.
                    mapped = {
                        "to_do": "planned",
                        "proposed": "outlined",
                        "in_review": "edited",
                        "final": "approved",
                    }.get(str(patch["status"]), ch.status)
                    ch.status = mapped

        s.save_state()
        return s.binder.to_tree()

    def refresh_synopsis(self, project_id: str, number: int) -> dict:
        """Ask the Architect for a corkboard synopsis and save it on the binder node."""
        from prose_sanitize import sanitize_manuscript, strip_em_dashes  # noqa: E402

        self.ensure_chapter(project_id, number)
        s = self._load(project_id)
        s.sync_binder()
        node = s.binder.chapter_node(number)
        if node is None:
            raise BadRequest(f"No binder node for chapter {number}.")

        ch = s.chapters.get(number)
        paths = self._stage_paths(project_id, number)
        outline = _read(paths["outline"]) or ""
        prose = (
            _read(paths["final"])
            or _read(paths["revised"])
            or _read(paths["draft"])
            or ""
        )
        outline_clean, _ = sanitize_manuscript(outline)
        prose_clean, _ = sanitize_manuscript(prose)
        title = (node.title or (ch.title if ch else "") or f"Chapter {number}").strip()
        pov = (node.pov or (ch.pov_character if ch else "") or "").strip()
        genre = s.metadata.get("genre", "")
        premise = str(s.metadata.get("premise") or "")
        existing = (node.synopsis or "").strip()

        context_bits = []
        if outline_clean.strip():
            context_bits.append(f"## Outline\n{outline_clean.strip()[:2200]}")
        if prose_clean.strip():
            context_bits.append(f"## Manuscript excerpt\n{prose_clean.strip()[:1800]}")
        if not context_bits and existing:
            context_bits.append(f"## Current synopsis\n{existing}")
        context = "\n\n".join(context_bits) or (
            "(No outline or manuscript yet — invent a fitting beat from the premise.)"
        )

        prompt = f"""# ARCHITECT TASK: Corkboard synopsis

Write a **corkboard index-card synopsis** for one chapter of "{s.metadata.get('title', project_id)}" ({genre}).
Premise: {premise or "[none]"}

Chapter {number}: {title}
POV: {pov or "[unspecified]"}

{context}

## Rules
- Return **only** 2–3 tight sentences (max ~60 words).
- Capture the chapter goal and one turning beat a Scrivener corkboard would show.
- No markdown headings, bullets, quotes, or labels like "Synopsis:".
- **Never use the em dash character (—).** Prefer commas or periods.
"""

        source = "architect"
        model = ""
        synopsis = ""
        try:
            orch = build_orchestrator(str(self._project_dir(project_id)))
            raw = orch._get_llm().run_agent("architect", prompt)
            model = _current_model_label()
            synopsis, _ = sanitize_manuscript(raw)
            synopsis = strip_em_dashes(synopsis).strip()
            if synopsis.startswith("```"):
                synopsis = re.sub(r"^```\w*\n?", "", synopsis)
                synopsis = re.sub(r"\n?```$", "", synopsis).strip()
            parts = re.split(r"(?<=[.!?])\s+", synopsis)
            synopsis = " ".join(parts[:3]).strip()
        except Exception:  # noqa: BLE001
            source = "heuristic"
            synopsis = self._heuristic_synopsis(outline_clean, prose_clean, title, existing)

        if not synopsis:
            synopsis = self._heuristic_synopsis(outline_clean, prose_clean, title, existing)
            source = "heuristic"

        s.binder.update(node.id, synopsis=synopsis)
        s.save_state()
        return {
            "chapter": number,
            "node_id": node.id,
            "synopsis": synopsis,
            "source": source,
            "model": model,
        }

    def refresh_outliner_metrics(self, project_id: str, chapter: int | None = None) -> dict:
        """Score tension / emotion / pacing per chapter; persist on binder.derived."""
        from chapter_metrics import score_chapter  # noqa: E402

        s = self._load(project_id)
        s.sync_binder()
        if chapter is not None and chapter not in s.chapters:
            raise ChapterNotFound(chapter)
        numbers = [chapter] if chapter is not None else sorted(s.chapters.keys())

        rows = []
        for number in numbers:
            node = s.binder.chapter_node(number)
            if node is None:
                continue
            paths = self._stage_paths(project_id, number)
            text = (
                _read(paths["final"])
                or _read(paths["revised"])
                or _read(paths["draft"])
                or ""
            )
            outline = _read(paths["outline"]) or ""
            metrics = score_chapter(
                text,
                synopsis=node.synopsis or "",
                outline=outline,
            )
            derived = dict(node.derived or {})
            derived.update({
                "tension": metrics["tension"],
                "emotional_intensity": metrics["emotional_intensity"],
                "pacing": metrics["pacing"],
                "source": metrics["source"],
                "metrics_word_count": metrics["word_count"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            s.binder.update(node.id, derived=derived)
            rows.append({
                "chapter": number,
                "node_id": node.id,
                "tension": metrics["tension"],
                "emotional_intensity": metrics["emotional_intensity"],
                "pacing": metrics["pacing"],
                "source": metrics["source"],
                "word_count": metrics["word_count"],
            })

        s.save_state()
        return {"chapters": rows, "source": "heuristic"}

    @staticmethod
    def _heuristic_synopsis(
        outline: str, prose: str, title: str, existing: str,
    ) -> str:
        """Offline / LLM-failure corkboard text from outline goal or prose head."""
        if existing.strip():
            return existing.strip()
        goal = ""
        m = re.search(
            r"##\s*Chapter Goal\s*\n+(.+?)(?:\n##|\Z)",
            outline or "",
            flags=re.I | re.S,
        )
        if m:
            goal = re.sub(r"\s+", " ", m.group(1)).strip()
        if goal:
            return goal[:320]
        head = re.sub(r"\s+", " ", (prose or "").strip())
        if head:
            return (head[:240] + ("…" if len(head) > 240 else "")).strip()
        return f"{title}: beat to be planned."

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
            db.ingest_project(self.base_dir, project_id)
        except Exception:  # noqa: BLE001 - ingest is best-effort
            pass
        p = self._stage_paths(project_id, number)
        # Sanitize for display: legacy files may still contain CHAPTER HTML
        # headers, em dashes, and agent bookkeeping blocks.
        from prose_sanitize import sanitize_manuscript  # noqa: E402

        def _clean(raw: str | None) -> str | None:
            if raw is None:
                return None
            body, _ = sanitize_manuscript(raw)
            return body

        provenance: dict[str, StageProvenance] = {}
        for key in ("outline", "draft", "revised", "final"):
            art = db.get_artifact(project_id, number, key)
            if art is None:
                continue
            provenance[key] = StageProvenance(
                produced_by_agent=art.produced_by_agent or "",
                produced_by_model=art.produced_by_model or "",
                reviewed_by=art.reviewed_by or "",
                reviewed_at=art.reviewed_at or "",
                updated_at=art.updated_at or "",
                word_count=art.word_count or 0,
            )

        return ChapterStages(
            number=number,
            status=c.status,
            outline=_read(p["outline"]),
            draft=_clean(_read(p["draft"])),
            revised=_clean(_read(p["revised"])),
            final=_clean(_read(p["final"])),
            continuity=c.continuity_checks or None,
            provenance=provenance,
        )

    def stage_diff(
        self, project_id: str, number: int, from_stage: str, to_stage: str,
    ) -> StageDiff:
        """Line-oriented diff between two pipeline stages (story-facing summary)."""
        allowed = {"outline", "draft", "revised", "final"}
        if from_stage not in allowed or to_stage not in allowed:
            raise BadRequest(f"Stages must be one of {sorted(allowed)}.")
        self.ensure_chapter(project_id, number)
        paths = self._stage_paths(project_id, number)
        from prose_sanitize import sanitize_manuscript  # noqa: E402

        def _body(stage: str) -> str:
            raw = _read(paths[stage]) or ""
            clean, _ = sanitize_manuscript(raw)
            return clean.strip()

        a = _body(from_stage)
        b = _body(to_stage)
        a_lines = [ln for ln in a.splitlines() if ln.strip()]
        b_lines = [ln for ln in b.splitlines() if ln.strip()]
        a_set = set(a_lines)
        b_set = set(b_lines)
        added = [ln for ln in b_lines if ln not in a_set][:40]
        removed = [ln for ln in a_lines if ln not in b_set][:40]
        aw, bw = len(a.split()), len(b.split())
        delta = bw - aw
        summary = (
            f"{to_stage.title()} is {abs(delta)} words {'longer' if delta >= 0 else 'shorter'} "
            f"than {from_stage}; {len(added)} new line(s), {len(removed)} removed."
        )
        return StageDiff(
            from_stage=from_stage,
            to_stage=to_stage,
            from_words=aw,
            to_words=bw,
            added_lines=added,
            removed_lines=removed,
            summary=summary,
        )

    def _commit_final(self, project_id: str, number: int, text: str,
                      doc: dict | None = None) -> int:
        """Write final.md atomically, update chapter word_count + timestamp, persist.

        When a ProseMirror document is supplied it is canonical, and `text` is
        its markdown projection. Markdown-only writers (promote, restore, the
        legacy PUT) convert on the way in so `doc_json` never drifts behind the
        file on disk. The `.md` file is still written either way, because that
        is what the agents and `core/orchestrator.py` read and because it
        means a conversion bug can never leave a manuscript unreadable.
        """
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        if doc is None:
            doc = richtext.from_markdown(text) if text else richtext.empty_doc()
        _atomic_write(self._stage_paths(project_id, number)["final"], text)
        wc = len(text.split())
        c.word_count = wc
        c.last_modified = datetime.now(timezone.utc).isoformat()
        s.save_state()
        # DB is the system-of-record for the human-owned Final
        try:
            db.upsert_artifact(
                project_id, number, "final", text,
                doc_json=json.dumps(doc, ensure_ascii=False),
                produced_by_agent="author",
                produced_by_model="",
                reviewed_by="author",
                reviewed_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception:  # noqa: BLE001
            pass
        return wc

    def get_final_doc(self, project_id: str, number: int) -> dict:
        """The Final as a ProseMirror document.

        Migration is lazy: a Final that predates P1 has no stored document, so
        it is converted from its markdown on read. Nothing is rewritten until
        the writer actually saves, so an unreviewed conversion never overwrites
        the manuscript on disk.

        Exception: spaced-hyphen corruption from a past sanitize bug is healed
        and persisted on read so the editor never shows mangled prose.
        """
        from prose_sanitize import repair_spaced_hyphen_corruption, sanitize_manuscript  # noqa: E402

        self.ensure_chapter(project_id, number)
        stored = db.get_artifact_doc(project_id, number, "final")
        if stored:
            try:
                doc = json.loads(stored)
                md = richtext.to_markdown(doc)
                if repair_spaced_hyphen_corruption(md) != md:
                    clean, _ = sanitize_manuscript(md)
                    clean_doc = richtext.from_markdown(clean) if clean else richtext.empty_doc()
                    self._commit_final(project_id, number, clean, doc=clean_doc)
                    return clean_doc
                return doc
            except json.JSONDecodeError:
                pass  # corrupt JSON: fall back to the markdown, which is intact
        text = self.get_final_text(project_id, number)
        if text and repair_spaced_hyphen_corruption(text) != text:
            clean, _ = sanitize_manuscript(text)
            clean_doc = richtext.from_markdown(clean) if clean else richtext.empty_doc()
            self._commit_final(project_id, number, clean, doc=clean_doc)
            return clean_doc
        return richtext.from_markdown(text) if text else richtext.empty_doc()

    def save_final_doc(self, project_id: str, number: int, doc: dict) -> int:
        """Save a ProseMirror document as Final, projecting markdown for agents."""
        from prose_sanitize import (  # noqa: E402
            sanitize_manuscript, apply_header_to_chapter, strip_em_dashes,
        )
        # House style is applied to the document's text nodes, not by parsing a
        # cleaned markdown string back into a document: that round trip drops
        # every mark markdown cannot express, which would wipe pending track
        # changes on the first save.
        clean_doc = richtext.map_text(doc, strip_em_dashes)
        md = richtext.to_markdown(clean_doc)
        clean, meta = sanitize_manuscript(md)
        s = self._load(project_id)
        apply_header_to_chapter(s.chapters.get(number), meta)
        s.save_state()
        return self._commit_final(project_id, number, clean, doc=clean_doc)

    def promote_final(self, project_id: str, number: int, force: bool = False) -> str:
        """Seed Final from revised||draft. Idempotent: never clobbers a human edit unless forced.

        P3.3: prefers a human-reviewed source. Use force=True to promote an
        unreviewed AI stage (author override).
        """
        p = self._stage_paths(project_id, number)
        if p["final"].exists() and not force:
            return p["final"].read_text(encoding="utf-8")

        source_stage = "revised" if p["revised"].exists() else ("draft" if p["draft"].exists() else None)
        if source_stage is None:
            raise NoSourceArtifact(number)

        if not force:
            art = db.get_artifact(project_id, number, source_stage)
            # Legacy file-only stages (no DB row) stay promotable. Once
            # provenance exists, require Accept (or force=true override).
            if art is not None and not (art.reviewed_by or "").strip():
                raise BadRequest(
                    f"Accept the {source_stage} stage first (or promote with force=true)."
                )

        source = _read(p[source_stage])
        if source is None:
            raise NoSourceArtifact(number)
        from prose_sanitize import sanitize_manuscript  # noqa: E402
        clean, meta = sanitize_manuscript(source)
        s = self._load(project_id)
        ch = s.chapters.get(number)
        if ch is not None:
            from prose_sanitize import apply_header_to_chapter  # noqa: E402
            apply_header_to_chapter(ch, meta)
            s.save_state()
        self._commit_final(project_id, number, clean)
        return clean

    def review_stage(
        self, project_id: str, number: int, stage: str, decision: str,
    ) -> dict:
        """Accept or reject an AI draft/revised stage (PLAN.md P3.3).

        Accept stamps reviewed_* and promotes into Final.
        Reject leaves the stage as unreviewed provenance and does not touch Final.
        """
        stage = (stage or "").strip().lower()
        decision = (decision or "").strip().lower()
        if stage not in ("draft", "revised"):
            raise BadRequest("Only draft and revised stages can be reviewed.")
        if decision not in ("accept", "reject"):
            raise BadRequest("Decision must be 'accept' or 'reject'.")

        self.ensure_chapter(project_id, number)
        path = self._stage_paths(project_id, number)[stage]
        text = _read(path)
        if not text:
            raise BadRequest(f"No {stage} text to review.")

        now = datetime.now(timezone.utc).isoformat()
        if decision == "reject":
            # Keep immutable AI output; clear any prior review stamp.
            db.upsert_artifact(
                project_id, number, stage, text,
                reviewed_by="",
                reviewed_at="",
            )
            return {
                "stage": stage,
                "decision": "reject",
                "reviewed_by": "",
                "reviewed_at": "",
                "promoted_final": False,
                "message": f"{stage.title()} kept as unreviewed provenance. Final unchanged.",
            }

        # Accept
        art = db.get_artifact(project_id, number, stage)
        model = (art.produced_by_model if art else "") or ""
        agent = (art.produced_by_agent if art else "") or (
            "scribe" if stage == "draft" else "editor"
        )
        db.upsert_artifact(
            project_id, number, stage, text,
            produced_by_agent=agent,
            produced_by_model=model,
            reviewed_by="author",
            reviewed_at=now,
        )

        s = self._load(project_id)
        ch = s.chapters.get(number)
        if ch is not None:
            # Binder maps edited/validated → in_review
            ch.status = "edited" if stage == "draft" else "validated"
            ch.last_modified = now
            s.save_state()

        # Human path into Final (agents never write Final).
        self.promote_final(project_id, number, force=True)
        return {
            "stage": stage,
            "decision": "accept",
            "reviewed_by": "author",
            "reviewed_at": now,
            "promoted_final": True,
            "message": f"{stage.title()} accepted and promoted to Final.",
        }

    def save_final(self, project_id: str, number: int, text: str) -> int:
        from prose_sanitize import sanitize_manuscript, apply_header_to_chapter  # noqa: E402
        clean, meta = sanitize_manuscript(text)
        s = self._load(project_id)
        ch = s.chapters.get(number)
        apply_header_to_chapter(ch, meta)
        s.save_state()
        return self._commit_final(project_id, number, clean)

    def continue_paragraph(self, project_id: str, number: int, instruction: str) -> dict:
        """Scribe writes the next paragraph from an author instruction (chat)."""
        instruction = (instruction or "").strip()
        if not instruction:
            raise BadRequest("Instruction is required.")
        from prose_sanitize import sanitize_manuscript, strip_em_dashes  # noqa: E402

        self.ensure_chapter(project_id, number)
        paths = self._stage_paths(project_id, number)
        # Prefer Final, then revised, then draft as context.
        context = (
            _read(paths["final"])
            or _read(paths["revised"])
            or _read(paths["draft"])
            or ""
        )
        context, _ = sanitize_manuscript(context)
        tail = context[-2500:] if context else "(Chapter is empty open with a strong first line.)"
        s = self._load(project_id)
        title = s.metadata.get("title", project_id)
        genre = s.metadata.get("genre", "")
        premise = str(s.metadata.get("premise") or "")
        chapter = s.chapters.get(number)
        pov = (chapter.pov_character if chapter else "") or ""
        location = (chapter.location if chapter else "") or ""
        try:
            from context_pack import build_context_pack, format_context_pack  # noqa: E402
            pack_md = format_context_pack(
                build_context_pack(s, number, purpose="continue"), max_chars=3000,
            )
        except Exception:
            pack_md = ""

        prompt = f"""# CONTINUE WRITING one paragraph only

You are the Scribe for "{title}" ({genre}).
Premise: {premise or "[none]"}
Chapter {number} POV: {pov or "[unspecified]"} · Location: {location or "[unspecified]"}

{pack_md}

## Current manuscript ending (context do not repeat)
```
{tail}
```

## Author instruction for what happens next
{instruction}

## Rules
- Write **exactly one** new paragraph (or a short beat of 2–4 sentences if dialogue needs a reply).
- Match the voice, tense, and POV of the context.
- **Never use the em dash character (—).** Use commas, periods, colons, or spaced hyphens (` - `).
- No HTML chapter headers. No [SCRIBE_STATE_UPDATE] block. No title lines. No commentary.
- Output only the new prose paragraph.
"""
        orch = build_orchestrator(str(self._project_dir(project_id)))
        try:
            raw = orch._get_llm().run_agent("scribe", prompt)
        except Exception as e:  # noqa: BLE001
            raise BadRequest(f"LLM continue failed: {e}") from e
        paragraph, _ = sanitize_manuscript(raw)
        paragraph = strip_em_dashes(paragraph).strip()
        # If the model still wrapped in quotes/fences, peel one layer
        if paragraph.startswith("```"):
            paragraph = re.sub(r"^```\w*\n?", "", paragraph)
            paragraph = re.sub(r"\n?```$", "", paragraph).strip()
        return {
            "paragraph": paragraph,
            "instruction": instruction,
            "word_count": len(paragraph.split()),
        }

    # In-memory consequence previews (single-user). Keyed by preview_id.
    _consequence_previews: dict[str, dict] = {}

    def preview_consequence(
        self,
        project_id: str,
        number: int,
        selection: str,
        instruction: str,
        *,
        before_context: str = "",
        after_context: str = "",
    ) -> dict:
        """Rewrite a selected span and compute deterministic + predicted ripple."""
        import uuid
        from continuity_engine import run_all  # noqa: E402
        from consequence import (  # noqa: E402
            diff_findings, extract_predicted, extract_rewritten,
        )
        from prose_sanitize import sanitize_manuscript, strip_em_dashes  # noqa: E402
        from state_parser import apply_to_state, parse_scribe  # noqa: E402

        selection = (selection or "").strip()
        instruction = (instruction or "").strip()
        if not selection:
            raise BadRequest("Select some text to rewrite.")
        if not instruction:
            raise BadRequest("Instruction is required.")

        self.ensure_chapter(project_id, number)
        s = self._load(project_id)
        title = s.metadata.get("title", project_id)
        genre = s.metadata.get("genre", "")
        chapter = s.chapters.get(number)
        pov = (chapter.pov_character if chapter else "") or ""
        location = (chapter.location if chapter else "") or ""
        try:
            from context_pack import build_context_pack, format_context_pack  # noqa: E402
            codex = format_context_pack(
                build_context_pack(s, number, purpose="consequence"), max_chars=2500,
            )
        except Exception:
            codex = s.format_codex_block(max_chars=2000)

        before_ctx = (before_context or "")[-800:]
        after_ctx = (after_context or "")[:800]

        prompt = f"""# REWRITE SPAN consequence preview

You are the Scribe for "{title}" ({genre}).
Chapter {number} POV: {pov or "[unspecified]"} · Location: {location or "[unspecified]"}

{codex if codex else ""}

## Context before selection
```
{before_ctx or "(start)"}
```

## Selection to rewrite
```
{selection}
```

## Context after selection
```
{after_ctx or "(end)"}
```

## Author instruction
{instruction}

## Output format (strict)
1. Put the rewritten selection only inside:
[REWRITTEN]
…rewritten prose matching voice/tense/POV…
[/REWRITTEN]

2. Then a state block for world changes implied by the rewrite (use None if none):
[SCRIBE_STATE_UPDATE]
Characters_Present: …
Key_Events: …
Emotional_Shifts: …
New_Information_Revealed: …
Foreshadowing_Planted: …
[/SCRIBE_STATE_UPDATE]

3. Then AI guesses that continuity checks cannot prove (label them clearly):
[PREDICTED_CONSEQUENCES]
- …
[/PREDICTED_CONSEQUENCES]

## Rules
- Rewrite only the selection; do not continue past it.
- **Never use the em dash character.** Use commas, periods, colons, or spaced hyphens (` - `).
- No HTML chapter headers. No commentary outside the tagged blocks.
"""
        orch = build_orchestrator(str(self._project_dir(project_id)))
        try:
            raw = orch._get_llm().run_agent("scribe", prompt)
        except Exception as e:  # noqa: BLE001
            raise BadRequest(f"LLM rewrite failed: {e}") from e

        rewritten = extract_rewritten(raw)
        rewritten, _ = sanitize_manuscript(rewritten)
        rewritten = strip_em_dashes(rewritten).strip()
        if rewritten.startswith("```"):
            rewritten = re.sub(r"^```\w*\n?", "", rewritten)
            rewritten = re.sub(r"\n?```$", "", rewritten).strip()
        if not rewritten:
            raise BadRequest("Scribe returned an empty rewrite.")

        predicted_msgs = extract_predicted(raw)
        state_delta = parse_scribe(raw) or {}

        proj = self._project_dir(project_id)
        before = [f.to_dict() for f in run_all(s, project_path=proj, as_of_chapter=number)]
        changelog: list[str] = []
        if state_delta:
            # Dry-apply on the in-memory state; never save_state during preview.
            changelog = apply_to_state(s, number, state_delta, source="consequence_preview")
        after = [f.to_dict() for f in run_all(s, project_path=proj, as_of_chapter=number)]
        deterministic = diff_findings(before, after)

        preview_id = uuid.uuid4().hex
        payload = {
            "preview_id": preview_id,
            "project_id": project_id,
            "chapter": number,
            "selection": selection,
            "instruction": instruction,
            "rewritten": rewritten,
            "state_delta": state_delta,
            "changelog": changelog,
            "deterministic": deterministic,
            "predicted": [{"message": m, "kind": "predicted"} for m in predicted_msgs],
            "word_count": len(rewritten.split()),
        }
        ProjectService._consequence_previews[preview_id] = payload
        # Cap cache so long sessions do not grow forever
        if len(ProjectService._consequence_previews) > 40:
            oldest = next(iter(ProjectService._consequence_previews))
            ProjectService._consequence_previews.pop(oldest, None)
        return {k: v for k, v in payload.items() if k not in ("project_id", "chapter")}

    def accept_consequence(
        self,
        project_id: str,
        number: int,
        preview_id: str,
        rewritten: str,
        doc: dict,
        state_delta: dict | None = None,
    ) -> dict:
        """Commit Final doc + world-state delta from a consequence preview."""
        from continuity_engine import run_all  # noqa: E402
        from prose_sanitize import sanitize_manuscript, apply_header_to_chapter, strip_em_dashes  # noqa: E402
        from state_parser import apply_to_state  # noqa: E402

        cached = ProjectService._consequence_previews.get(preview_id)
        if cached is None:
            raise BadRequest("Preview expired. Run Rewrite again.")
        if cached.get("project_id") != project_id or cached.get("chapter") != number:
            raise BadRequest("Preview does not match this chapter.")

        rewritten = strip_em_dashes(sanitize_manuscript(rewritten or "")[0]).strip()
        if not rewritten:
            raise BadRequest("Rewritten text is empty.")

        delta = state_delta if state_delta is not None else (cached.get("state_delta") or {})
        md = richtext.to_markdown(doc)
        clean, meta = sanitize_manuscript(md)
        s = self._load(project_id)
        apply_header_to_chapter(s.chapters.get(number), meta)
        changelog: list[str] = []
        if delta:
            changelog = apply_to_state(s, number, delta, source="consequence_accept")

        clean_doc = richtext.from_markdown(clean) if clean else richtext.empty_doc()
        wc = self._commit_final(project_id, number, clean, doc=clean_doc)
        s.save_state()
        ProjectService._consequence_previews.pop(preview_id, None)

        finding_dicts = [
            f.to_dict()
            for f in run_all(s, project_path=self._project_dir(project_id), as_of_chapter=number)
        ]
        return {
            "final": {
                "doc": clean_doc,
                "markdown": clean,
                "word_count": wc,
            },
            "changelog": changelog,
            "continuity": {
                "findings": finding_dicts,
                "critical": sum(1 for f in finding_dicts if f.get("severity") == "critical"),
                "warning": sum(1 for f in finding_dicts if f.get("severity") == "warning"),
                "info": sum(1 for f in finding_dicts if f.get("severity") == "info"),
            },
        }

    # ----- Tier 0: create / edit the world

    def create_project(self, title: str, genre: str = "", author: str = "",
                       genres: list[str] | None = None, premise: str = "") -> ProjectSummary:
        title = title.strip()
        if not title:
            raise BadRequest("Title is required.")
        normalized = _normalize_genres(genres, genre)
        label = _genre_label(normalized, genre)
        slug = _slugify(title)
        base = self.base_dir
        folder = base / slug
        n = 2
        while (folder / "outputs" / "state" / "story_state.json").exists():
            folder = base / f"{slug}-{n}"
            n += 1
        folder.mkdir(parents=True, exist_ok=True)
        build_orchestrator(str(folder)).init_project(title, label or "Fiction", author)
        db.project_claim(folder.name, self.workspace.id if self.workspace
                         else tenancy.DEFAULT_WORKSPACE_ID)
        s = StoryState(str(folder))
        if normalized:
            s.set_metadata("genres", normalized)
            s.set_metadata("genre", label)
            s.update_story_bible("genre", label)
        if premise.strip():
            s.set_metadata("premise", premise.strip())
            s.update_story_bible("premise", premise.strip())
            # Seed story bible markdown with the author's brief
            bible = folder / "outputs" / "story_bible.md"
            if bible.exists():
                text = bible.read_text(encoding="utf-8")
                if "## Premise" not in text:
                    text = text.replace(
                        f"## 📚 Genre\n{label or 'Fiction'}\n",
                        f"## 📚 Genre\n{label or 'Fiction'}\n\n## Premise\n{premise.strip()}\n",
                        1,
                    )
                    bible.write_text(text, encoding="utf-8")
        s.save_state()
        return self._summary(folder.name, s, folder / "outputs" / "state" / "story_state.json")

    def create_sample_project(self) -> ProjectSummary:
        """Seed a tiny demo manuscript for first-run tour (idempotent by slug)."""
        from state_manager import Character, CodexEntry, ChapterState  # noqa: E402

        slug = "glass-harbor-sample"
        existing = self.base_dir / slug
        if (existing / "outputs" / "state" / "story_state.json").exists():
            s = StoryState(str(existing))
            return self._summary(slug, s, existing / "outputs" / "state" / "story_state.json")

        summary = self.create_project(
            "Glass Harbor (Sample)",
            author="Novel OS Tour",
            genres=["Literary Fiction", "Mystery"],
            premise=(
                "In a fogbound port where lanterns burn blue salt-oil, Lena Marrow "
                "waits for a ferry that never comes until a red light means quarantine."
            ),
        )
        # create_project may have used a different slug if collision prefer returned id
        pid = summary.id
        s = self._load(pid)

        if not s.characters:
            s.add_character(Character(
                id="char_001",
                full_name="Lena Marrow",
                role="protagonist",
                current_location="Glass Harbor pier",
                emotional_state="wary hope",
                notes="Keeps a brass compass that never points north.",
            ))
        s.add_codex_entry(CodexEntry(
            id="loc-001",
            entry_type="location",
            name="Glass Harbor",
            summary="A fogbound port where lanterns burn blue salt-oil.",
            notes="Tide clocks the town; ferries stop after dusk.",
        ))
        s.add_codex_entry(CodexEntry(
            id="wor-001",
            entry_type="worldbuilding",
            name="Salt-oil lanterns",
            summary="Harbor lights burn with blue flame; red flame means quarantine.",
        ))
        s.add_codex_entry(CodexEntry(
            id="ite-001",
            entry_type="item",
            name="Brass compass",
            summary="Lena's heirloom; needle refuses magnetic north.",
        ))

        ch = s.chapters.get(1) or ChapterState(number=1, title="Blue Lanterns")
        ch.title = "Blue Lanterns"
        ch.status = "drafted"
        ch.pov_character = "Lena Marrow"
        ch.location = "Glass Harbor pier"
        ch.word_count = 420
        ch.plot_advances = ["Lena waits for a ferry that never arrives; a red lantern appears."]
        s.chapters[1] = ch
        s.save_state()

        # Outline + short draft so pipeline stages are visible
        out = self._project_dir(pid)
        (out / "outputs").mkdir(parents=True, exist_ok=True)
        (out / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
        (out / "outputs" / "chapter_001_outline.md").write_text(
            "# Chapter 1 Blue Lanterns\n\n"
            "- Opening: Lena on the pier at dusk\n"
            "- Beat: ferry overdue; crowd thins\n"
            "- Turn: a single red lantern across the channel\n"
            "- Hook: compass needle spins toward the light\n",
            encoding="utf-8",
        )
        draft = (
            "<!--\nCHAPTER: 1 - Blue Lanterns\nPOV: Lena Marrow\n"
            "LOCATION: Glass Harbor pier\n-->\n\n"
            "Fog chewed the pier pilings. Lena Marrow cupped the brass compass "
            "until the metal warmed, then watched the needle refuse the north "
            "it owed her. Blue salt-oil lanterns lined the quay until one "
            "across the channel burned red.\n"
        )
        (out / "outputs" / "manuscript" / "chapter_001_draft.md").write_text(
            draft, encoding="utf-8",
        )
        s = self._load(pid)
        return self._summary(pid, s, out / "outputs" / "state" / "story_state.json")

    def add_character(self, project_id: str, name: str, role: str) -> list[CharacterSummary]:
        self._project_dir(project_id)  # 404 if missing
        if not name.strip():
            raise BadRequest("Character name is required.")
        build_orchestrator(str(self._project_dir(project_id))).add_character(name.strip(), role)
        return self.list_characters(project_id)

    def make_phase_job(self, project_id: str, stage: str, params: dict) -> Callable[[], None]:
        """Validate inputs and return a 0-arg callable the JobRunner can run."""
        self._project_dir(project_id)  # 404 if missing
        if stage not in PHASES:
            raise BadRequest(f"Unknown stage '{stage}'. Expected one of {sorted(PHASES)}.")
        project_dir = str(self._project_dir(project_id))

        def fn() -> None:
            orch = build_orchestrator(project_dir)
            PHASES[stage](orch, params)
            # Stamp pipeline provenance after the agent write (P3.2).
            mapping = _PHASE_ARTIFACT.get(stage)
            chapter = int(params.get("number") or 0)
            if mapping and chapter:
                art_stage, agent = mapping
                path = self._stage_paths(project_id, chapter).get(art_stage)
                text = _read(path) if path else None
                if text is not None:
                    try:
                        db.upsert_artifact(
                            project_id, chapter, art_stage, text,
                            produced_by_agent=agent,
                            produced_by_model=_current_model_label(),
                            reviewed_by="",
                            reviewed_at="",
                        )
                    except Exception:  # noqa: BLE001
                        pass

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

    def manuscript_statistics(self, project_id: str) -> dict:
        """Style Curator surface: frequency, echoes, reading time (deterministic)."""
        from style_stats import analyze_manuscript  # noqa: E402

        s = self._load(project_id)
        texts: list[str] = []
        with_prose = 0
        for c in sorted(s.chapters.values(), key=lambda c: c.number):
            p = self._stage_paths(project_id, c.number)
            text = _read(p["final"]) or _read(p["revised"]) or _read(p["draft"])
            if text and text.strip():
                texts.append(text)
                with_prose += 1
        stats = analyze_manuscript(texts)
        stats["chapter_count"] = len(s.chapters)
        stats["chapters_with_prose"] = with_prose
        return stats

    def continuity_findings(self, project_id: str, chapter: int | None = None) -> list[dict]:
        """Run deterministic continuity checks (fast, free)."""
        from continuity_engine import run_all  # type: ignore  # on core/ path

        s = self._load(project_id)
        proj = self._project_dir(project_id)
        findings = run_all(s, project_path=proj, as_of_chapter=chapter)
        if chapter is not None:
            findings = [f for f in findings if f.chapter is None or f.chapter == chapter]
        return [f.to_dict() for f in findings]

    def book_shape(self, project_id: str) -> dict:
        """Per-chapter movement plus any sagging runs (design spec §4.3).

        Deterministic: the engine measures what changed, it does not ask a model
        whether the book drags.
        """
        from stall_detector import book_shape, find_stalls  # noqa: E402

        s = self._load(project_id)
        return {
            "chapters": [a.to_dict() for a in book_shape(s)],
            "stalls": [r.to_dict() for r in find_stalls(s)],
        }

    def exempt_finding(self, project_id: str, key: str, reason: str = "") -> dict:
        """Mark a finding intentional (PLAN.md P2.1).

        A checker cannot distinguish an unreliable narrator, deliberate
        foreshadowing, or a character who lies from a real mistake. Without a
        dismissal that persists, the panel re-raises the same non-error forever
        and the writer stops reading it.
        """
        s = self._load(project_id)
        try:
            record = s.exempt_finding(key, reason)
        except ValueError as e:
            raise BadRequest(str(e))
        return {"key": key, **record}

    def unexempt_finding(self, project_id: str, key: str) -> bool:
        s = self._load(project_id)
        return s.unexempt_finding(key)

    def list_exemptions(self, project_id: str) -> list[dict]:
        s = self._load(project_id)
        return [
            {"key": k, "reason": v.get("reason", ""), "at": v.get("at", "")}
            for k, v in sorted(s.continuity_exemptions.items())
        ]
