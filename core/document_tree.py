"""Document tree the binder model (PLAN.md P0.4).

`StoryState.chapters` is a flat `{number: ChapterState}` map. A studio needs
structure: parts containing chapters containing scenes, reorderable, with
per-node metadata. This module is that structure.

Two deliberate constraints:

* **Additive.** The binder sits *beside* `chapters`, referencing chapters by
  number rather than replacing them. Agent prompts, the state parser and the
  continuity engine keep working untouched. Scenes are modelled here but the
  writing path stays chapter-level until the binder UI lands; making scenes
  the atomic writable unit is a later, separate change.
* **Flat storage, tree semantics.** Nodes are stored as a flat list with
  `parent_id` + `order` rather than nested dicts. Reordering and moving become
  local edits instead of rewrites, and JSON round-trips stay diff-friendly.

Migration ids are deterministic (`part-manuscript`, `ch-001`, `ch-001-s01`) so
golden-file tests are stable and a migrated binder is readable by eye. Nodes
created afterwards get random ids.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional

# Node types. `folder` exists for research and other non-manuscript material.
PART = "part"
CHAPTER = "chapter"
SCENE = "scene"
FOLDER = "folder"
NODE_TYPES = (PART, CHAPTER, SCENE, FOLDER)

ROOT = None  # a node whose parent_id is None sits at the top level


class BinderError(ValueError):
    """An operation that would corrupt the tree."""


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class DocumentNode:
    """One node in the binder.

    `chapter_number` links a chapter node back to its `ChapterState`; it is the
    only coupling between the tree and the flat model, and it is what lets both
    representations coexist without either owning the other.
    """
    id: str = field(default_factory=_new_id)
    type: str = SCENE
    title: str = ""
    parent_id: Optional[str] = None
    order: int = 0

    chapter_number: Optional[int] = None

    # Metadata every node carries (Scrivener's outliner columns).
    synopsis: str = ""
    status: str = "to_do"          # to_do | proposed | in_review | final
    label: str = ""                 # colour label
    keywords: List[str] = field(default_factory=list)
    pov: str = ""
    target_words: int = 0
    word_count: int = 0

    # AI-derived, human-confirmable: tension, emotional_intensity, pacing, …
    # Kept open rather than typed so agents can add columns without a migration.
    derived: Dict[str, Any] = field(default_factory=dict)

    include_in_compile: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentNode":
        # Tolerate unknown keys so an older client can't crash a newer state
        # file, and vice versa.
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class Binder:
    """The document tree. Flat node storage, tree operations."""

    def __init__(self, nodes: Optional[List[DocumentNode]] = None) -> None:
        self._nodes: Dict[str, DocumentNode] = {n.id: n for n in (nodes or [])}

    # ------------------------------------------------------------- accessors

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._nodes

    def get(self, node_id: str) -> Optional[DocumentNode]:
        return self._nodes.get(node_id)

    def all_nodes(self) -> List[DocumentNode]:
        return list(self._nodes.values())

    def children(self, parent_id: Optional[str]) -> List[DocumentNode]:
        kids = [n for n in self._nodes.values() if n.parent_id == parent_id]
        return sorted(kids, key=lambda n: (n.order, n.title))

    def roots(self) -> List[DocumentNode]:
        return self.children(ROOT)

    def walk(self, parent_id: Optional[str] = ROOT) -> Iterator[DocumentNode]:
        """Depth-first, in document order the order a reader would meet them."""
        for node in self.children(parent_id):
            yield node
            yield from self.walk(node.id)

    def ancestors(self, node_id: str) -> List[DocumentNode]:
        """Nearest parent first. Also the cycle guard for `move`."""
        out: List[DocumentNode] = []
        seen = {node_id}
        node = self._nodes.get(node_id)
        while node is not None and node.parent_id is not None:
            if node.parent_id in seen:  # defensive: a pre-existing cycle
                break
            seen.add(node.parent_id)
            parent = self._nodes.get(node.parent_id)
            if parent is None:
                break
            out.append(parent)
            node = parent
        return out

    def chapter_node(self, number: int) -> Optional[DocumentNode]:
        for n in self._nodes.values():
            if n.type == CHAPTER and n.chapter_number == number:
                return n
        return None

    # -------------------------------------------------------------- mutation

    def add(self, node: DocumentNode, parent_id: Optional[str] = ROOT,
            index: Optional[int] = None) -> DocumentNode:
        if node.type not in NODE_TYPES:
            raise BinderError(f"Unknown node type {node.type!r}")
        if parent_id is not None and parent_id not in self._nodes:
            raise BinderError(f"No such parent {parent_id!r}")
        if node.id in self._nodes:
            raise BinderError(f"Duplicate node id {node.id!r}")

        node.parent_id = parent_id
        self._nodes[node.id] = node
        self._place(node, index)
        return node

    def move(self, node_id: str, new_parent_id: Optional[str],
             index: Optional[int] = None) -> DocumentNode:
        node = self._require(node_id)
        if new_parent_id is not None:
            if new_parent_id not in self._nodes:
                raise BinderError(f"No such parent {new_parent_id!r}")
            # Moving a node beneath itself would orphan the subtree.
            if new_parent_id == node_id or node_id in {
                a.id for a in self.ancestors(new_parent_id)
            }:
                raise BinderError("Cannot move a node into its own subtree")

        old_parent = node.parent_id
        node.parent_id = new_parent_id
        self._place(node, index)
        if old_parent != new_parent_id:
            self._renumber(old_parent)
        return node

    def rename(self, node_id: str, title: str) -> DocumentNode:
        node = self._require(node_id)
        node.title = title
        return node

    def update(self, node_id: str, **fields: Any) -> DocumentNode:
        """Patch metadata. Structural fields are moved, not assigned."""
        node = self._require(node_id)
        for key, value in fields.items():
            if key in ("id", "parent_id", "order", "type"):
                raise BinderError(f"{key!r} is structural use add/move instead")
            if key not in DocumentNode.__dataclass_fields__:
                raise BinderError(f"Unknown field {key!r}")
            setattr(node, key, value)
        return node

    def remove(self, node_id: str) -> List[DocumentNode]:
        """Remove a node and everything under it. Returns what was removed."""
        node = self._require(node_id)
        doomed = [node] + list(self.walk(node_id))
        parent = node.parent_id
        for n in doomed:
            self._nodes.pop(n.id, None)
        self._renumber(parent)
        return doomed

    # ------------------------------------------------------------- internals

    def _require(self, node_id: str) -> DocumentNode:
        node = self._nodes.get(node_id)
        if node is None:
            raise BinderError(f"No such node {node_id!r}")
        return node

    def _place(self, node: DocumentNode, index: Optional[int]) -> None:
        """Insert `node` among its siblings at `index` (append if None)."""
        siblings = [n for n in self.children(node.parent_id) if n.id != node.id]
        if index is None or index >= len(siblings):
            siblings.append(node)
        else:
            siblings.insert(max(0, index), node)
        for i, n in enumerate(siblings):
            n.order = i

    def _renumber(self, parent_id: Optional[str]) -> None:
        for i, n in enumerate(self.children(parent_id)):
            n.order = i

    # ----------------------------------------------------------- persistence

    def to_list(self) -> List[Dict[str, Any]]:
        """Serialise in document order, so the JSON reads top to bottom."""
        return [n.to_dict() for n in self.walk()]

    @classmethod
    def from_list(cls, rows: List[Dict[str, Any]]) -> "Binder":
        return cls([DocumentNode.from_dict(r) for r in rows or []])

    def to_tree(self, parent_id: Optional[str] = ROOT) -> List[Dict[str, Any]]:
        """Nested form, for the API and the binder UI."""
        out = []
        for node in self.children(parent_id):
            row = node.to_dict()
            row["children"] = self.to_tree(node.id)
            out.append(row)
        return out


# --------------------------------------------------------------- migration

MANUSCRIPT_ID = "part-manuscript"


def chapter_id(number: int) -> str:
    return f"ch-{number:03d}"


def scene_id(number: int, index: int) -> str:
    return f"ch-{number:03d}-s{index:02d}"


def build_from_chapters(chapters: Dict[int, Any]) -> Binder:
    """Migrate a flat chapter map into `Manuscript → chapters → scenes`.

    Every chapter gets at least one scene, so the tree has a writable leaf even
    for chapters that were never broken into scenes. Where `ChapterState.scenes`
    already holds entries, each becomes a scene node and keeps its summary as
    the synopsis.
    """
    binder = Binder()
    part = DocumentNode(id=MANUSCRIPT_ID, type=PART, title="Manuscript")
    binder.add(part, ROOT)

    for number in sorted(chapters):
        ch = chapters[number]
        node = DocumentNode(
            id=chapter_id(number),
            type=CHAPTER,
            title=_get(ch, "title", "") or f"Chapter {number}",
            chapter_number=number,
            status=_migrate_status(_get(ch, "status", "planned")),
            pov=_get(ch, "pov_character", "") or "",
            word_count=int(_get(ch, "word_count", 0) or 0),
            target_words=int(_get(ch, "target_word_count", 0) or 0),
        )
        binder.add(node, part.id)

        scenes = _get(ch, "scenes", []) or []
        if not scenes:
            scenes = [{}]
        for i, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                scene = {"summary": str(scene)}
            binder.add(
                DocumentNode(
                    id=scene_id(number, i),
                    type=SCENE,
                    title=scene.get("title") or f"Scene {i}",
                    synopsis=scene.get("summary") or scene.get("synopsis") or "",
                    pov=scene.get("pov") or node.pov,
                    status=node.status,
                ),
                node.id,
            )
    return binder


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read from either a ChapterState or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# The chapter status enum predates the review lifecycle. Map the old values
# onto the node lifecycle without losing the distinction between "drafted by
# an agent" and "signed off by a human".
_STATUS_MAP = {
    "planned": "to_do",
    "drafting": "proposed",
    "drafted": "proposed",
    "editing": "proposed",
    "edited": "in_review",
    "validated": "in_review",
    "complete": "final",
    "approved": "final",
}


def migrate_status(status: str) -> str:
    """Map a `ChapterState.status` value onto a node lifecycle state."""
    return _STATUS_MAP.get((status or "").lower(), "to_do")


_migrate_status = migrate_status  # internal alias, kept for readability above
