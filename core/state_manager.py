"""
Novel OS - State Management System

Centralized state management for the Novel OS architecture.
Maintains story bible, character database, plot tracker, timeline, and style profile.
"""

import json
import os
import threading
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path


_project_locks: dict[str, threading.Lock] = {}
_project_locks_guard = threading.Lock()


def project_state_lock(project_path: str) -> threading.Lock:
    """Serialize load/apply/save for one project (parallel miners, extractors, etc.)."""
    key = str(Path(project_path).resolve())
    with _project_locks_guard:
        if key not in _project_locks:
            _project_locks[key] = threading.Lock()
        return _project_locks[key]


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
    aliases: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Character':
        from dataclasses import fields
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        kwargs.setdefault("aliases", [])
        return cls(**kwargs)
    
    def all_names(self) -> List[str]:
        """Canonical name plus registered aliases."""
        names = [self.full_name]
        names.extend(a for a in self.aliases if a.strip())
        return names


@dataclass
class PlotThread:
    """Represents a plot thread or storyline."""
    id: str
    name: str
    description: str
    thread_type: str  # main, subplot, character_arc, mystery
    status: str = "active"  # active, resolved, abandoned, foreshadowed
    priority: int = 1  # 1-5, 5 being highest
    sort_order: int = 0
    subplots: List[str] = field(default_factory=list)
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
        from dataclasses import fields
        valid = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in valid}
        kwargs.setdefault("subplots", [])
        kwargs.setdefault("sort_order", 0)
        return cls(**kwargs)


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
    continuity_checks: Dict[str, Any] = field(default_factory=dict)
    quality_scores: Dict[str, float] = field(default_factory=dict)
    last_modified: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChapterState':
        return cls(**data)


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
        self.plot_threads: Dict[str, PlotThread] = {}
        self.chapters: Dict[int, ChapterState] = {}
        self.timeline: List[TimelineEvent] = []
        self.style_profile: StyleProfile = StyleProfile()
        
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
    
    def save_state(self):
        """Save current state to disk."""
        data = {
            'metadata': self.metadata,
            'story_bible': self.story_bible,
            'characters': {k: v.to_dict() for k, v in self.characters.items()},
            'plot_threads': {k: v.to_dict() for k, v in self.plot_threads.items()},
            'chapters': {k: v.to_dict() for k, v in self.chapters.items()},
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
        """Find a character by full name or alias (case-insensitive)."""
        needle = name.strip().lower()
        if not needle:
            return None
        for char in self.characters.values():
            if char.full_name.lower() == needle:
                return char
            for alias in char.aliases:
                if alias.strip().lower() == needle:
                    return char
        return None

    def add_character_alias(self, character_id: str, alias: str) -> bool:
        """Register an alternate name for a character."""
        alias = alias.strip()
        if not alias:
            return False
        char = self.characters.get(character_id)
        if char is None:
            return False
        if alias.lower() == char.full_name.lower():
            return False
        known = {char.full_name.lower(), *(a.lower() for a in char.aliases)}
        if alias.lower() in known:
            return False
        char.aliases.append(alias)
        self._log_action('character_alias_added', {'character_id': character_id, 'alias': alias})
        return True
    
    def get_all_characters(self) -> List[Character]:
        """Get all characters as a list."""
        return list(self.characters.values())
    
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

    def delete_character(self, character_id: str) -> bool:
        """Remove a character and scrub references from plot threads and timeline."""
        char = self.characters.pop(character_id, None)
        if char is None:
            return False
        for thread in self.plot_threads.values():
            thread.related_characters = [
                cid for cid in thread.related_characters if cid != character_id
            ]
        self.timeline = [
            e for e in self.timeline if character_id not in e.characters_present
        ]
        self._log_action('character_deleted', {
            'character_id': character_id,
            'name': char.full_name,
        })
        return True
    
    # ===== Plot Thread Management =====
    
    def _plot_thread_sort_key(self, thread: PlotThread) -> tuple:
        return (thread.sort_order, -thread.priority, thread.name.lower())

    def get_ordered_plot_threads(self) -> List[PlotThread]:
        """All plot threads in display / prompt order."""
        threads = list(self.plot_threads.values())
        if threads and len({t.sort_order for t in threads}) == 1:
            threads.sort(key=lambda t: (-t.priority, t.name.lower()))
        else:
            threads.sort(key=self._plot_thread_sort_key)
        return threads

    def add_plot_thread(self, thread: PlotThread) -> str:
        """Add a new plot thread."""
        if self.plot_threads and thread.sort_order == 0:
            thread.sort_order = max(t.sort_order for t in self.plot_threads.values()) + 1
        self.plot_threads[thread.id] = thread
        self._log_action('plot_thread_added', {'thread_id': thread.id})
        return thread.id

    def reorder_plot_threads(self, ordered_ids: List[str]) -> None:
        """Persist drag-and-drop order."""
        for i, tid in enumerate(ordered_ids):
            if tid in self.plot_threads:
                self.plot_threads[tid].sort_order = i
        self._log_action('plot_threads_reordered', {'order': ordered_ids})
    
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
        """Active plot threads in sort order (for prompts)."""
        return [t for t in self.get_ordered_plot_threads() if t.status == 'active']
    
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

    def delete_plot_thread(self, thread_id: str) -> bool:
        """Remove a plot thread."""
        if self.plot_threads.pop(thread_id, None) is None:
            return False
        self._log_action('plot_thread_deleted', {'thread_id': thread_id})
        return True
    
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

    def delete_chapter(self, number: int) -> bool:
        """Remove a chapter from state and scrub its timeline events."""
        if self.chapters.pop(number, None) is None:
            return False
        self.timeline = [e for e in self.timeline if e.chapter != number]
        self._log_action('chapter_deleted', {'chapter': number})
        return True

    def reassign_chapter(self, from_number: int, to_number: int) -> str:
        """Move a chapter to a new number, or swap with an existing chapter."""
        if from_number not in self.chapters:
            raise ValueError(f"Chapter {from_number} not found")
        if from_number == to_number:
            return "unchanged"
        if to_number in self.chapters:
            self._swap_chapter_numbers(from_number, to_number)
            self._log_action('chapter_swapped', {'a': from_number, 'b': to_number})
            return "swapped"
        ch = self.chapters.pop(from_number)
        ch.number = to_number
        self.chapters[to_number] = ch
        self._remap_chapter_number(from_number, to_number)
        self._log_action('chapter_reassigned', {'from': from_number, 'to': to_number})
        return "moved"

    def _remap_chapter_number(self, old: int, new: int) -> None:
        for event in self.timeline:
            if event.chapter == old:
                event.chapter = new
        for char in self.characters.values():
            if char.last_appearance_chapter == old:
                char.last_appearance_chapter = new
        for thread in self.plot_threads.values():
            if thread.start_chapter == old:
                thread.start_chapter = new
            if thread.last_updated_chapter == old:
                thread.last_updated_chapter = new
            if thread.target_resolution_chapter == old:
                thread.target_resolution_chapter = new
            thread.foreshadowing_planted = [
                new if ch == old else ch for ch in thread.foreshadowing_planted
            ]
            for ms in thread.milestones:
                if ms.get("chapter") == old:
                    ms["chapter"] = new

    def _swap_chapter_numbers(self, a: int, b: int) -> None:
        ch_a = self.chapters[a]
        ch_b = self.chapters[b]
        ch_a.number = b
        ch_b.number = a
        self.chapters[b] = ch_a
        self.chapters[a] = ch_b
        sentinel = -(max(a, b) + 100000)
        for event in self.timeline:
            if event.chapter == a:
                event.chapter = sentinel
            elif event.chapter == b:
                event.chapter = a
        for event in self.timeline:
            if event.chapter == sentinel:
                event.chapter = b
        for char in self.characters.values():
            if char.last_appearance_chapter == a:
                char.last_appearance_chapter = sentinel
            elif char.last_appearance_chapter == b:
                char.last_appearance_chapter = a
        for char in self.characters.values():
            if char.last_appearance_chapter == sentinel:
                char.last_appearance_chapter = b
        for thread in self.plot_threads.values():
            for field in ("start_chapter", "last_updated_chapter", "target_resolution_chapter"):
                val = getattr(thread, field)
                if val == a:
                    setattr(thread, field, sentinel)
                elif val == b:
                    setattr(thread, field, a)
            thread.foreshadowing_planted = [
                sentinel if ch == a else (a if ch == b else ch)
                for ch in thread.foreshadowing_planted
            ]
            thread.foreshadowing_planted = [
                b if ch == sentinel else ch for ch in thread.foreshadowing_planted
            ]
            for ms in thread.milestones:
                ch_num = ms.get("chapter")
                if ch_num == a:
                    ms["chapter"] = sentinel
                elif ch_num == b:
                    ms["chapter"] = a
            for ms in thread.milestones:
                if ms.get("chapter") == sentinel:
                    ms["chapter"] = b
    
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
            ] if chapter > 1 else []
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
