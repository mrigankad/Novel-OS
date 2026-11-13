"""Per-store launch checklists, with status computed from the book's actual data.

Each checklist item is either *auto* (derived from chapters, metadata, covers,
marketing assets) or *manual* (the author ticks it; stored in Release.checklist).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import case
from sqlmodel import Session, func, select

from ..models import BookMetadata, Chapter, CoverDesign, Media, Release
from ..models.base import now
from ..models.publish_extra import MarketingAsset
from . import has_reportlab

STORES = ("kdp", "ingram", "d2d", "audiobook", "beta", "query")
STORE_LABELS = {
    "kdp": "Amazon KDP", "ingram": "IngramSpark", "d2d": "Draft2Digital",
    "audiobook": "Audiobook (ACX / Findaway)", "beta": "Beta readers", "query": "Agent queries",
}
# Statuses the author sets by hand; computed status never overrides them.
MANUAL_STATUSES = ("submitted", "live")


@dataclass
class Ctx:
    words: int
    chapters: int
    drafted: int
    meta: BookMetadata
    covers: dict  # format -> CoverDesign with a front image
    assets: set
    pdf_ok: bool


@dataclass
class Item:
    key: str
    label: str
    required: bool
    check: Optional[Callable[[Ctx], tuple[bool, str]]] = None  # None => manual
    file: str = ""  # label shown in the Files column when satisfied


def _manuscript(c: Ctx):
    return c.words > 0, f"{c.drafted} chapters, {c.words:,} words" if c.words else "No drafted chapters"


def _pdf(c: Ctx):
    if not c.pdf_ok:
        return False, "Install reportlab to build the print interior"
    return _manuscript(c)


def _cover(fmt: str, what: str):
    def f(c: Ctx):
        return (fmt in c.covers, f"{what} ready" if fmt in c.covers else f"No {what.lower()} with a front image")
    return f


def _print_cover(c: Ctx):
    ok = "paperback" in c.covers or "hardcover" in c.covers
    return ok, "Cover wrap ready" if ok else "Design a paperback wrap with a front image"


def _desc(c: Ctx):
    n = len(c.meta.description.strip())
    return n >= 150, f"{n} characters" if n else "No description"


def _keywords(n: int):
    def f(c: Ctx):
        k = len([x for x in c.meta.keywords if str(x).strip()])
        return k >= n, f"{k} of {n}"
    return f


def _cats(n: int):
    def f(c: Ctx):
        k = len(c.meta.bisac)
        return k >= n, f"{k} of {n}"
    return f


def _isbn_print(c: Ctx):
    return bool(c.meta.isbn_print.strip()), c.meta.isbn_print or "No print ISBN"


def _isbn_any(c: Ctx):
    v = c.meta.isbn_print or c.meta.isbn_ebook
    return bool(v.strip()), v or "Store-assigned ASIN will be used"


def _price(c: Ctx):
    ok = any(v not in (None, "", 0) for v in (c.meta.price or {}).values())
    return ok, "Price set" if ok else "No list price"


def _asset(kind: str, label: str):
    def f(c: Ctx):
        return kind in c.assets, f"{label} drafted" if kind in c.assets else f"Generate a {label.lower()}"
    return f


def _sample(c: Ctx):
    return c.drafted >= 3, f"{min(c.drafted, 3)} of 3 opening chapters"


CHECKLISTS: dict[str, list[Item]] = {
    "kdp": [
        Item("interior_pdf", "Interior PDF", True, _pdf, "PDF"),
        Item("epub", "EPUB", True, _manuscript, "EPUB"),
        Item("cover_wrap", "Cover wrap", True, _print_cover, "Wrap"),
        Item("ebook_cover", "Ebook cover", True, _cover("ebook", "Ebook cover"), "JPG"),
        Item("description", "Description", True, _desc),
        Item("keywords", "7 keywords", True, _keywords(7)),
        Item("categories", "3 categories", True, _cats(3)),
        Item("isbn", "ISBN (optional)", False, _isbn_any),
    ],
    "ingram": [
        Item("interior_pdf", "Interior PDF", True, _pdf, "PDF"),
        Item("cover_wrap", "Cover wrap", True, _print_cover, "Wrap"),
        Item("isbn_print", "Print ISBN (required)", True, _isbn_print),
        Item("description", "Description", True, _desc),
        Item("categories", "BISAC category", True, _cats(1)),
        Item("price", "List price", True, _price),
    ],
    "d2d": [
        Item("epub", "EPUB", True, _manuscript, "EPUB"),
        Item("ebook_cover", "Ebook cover", True, _cover("ebook", "Ebook cover"), "JPG"),
        Item("description", "Description", True, _desc),
        Item("keywords", "Keywords", True, _keywords(3)),
        Item("categories", "Category", True, _cats(1)),
    ],
    "audiobook": [
        Item("manuscript", "Final manuscript", True, _manuscript, "DOCX"),
        Item("audio_cover", "Square cover (1:1)", True, _cover("audiobook", "Audiobook cover"), "JPG"),
        Item("narrator", "Narrator chosen", True),
        Item("audio_files", "Audio files mastered (ACX spec)", True),
        Item("description", "Description", True, _desc),
    ],
    "beta": [
        Item("epub", "Reader copy (EPUB)", True, _manuscript, "EPUB"),
        Item("readers", "Beta reader list", True),
        Item("questions", "Feedback questions", False),
    ],
    "query": [
        Item("query_letter", "Query letter", True, _asset("query_letter", "Query letter")),
        Item("synopsis", "One-page synopsis", True, _asset("synopsis_1p", "Synopsis")),
        Item("sample", "Sample pages", True, _sample, "DOCX"),
        Item("agent_list", "Agent list researched", True),
    ],
}


def _ctx(session: Session, project_id: str) -> Ctx:
    words, chapters, drafted = session.exec(
        select(func.coalesce(func.sum(Chapter.word_count), 0), func.count(Chapter.id),
               func.coalesce(func.sum(case((Chapter.word_count > 0, 1), else_=0)), 0))
        .where(Chapter.project_id == project_id)
    ).one()
    meta = get_metadata(session, project_id)
    covers = {}
    for c in session.exec(select(CoverDesign).where(CoverDesign.project_id == project_id,
                                                   CoverDesign.front_media_id.is_not(None))).all():
        if c.selected or c.format not in covers:
            covers[c.format] = c
    assets = set(session.exec(select(MarketingAsset.kind).where(MarketingAsset.project_id == project_id)).all())
    return Ctx(int(words), int(chapters), int(drafted), meta, covers, assets, has_reportlab())


def get_metadata(session: Session, project_id: str) -> BookMetadata:
    m = session.exec(select(BookMetadata).where(BookMetadata.project_id == project_id)).first()
    if not m:
        m = BookMetadata(project_id=project_id)
        session.add(m)
        session.commit()
        session.refresh(m)
    return m


def ensure_seeded(session: Session, project_id: str) -> list[Release]:
    rows = {r.store: r for r in session.exec(select(Release).where(Release.project_id == project_id)).all()}
    added = False
    for store in STORES:
        if store not in rows:
            r = Release(project_id=project_id, store=store, checklist={})
            session.add(r)
            rows[store] = r
            added = True
    if added:
        session.commit()
    order = {s: i for i, s in enumerate(STORES)}
    return sorted(rows.values(), key=lambda r: order.get(r.store, 99))


def evaluate(release: Release, ctx: Ctx) -> dict:
    items = []
    manual = release.checklist or {}
    for it in CHECKLISTS.get(release.store, []):
        if it.check:
            done, detail = it.check(ctx)
        else:
            done, detail = bool(manual.get(it.key)), "Tick when done"
        items.append({"key": it.key, "label": it.label, "required": it.required, "done": done,
                      "auto": it.check is not None, "detail": detail, "file": it.file if done else ""})
    blocked = any(i["required"] and not i["done"] for i in items)
    computed = "blocked" if blocked else "ready"
    status = release.status if release.status in MANUAL_STATUSES else computed
    return {
        "id": release.id, "store": release.store, "label": STORE_LABELS.get(release.store, release.store),
        "status": status, "computed_status": computed, "notes": release.notes, "items": items,
        "files": [i["file"] for i in items if i["file"]],
        "done": sum(1 for i in items if i["done"]), "total": len(items),
    }


def overview(session: Session, project_id: str) -> dict:
    rows = ensure_seeded(session, project_id)
    ctx = _ctx(session, project_id)
    out = [evaluate(r, ctx) for r in rows]
    dirty = False
    for r, o in zip(rows, out):  # persist the computed status so other screens can read it
        if r.status not in MANUAL_STATUSES and r.status != o["status"]:
            r.status = o["status"]
            r.updated_at = now()
            session.add(r)
            dirty = True
    if dirty:
        session.commit()
    # Launch steps: unique checklist keys across stores (a step shared by stores counts once).
    steps: dict[str, bool] = {}
    for o in out:
        for i in o["items"]:
            if not i["required"]:
                continue
            k = i["key"] if i["auto"] else f"{o['store']}.{i['key']}"
            steps[k] = steps.get(k, True) and i["done"]
    return {"releases": out, "steps_done": sum(steps.values()), "steps_total": len(steps)}


def media_for(session: Session, media_id: Optional[str]) -> Optional[Media]:
    return session.get(Media, media_id) if media_id else None
