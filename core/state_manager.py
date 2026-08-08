"""
Novel OS - State Management System

Centralized state management for the Novel OS architecture.
Maintains story bible, character database, plot tracker, timeline, and style profile.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path

# core/ is on sys.path rather than being a package, so siblings import by
# top-level name (see the header of api/services.py).
from document_tree import (
    CHAPTER, MANUSCRIPT_ID, PART, SCENE, Binder, DocumentNode,
    build_from_chapters, chapter_id, migrate_status, scene_id,
)


@dataclass
class Character:
    """Represents a character in the story."""
    id: str
    full_name: str
    role: str  # protagonist, antagonist, supporting, etc.
    age: Optional[int] = None
    physical_description: str = ""
    internal_desire: str = ""
    external_goal: str = ""
    fear: str = ""
    weakness: str = ""
    strength: str = ""
    secret: str = ""
    arc_stage: str = "beginning"  # beginning, middle, climax, resolution
    arc_progress: int = 0  # 0-100
    relationships: Dict[str, str] = field(default_factory=dict)
    knowledge: List[str] = field(default_factory=list)
    possessions: List[str] = field(default_factory=list)
    current_location: str = ""
    emotional_state: str = ""
    last_appearance_chapter: int = 0
    notes: str = ""
    portrait_media_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Character':
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


CODEX_TYPES = ("character", "location", "worldbuilding", "item")

RELATIONSHIP_PRESETS = (
    "ally", "rival", "family", "romantic", "mentor", "enemy",
    "owes debt", "secret", "unknown",
)


@dataclass
class RelationshipEdge:
    """Typed bond between Codex entities (context-menu / chart system)."""
    id: str
    source_id: str
    target_id: str
    label: str = "unknown"
    kind: str = "character_character"
    strength: float = 0.5
    status: str = "active"  # active | strained | resolved | hidden
    since_chapter: int = 0
    notes: str = ""
    directed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipEdge":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Collection:
    """Saved keyword search over the project world model (Scrivener-style)."""
    id: str
    name: str
    query: str
    kinds: List[str] = field(default_factory=list)  # empty = all kinds
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Collection":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class CodexEntry:
    """Typed world-model entry (PLAN.md P2.2). Non-character types live here;
    characters remain in `characters` for agent compatibility."""
    id: str
    entry_type: str  # location | worldbuilding | item
    name: str
    summary: str = ""
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    portrait_media_id: str = ""
    fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodexEntry":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class PlotThread:
    """Represents a plot thread or storyline."""
    id: str
    name: str
    description: str
    thread_type: str  # main, subplot, character_arc, mystery
    status: str = "active"  # active, resolved, abandoned, foreshadowed
    priority: int = 1  # 1-5, 5 being highest
    start_chapter: int = 0
    target_resolution_chapter: Optional[int] = None
    related_characters: List[str] = field(default_factory=list)
    related_threads: List[str] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)
    foreshadowing_planted: List[int] = field(default_factory=list)
    last_updated_chapter: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlotThread':
        return cls(**data)


@dataclass
class ChapterState:
    """Represents the state of a chapter."""
    number: int
    title: str = ""
    status: str = "planned"  # planned, drafting, drafted, editing, edited, validated, complete
    pov_character: str = ""
    location: str = ""
    time: str = ""
    word_count: int = 0
    target_word_count: int = 2500
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    plot_advances: List[str] = field(default_factory=list)
    character_development: Dict[str, str] = field(default_factory=dict)
    emotional_beats: List[str] = field(default_factory=list)
    new_information: List[str] = field(default_factory=list)
    foreshadowing_planted: List[str] = field(default_factory=list)
    foreshadowing_resolved: List[str] = field(default_factory=list)
    hooks_start: List[str] = field(default_factory=list)
    hooks_end: List[str] = field(default_factory=list)
    characters_present: List[str] = field(default_factory=list)
    continuity_checks: Dict[str, Any] = field(default_factory=dict)
    quality_scores: Dict[str, float] = field(default_factory=dict)
    last_modified: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChapterState':
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class StyleProfile:
    """Defines the writing style for the novel."""
    name: str = "default"
    description: str = ""
    tone: str = "neutral"  # dark, light, humorous, serious, etc.
    point_of_view: str = "third_limited"  # first, third_limited, third_omniscient
    tense: str = "past"  # past, present
    prose_style: str = "balanced"  # lyrical, minimalist, cinematic, intimate, suspenseful
    avg_sentence_length: int = 15
    vocabulary_level: str = "moderate"  # simple, moderate, complex
    dialogue_ratio: float = 0.3  # 0-1
    description_ratio: float = 0.3  # 0-1
    internal_monologue_ratio: float = 0.2  # 0-1
    paragraph_max_sentences: int = 5
    chapter_target_words: int = 2500
    scene_break_marker: str = "***"
    dialect_notes: str = ""
    genre_conventions: List[str] = field(default_factory=list)
    forbidden_words: List[str] = field(default_factory=list)
    preferred_words: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StyleProfile':
        return cls(**data)


@dataclass
class TimelineEvent:
    """Represents an event in the story timeline."""
    id: str
    description: str
    chapter: int
    day: Optional[int] = None
    time: Optional[str] = None
    location: str = ""
    characters_present: List[str] = field(default_factory=list)
    event_type: str = "scene"  # scene, backstory, flashback, summary
    significance: str = "minor"  # minor, major, turning_point, climax
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimelineEvent':
        return cls(**data)


class StoryState:
    """
    Central state manager for Novel OS.
    Maintains all story data and provides CRUD operations.
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / "outputs" / "state"
        self.state_file = self.state_dir / "story_state.json"
        
        # Core data structures
        self.metadata: Dict[str, Any] = {}
        self.story_bible: Dict[str, Any] = {}
        self.characters: Dict[str, Character] = {}
        self.codex: Dict[str, CodexEntry] = {}
        self.relationships: Dict[str, RelationshipEdge] = {}
        self.collections: Dict[str, Collection] = {}
        # Continuity findings the writer has marked intentional, keyed by the
        # fact they exempt. A checker cannot tell an unreliable narrator or a
        # character who lies from a mistake, so without a dismissal that sticks
        # the panel re-raises the same non-error every run and the writer learns
        # to ignore it - which costs more than the check is worth.
        self.continuity_exemptions: Dict[str, Dict[str, Any]] = {}
        self.plot_threads: Dict[str, PlotThread] = {}
        self.chapters: Dict[int, ChapterState] = {}
        self.timeline: List[TimelineEvent] = []
        self.style_profile: StyleProfile = StyleProfile()
        # Document tree. Sits beside `chapters` rather than replacing it, so the
        # agents and continuity engine are unaffected. See core/document_tree.py.
        self.binder: Binder = Binder()
        
        # Session tracking
        self.session_log: List[Dict[str, Any]] = []
        
        self._ensure_directories()
        self._load_state()
    
    def _ensure_directories(self):
        """Create necessary directories."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_state(self):
        """Load state from disk if it exists."""
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.metadata = data.get('metadata', {})
                self.story_bible = data.get('story_bible', {})
                self.characters = {
                    k: Character.from_dict(v) 
                    for k, v in data.get('characters', {}).items()
                }
                self.codex = {
                    k: CodexEntry.from_dict(v)
                    for k, v in data.get('codex', {}).items()
                }
                self.relationships = {
                    k: RelationshipEdge.from_dict(v)
                    for k, v in data.get('relationships', {}).items()
                }
                self.collections = {
                    k: Collection.from_dict(v)
                    for k, v in data.get('collections', {}).items()
                }
                self.continuity_exemptions = dict(
                    data.get('continuity_exemptions', {}) or {}
                )
                self.plot_threads = {
                    k: PlotThread.from_dict(v)
                    for k, v in data.get('plot_threads', {}).items()
                }
                self.chapters = {
                    int(k): ChapterState.from_dict(v)
                    for k, v in data.get('chapters', {}).items()
                }
                self.timeline = [
                    TimelineEvent.from_dict(e)
                    for e in data.get('timeline', [])
                ]
                self.style_profile = StyleProfile.from_dict(
                    data.get('style_profile', {})
                )
                self.session_log = data.get('session_log', [])
                self.binder = Binder.from_list(data.get('binder', []))

        # Migrate legacy Character.relationships dict → typed edges once.
        self._migrate_legacy_relationships()

        # A project written before the binder existed has no tree. Build one
        # from the flat chapters on first load; it is persisted on next save.
        if len(self.binder) == 0 and self.chapters:
            self.binder = build_from_chapters(self.chapters)

    def sync_binder(self) -> None:
        """Reconcile the tree with `chapters` after chapters are added or edited.

        `chapters` stays authoritative for chapter-level data while the writing
        path is chapter-level; this mirrors it forward. Nodes the user created
        or reordered are left alone titles and structure are theirs to own.
        """
        if len(self.binder) == 0:
            self.binder = build_from_chapters(self.chapters)
            return

        part = self.binder.get(MANUSCRIPT_ID)
        if part is None:
            part = self.binder.add(
                DocumentNode(id=MANUSCRIPT_ID, type=PART, title="Manuscript")
            )

        for number in sorted(self.chapters):
            ch = self.chapters[number]
            node = self.binder.chapter_node(number)
            if node is None:
                node = self.binder.add(
                    DocumentNode(
                        id=chapter_id(number), type=CHAPTER,
                        title=ch.title or f"Chapter {number}", chapter_number=number,
                    ),
                    part.id,
                )
                self.binder.add(
                    DocumentNode(id=scene_id(number, 1), type=SCENE, title="Scene 1"),
                    node.id,
                )
            # Mirror engine-owned facts; leave user-owned title/order alone.
            node.word_count = int(ch.word_count or 0)
            node.pov = ch.pov_character or node.pov
            node.status = migrate_status(ch.status)


    def save_state(self):
        """Save current state to disk."""
        # Keep the tree in step with the flat chapters on every write, so the
        # two representations can never drift.
        self.sync_binder()
        data = {
            'metadata': self.metadata,
            'story_bible': self.story_bible,
            'characters': {k: v.to_dict() for k, v in self.characters.items()},
            'codex': {k: v.to_dict() for k, v in self.codex.items()},
            'relationships': {k: v.to_dict() for k, v in self.relationships.items()},
            'collections': {k: v.to_dict() for k, v in self.collections.items()},
            'continuity_exemptions': dict(self.continuity_exemptions),
            'plot_threads': {k: v.to_dict() for k, v in self.plot_threads.items()},
            'chapters': {k: v.to_dict() for k, v in self.chapters.items()},
            'binder': self.binder.to_list(),
            'timeline': [e.to_dict() for e in self.timeline],
            'style_profile': self.style_profile.to_dict(),
            'session_log': self.session_log,
            'last_saved': datetime.now().isoformat()
        }
        
        # Create backup of existing state (os.replace overwrites on Windows too)
        if self.state_file.exists():
            backup_path = self.state_file.with_suffix('.json.bak')
            os.replace(self.state_file, backup_path)
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # ===== Character Management =====
    
    def add_character(self, character: Character) -> str:
        """Add a new character to the database."""
        self.characters[character.id] = character
        self._log_action('character_added', {'character_id': character.id})
        return character.id
    
    def update_character(self, character_id: str, updates: Dict[str, Any]):
        """Update character fields."""
        if character_id in self.characters:
            char = self.characters[character_id]
            for key, value in updates.items():
                if hasattr(char, key):
                    setattr(char, key, value)
            self._log_action('character_updated', {
                'character_id': character_id,
                'updates': list(updates.keys())
            })
    
    def get_character(self, character_id: str) -> Optional[Character]:
        """Retrieve a character by ID."""
        return self.characters.get(character_id)
    
    def get_character_by_name(self, name: str) -> Optional[Character]:
        """Find a character by full name."""
        for char in self.characters.values():
            if char.full_name.lower() == name.lower():
                return char
        return None
    
    def get_all_characters(self) -> List[Character]:
        """Get all characters as a list."""
        return list(self.characters.values())

    def add_codex_entry(self, entry: CodexEntry) -> str:
        if entry.entry_type not in CODEX_TYPES:
            raise ValueError(f"Invalid codex type '{entry.entry_type}'")
        self.codex[entry.id] = entry
        self._log_action('codex_added', {'id': entry.id, 'type': entry.entry_type})
        self.save_state()
        return entry.id

    def update_codex_entry(self, entry_id: str, **kwargs: Any) -> Optional[CodexEntry]:
        entry = self.codex.get(entry_id)
        if not entry:
            return None
        for k, v in kwargs.items():
            if hasattr(entry, k) and v is not None:
                setattr(entry, k, v)
        self._log_action('codex_updated', {'id': entry_id})
        self.save_state()
        return entry

    def get_codex_entries(self, entry_type: Optional[str] = None) -> List[CodexEntry]:
        items = list(self.codex.values())
        if entry_type:
            items = [e for e in items if e.entry_type == entry_type]
        return sorted(items, key=lambda e: e.name.lower())

    def format_codex_block(self, max_chars: int = 4500) -> str:
        """Canonical world-model text for Guardian (and other agents) prompts.

        Characters live in `characters`; non-character types in `codex`. Empty
        when the author hasn't filled anything yet.
        """
        lines: List[str] = ["## Codex (canonical world model - treat as ground truth)", ""]
        chars = self.get_all_characters()
        if chars:
            lines.append("### Characters")
            for c in sorted(chars, key=lambda x: x.full_name.lower()):
                bits = [f"**{c.full_name}** ({c.role or 'unspecified'})"]
                if c.current_location:
                    bits.append(f"location: {c.current_location}")
                if c.emotional_state:
                    bits.append(f"emotion: {c.emotional_state}")
                if c.notes:
                    bits.append(c.notes.strip()[:240])
                lines.append("- " + " · ".join(bits))
            lines.append("")
        by_type = {
            "location": "Locations",
            "worldbuilding": "World rules",
            "item": "Items",
        }
        for etype, heading in by_type.items():
            entries = self.get_codex_entries(etype)
            if not entries:
                continue
            lines.append(f"### {heading}")
            for e in entries:
                line = f"- **{e.name}**"
                if e.summary:
                    line += f": {e.summary.strip()[:320]}"
                lines.append(line)
                if e.notes:
                    lines.append(f"  notes: {e.notes.strip()[:200]}")
            lines.append("")
        # Relationship graph (1-hop bonds)
        rels = getattr(self, "relationships", None) or {}
        if rels:
            lines.append("### Relationships")
            for e in sorted(rels.values(), key=lambda x: x.label.lower()):
                a = self.characters.get(e.source_id)
                b = self.characters.get(e.target_id)
                an = a.full_name if a else e.source_id
                bn = b.full_name if b else e.target_id
                arrow = " → " if e.directed else " ↔ "
                lines.append(f"- **{an}**{arrow}**{bn}** ({e.label}"
                             f"{', ' + e.status if e.status and e.status != 'active' else ''})")
                if e.notes:
                    lines.append(f"  notes: {e.notes.strip()[:160]}")
            lines.append("")
        if len(lines) <= 2:
            return ""
        text = "\n".join(lines).rstrip() + "\n"
        if len(text) > max_chars:
            text = text[: max_chars - 40].rstrip() + "\n…[codex truncated]\n"
        return text

    def set_character_portrait(self, character_id: str, media_id: str) -> Optional[Character]:
        char = self.characters.get(character_id)
        if not char:
            return None
        char.portrait_media_id = media_id
        self.save_state()
        return char

    def _migrate_legacy_relationships(self) -> None:
        """Promote Character.relationships string map into RelationshipEdge rows."""
        if self.relationships:
            return
        n = 0
        for cid, char in self.characters.items():
            for other_id, label in (char.relationships or {}).items():
                if other_id not in self.characters and other_id not in self.codex:
                    continue
                # Skip if reverse already created
                exists = any(
                    {e.source_id, e.target_id} == {cid, other_id}
                    for e in self.relationships.values()
                )
                if exists:
                    continue
                n += 1
                eid = f"rel-{n:03d}"
                while eid in self.relationships:
                    n += 1
                    eid = f"rel-{n:03d}"
                self.relationships[eid] = RelationshipEdge(
                    id=eid,
                    source_id=cid,
                    target_id=other_id,
                    label=str(label or "unknown"),
                )

    def list_relationships(self, entry_id: Optional[str] = None) -> List[RelationshipEdge]:
        items = list(self.relationships.values())
        if entry_id:
            items = [e for e in items if e.source_id == entry_id or e.target_id == entry_id]
        return sorted(items, key=lambda e: e.label.lower())

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        label: str = "unknown",
        *,
        notes: str = "",
        directed: bool = False,
        since_chapter: int = 0,
    ) -> RelationshipEdge:
        if source_id == target_id:
            raise ValueError("Cannot relate an entry to itself")
        for e in self.relationships.values():
            if not e.directed and {e.source_id, e.target_id} == {source_id, target_id}:
                e.label = label.strip() or e.label
                e.notes = notes.strip() or e.notes
                self.save_state()
                return e
            if e.directed and e.source_id == source_id and e.target_id == target_id:
                e.label = label.strip() or e.label
                e.notes = notes.strip() or e.notes
                self.save_state()
                return e
        n = len(self.relationships) + 1
        eid = f"rel-{n:03d}"
        while eid in self.relationships:
            n += 1
            eid = f"rel-{n:03d}"
        edge = RelationshipEdge(
            id=eid,
            source_id=source_id,
            target_id=target_id,
            label=(label or "unknown").strip(),
            notes=notes.strip(),
            directed=directed,
            since_chapter=since_chapter,
        )
        self.relationships[eid] = edge
        self._log_action("relationship_added", {"id": eid})
        self.save_state()
        return edge

    def delete_relationship(self, edge_id: str) -> bool:
        if edge_id not in self.relationships:
            return False
        del self.relationships[edge_id]
        self._log_action("relationship_deleted", {"id": edge_id})
        self.save_state()
        return True

    def exempt_finding(self, key: str, reason: str = "") -> Dict[str, Any]:
        """Mark a continuity finding intentional so it stops being reported.

        The reason is the point: six months later the writer needs to know why
        past-them waved this through, and the Guardian gets to read it too.
        """
        key = (key or "").strip()
        if not key:
            raise ValueError("An exemption needs a finding key.")
        record = {"reason": (reason or "").strip(), "at": datetime.now().isoformat()}
        self.continuity_exemptions[key] = record
        self._log_action("continuity_exempted", {"key": key})
        self.save_state()
        return record

    def unexempt_finding(self, key: str) -> bool:
        """Undo an exemption, so the finding can be reported again."""
        if key not in self.continuity_exemptions:
            return False
        del self.continuity_exemptions[key]
        self._log_action("continuity_unexempted", {"key": key})
        self.save_state()
        return True

    def list_collections(self) -> List[Collection]:
        return sorted(self.collections.values(), key=lambda c: c.name.lower())

    def add_collection(
        self, name: str, query: str, kinds: Optional[List[str]] = None, notes: str = "",
    ) -> Collection:
        import uuid
        cid = f"col-{uuid.uuid4().hex[:8]}"
        col = Collection(
            id=cid,
            name=(name or query or "Untitled").strip()[:80],
            query=(query or "").strip(),
            kinds=[k for k in (kinds or []) if k],
            notes=(notes or "").strip(),
        )
        self.collections[cid] = col
        self._log_action("collection_added", {"id": cid})
        self.save_state()
        return col

    def delete_collection(self, collection_id: str) -> bool:
        if collection_id not in self.collections:
            return False
        del self.collections[collection_id]
        self._log_action("collection_deleted", {"id": collection_id})
        self.save_state()
        return True

    def update_character_location(self, character_id: str, location: str, chapter: int):
        """Update a character's current location."""
        if character_id in self.characters:
            char = self.characters[character_id]
            char.current_location = location
            char.last_appearance_chapter = chapter
    
    def update_character_arc(self, character_id: str, new_stage: str, progress: int):
        """Update a character's arc stage and progress."""
        if character_id in self.characters:
            char = self.characters[character_id]
            char.arc_stage = new_stage
            char.arc_progress = max(0, min(100, progress))
    
    # ===== Plot Thread Management =====
    
    def add_plot_thread(self, thread: PlotThread) -> str:
        """Add a new plot thread."""
        self.plot_threads[thread.id] = thread
        self._log_action('plot_thread_added', {'thread_id': thread.id})
        return thread.id
    
    def update_plot_thread(self, thread_id: str, updates: Dict[str, Any]):
        """Update plot thread fields."""
        if thread_id in self.plot_threads:
            thread = self.plot_threads[thread_id]
            for key, value in updates.items():
                if hasattr(thread, key):
                    setattr(thread, key, value)
    
    def get_plot_thread(self, thread_id: str) -> Optional[PlotThread]:
        """Retrieve a plot thread by ID."""
        return self.plot_threads.get(thread_id)
    
    def get_active_plot_threads(self) -> List[PlotThread]:
        """Get all active plot threads."""
        return [t for t in self.plot_threads.values() if t.status == 'active']
    
    def get_unresolved_threads(self) -> List[PlotThread]:
        """Get threads that need resolution."""
        return [
            t for t in self.plot_threads.values()
            if t.status in ['active', 'foreshadowed']
        ]
    
    def add_milestone_to_thread(self, thread_id: str, description: str, chapter: int):
        """Add a milestone to a plot thread."""
        if thread_id in self.plot_threads:
            thread = self.plot_threads[thread_id]
            milestone = {
                'description': description,
                'chapter': chapter,
                'timestamp': datetime.now().isoformat()
            }
            thread.milestones.append(milestone)
            thread.last_updated_chapter = chapter
    
    def resolve_plot_thread(self, thread_id: str, chapter: int):
        """Mark a plot thread as resolved."""
        if thread_id in self.plot_threads:
            thread = self.plot_threads[thread_id]
            thread.status = 'resolved'
            self.add_milestone_to_thread(thread_id, 'Thread resolved', chapter)
    
    # ===== Chapter Management =====
    
    def create_chapter(self, number: int, title: str = "") -> ChapterState:
        """Create a new chapter entry."""
        chapter = ChapterState(number=number, title=title)
        self.chapters[number] = chapter
        self._log_action('chapter_created', {'chapter': number})
        return chapter
    
    def get_chapter(self, number: int) -> Optional[ChapterState]:
        """Retrieve chapter state by number."""
        return self.chapters.get(number)
    
    def update_chapter(self, number: int, updates: Dict[str, Any]):
        """Update chapter fields."""
        if number in self.chapters:
            chapter = self.chapters[number]
            for key, value in updates.items():
                if hasattr(chapter, key):
                    setattr(chapter, key, value)
            chapter.last_modified = datetime.now().isoformat()
    
    def get_chapter_count(self) -> int:
        """Get total number of chapters."""
        return len(self.chapters)
    
    def get_completed_chapters(self) -> List[ChapterState]:
        """Get all chapters marked as complete."""
        return [
            c for c in self.chapters.values()
            if c.status == 'complete'
        ]
    
    # ===== Timeline Management =====
    
    def add_timeline_event(self, event: TimelineEvent):
        """Add an event to the timeline."""
        self.timeline.append(event)
        self.timeline.sort(key=lambda e: (e.chapter, e.day or 0))
    
    def get_timeline_for_chapter(self, chapter: int) -> List[TimelineEvent]:
        """Get all timeline events for a specific chapter."""
        return [e for e in self.timeline if e.chapter == chapter]
    
    def get_character_timeline(self, character_id: str) -> List[TimelineEvent]:
        """Get all timeline events featuring a character."""
        return [
            e for e in self.timeline
            if character_id in e.characters_present
        ]
    
    # ===== Style Management =====
    
    def set_style_profile(self, profile: StyleProfile):
        """Set the novel's style profile."""
        self.style_profile = profile
        self._log_action('style_profile_updated', {'profile_name': profile.name})
    
    def get_style_profile(self) -> StyleProfile:
        """Get the current style profile."""
        return self.style_profile
    
    # ===== Story Bible Management =====
    
    def update_story_bible(self, section: str, data: Any):
        """Update a section of the story bible."""
        self.story_bible[section] = data
        self._log_action('story_bible_updated', {'section': section})
    
    def get_story_bible_section(self, section: str) -> Any:
        """Retrieve a section from the story bible."""
        return self.story_bible.get(section)
    
    # ===== Metadata =====
    
    def set_metadata(self, key: str, value: Any):
        """Set a metadata value."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default=None) -> Any:
        """Get a metadata value."""
        return self.metadata.get(key, default)
    
    # ===== Session Logging =====
    
    def _log_action(self, action: str, details: Dict[str, Any]):
        """Log an action to the session log."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details
        }
        self.session_log.append(entry)
    
    def get_session_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent session log entries."""
        return self.session_log[-limit:]
    
    # ===== State Summaries =====
    
    def get_story_summary(self) -> str:
        """Generate a text summary of the story state."""
        lines = [
            f"# Story Summary: {self.metadata.get('title', 'Untitled')}",
            f"",
            f"## Metadata",
            f"- Genre: {self.metadata.get('genre', 'Unknown')}",
            f"- Chapters: {len(self.chapters)}",
            f"- Characters: {len(self.characters)}",
            f"- Active Plot Threads: {len(self.get_active_plot_threads())}",
            f"",
            f"## Characters",
        ]
        
        for char in self.characters.values():
            lines.append(f"- **{char.full_name}** ({char.role}): {char.arc_stage} ({char.arc_progress}%)")
        
        lines.extend([
            f"",
            f"## Active Plot Threads",
        ])
        
        for thread in self.get_active_plot_threads():
            lines.append(f"- **{thread.name}** (Priority {thread.priority})")
        
        return '\n'.join(lines)
    
    def get_continuity_context(self, chapter: int) -> Dict[str, Any]:
        """Get context needed for continuity checking."""
        try:
            from context_pack import build_context_pack, format_context_pack
            pack = build_context_pack(self, chapter, purpose="guardian")
            codex_block = format_context_pack(pack)
            rel_subset = [
                e.to_dict()
                for e in getattr(self, "relationships", {}).values()
                if any(b["id"] == e.id for b in pack.bonds)
            ] or [
                e.to_dict() for e in getattr(self, "relationships", {}).values()
            ]
        except Exception:
            codex_block = self.format_codex_block()
            rel_subset = [
                e.to_dict() for e in getattr(self, "relationships", {}).values()
            ]
        return {
            'chapter': chapter,
            'character_locations': {
                cid: char.current_location
                for cid, char in self.characters.items()
            },
            'character_emotional_states': {
                cid: char.emotional_state
                for cid, char in self.characters.items()
            },
            'active_threads': [
                t.to_dict() for t in self.get_active_plot_threads()
            ],
            'foreshadowing_active': [
                t.to_dict() for t in self.plot_threads.values()
                if t.status == 'foreshadowed'
            ],
            'previous_chapter_events': [
                e.to_dict() for e in self.get_timeline_for_chapter(chapter - 1)
            ] if chapter > 1 else [],
            'codex_block': codex_block,
            'relationships': rel_subset,
        }


def initialize_project(project_path: str, title: str, genre: str) -> StoryState:
    """Initialize a new novel project with default state."""
    state = StoryState(project_path)
    
    # Set metadata
    state.set_metadata('title', title)
    state.set_metadata('genre', genre)
    state.set_metadata('created', datetime.now().isoformat())
    state.set_metadata('version', '1.0')
    
    # Initialize story bible with defaults
    state.update_story_bible('genre', genre)
    state.update_story_bible('themes', [])
    state.update_story_bible('tone', '')
    state.update_story_bible('setting', {
        'time_period': '',
        'primary_location': '',
        'world_rules': {}
    })
    state.update_story_bible('magic_system' if 'fantasy' in genre.lower() else 'technology', {})
    
    # Save initial state
    state.save_state()
    
    return state


if __name__ == '__main__':
    # Demo usage
    state = initialize_project('.', 'Demo Novel', 'Science Fiction')
    
    # Add a character
    protagonist = Character(
        id='char_001',
        full_name='Aria Chen',
        role='protagonist',
        internal_desire='Find belonging',
        external_goal='Stop the AI uprising',
        arc_stage='beginning',
        arc_progress=0
    )
    state.add_character(protagonist)
    
    # Add a plot thread
    main_thread = PlotThread(
        id='plot_001',
        name='The Uprising',
        description='AI systems begin to rebel against human control',
        thread_type='main',
        priority=5
    )
    state.add_plot_thread(main_thread)
    
    # Save
    state.save_state()
    
    print(state.get_story_summary())
