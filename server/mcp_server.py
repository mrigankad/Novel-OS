"""Novel OS MCP server: lets Claude Code, Claude Desktop, Cursor or Codex work on a book.

    python -m server.mcp_server                    # stdio (Claude Code, .mcp.json)
    python -m server.mcp_server --http --port 8765 # Streamable HTTP at http://127.0.0.1:8765/mcp

Works directly on the studio database (server.db), so changes show up in the web app.
"""

from __future__ import annotations

import argparse
import re
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session, func, or_, select

from .db import engine, init_db
from .models import Chapter, ChapterVersion, CodexEntry, Memory, PlotThread, Project
from .models.base import now
from .services.continuity import continuity_findings

INSTRUCTIONS = """\
Novel OS holds the canon for the author's books: story bible, chapters, Codex (characters,
places, lore), open plot threads and shared memory.

Before writing or revising prose:
  1. call get_book to read the bible, chapter list and open plot threads;
  2. call search_codex and recall_memory for every character, place and fact you touch;
  3. call get_chapter for the chapters either side of the one you are working on.
After writing:
  - save prose with write_chapter (it keeps a version, so nothing is lost);
  - record any new fact you introduced with add_codex_entry or remember;
  - call run_continuity and fix or report what it finds.
Never contradict canon silently. If the author's request conflicts with canon, say so.
"""


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _project(s: Session, project_id: str) -> Project:
    p = s.get(Project, project_id)
    if not p:
        raise ValueError(f"No project with id '{project_id}'. Call list_projects first.")
    return p


def build_server(host: str = "127.0.0.1", port: int = 8765) -> FastMCP:
    init_db()
    mcp = FastMCP("novel-os", instructions=INSTRUCTIONS, host=host, port=port)

    @mcp.tool()
    def list_projects() -> list[dict[str, Any]]:
        """List every book in the studio with its id, title, genre, status and word count."""
        with Session(engine()) as s:
            words = dict(s.exec(select(Chapter.project_id, func.coalesce(func.sum(Chapter.word_count), 0))
                                .group_by(Chapter.project_id)).all())
            return [{"id": p.id, "title": p.title, "genre": p.genre, "status": p.status,
                     "word_count": int(words.get(p.id, 0))}
                    for p in s.exec(select(Project).order_by(Project.updated_at.desc())).all()]

    @mcp.tool()
    def get_book(project_id: str) -> dict[str, Any]:
        """Read a book's canon: project, story bible, chapter list (no text) and open plot threads."""
        with Session(engine()) as s:
            p = _project(s, project_id)
            chapters = s.exec(select(Chapter).where(Chapter.project_id == p.id).order_by(Chapter.number)).all()
            threads = s.exec(select(PlotThread).where(PlotThread.project_id == p.id,
                                                      PlotThread.status == "open")).all()
            return {
                "project": {"id": p.id, "title": p.title, "author": p.author, "genre": p.genre,
                            "premise": p.premise, "status": p.status, "target_words": p.target_words},
                "bible": p.bible,
                "chapters": [{"number": c.number, "title": c.title, "status": c.status, "pov": c.pov,
                              "synopsis": c.synopsis, "word_count": c.word_count} for c in chapters],
                "open_plot_threads": [{"name": t.name, "kind": t.kind, "planted_chapter": t.planted_chapter,
                                       "target_chapter": t.target_chapter, "notes": t.notes} for t in threads],
            }

    @mcp.tool()
    def get_chapter(project_id: str, number: int) -> dict[str, Any]:
        """Read one chapter, including its full text, synopsis and beats."""
        with Session(engine()) as s:
            c = s.exec(select(Chapter).where(Chapter.project_id == project_id, Chapter.number == number)).first()
            if not c:
                raise ValueError(f"Chapter {number} doesn't exist yet.")
            return {"number": c.number, "title": c.title, "status": c.status, "pov": c.pov,
                    "synopsis": c.synopsis, "beats": c.beats, "text": c.text, "word_count": c.word_count}

    @mcp.tool()
    def write_chapter(project_id: str, number: int, text: str, title: Optional[str] = None,
                      note: str = "") -> dict[str, Any]:
        """Save a chapter's prose (Markdown). Creates the chapter if needed and keeps a draft version."""
        with Session(engine()) as s:
            p = _project(s, project_id)
            c = s.exec(select(Chapter).where(Chapter.project_id == p.id, Chapter.number == number)).first()
            if not c:
                c = Chapter(project_id=p.id, number=number, title=title or f"Chapter {number}")
            if title:
                c.title = title
            c.text = text
            c.word_count = _words(text)
            if c.status == "planned":
                c.status = "drafted"
            c.updated_at = now()
            p.updated_at = now()
            s.add(c)
            s.add(p)
            s.flush()
            s.add(ChapterVersion(chapter_id=c.id, kind="draft", text=text, word_count=c.word_count,
                                 produced_by="mcp", note=note))
            s.commit()
            return {"ok": True, "number": c.number, "title": c.title, "word_count": c.word_count}

    @mcp.tool()
    def search_codex(project_id: str, query: str = "", kind: Optional[str] = None) -> list[dict[str, Any]]:
        """Find Codex entries (characters, locations, items, lore...) by name, alias or summary."""
        with Session(engine()) as s:
            stmt = select(CodexEntry).where(CodexEntry.project_id == project_id)
            if kind:
                stmt = stmt.where(CodexEntry.kind == kind)
            rows = s.exec(stmt.order_by(CodexEntry.name)).all()
            q = query.lower().strip()
            hits = [e for e in rows if not q or q in e.name.lower() or q in e.summary.lower()
                    or any(q in str(a).lower() for a in e.aliases)]
            return [{"id": e.id, "kind": e.kind, "name": e.name, "aliases": e.aliases, "role": e.role,
                     "summary": e.summary, "facts": e.facts} for e in hits[:50]]

    @mcp.tool()
    def add_codex_entry(project_id: str, kind: str, name: str, summary: str = "",
                        facts: Optional[dict] = None, aliases: Optional[list[str]] = None,
                        first_chapter: Optional[int] = None) -> dict[str, Any]:
        """Add a new canon entry. kind: character | location | item | lore | faction | event | theme."""
        with Session(engine()) as s:
            _project(s, project_id)
            e = CodexEntry(project_id=project_id, kind=kind, name=name, summary=summary,
                           facts=facts or {}, aliases=aliases or [], first_chapter=first_chapter)
            s.add(e)
            s.commit()
            return {"ok": True, "id": e.id, "name": e.name}

    @mcp.tool()
    def recall_memory(project_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Keyword search over the book's shared memory (facts, decisions, preferences)."""
        terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
        with Session(engine()) as s:
            stmt = select(Memory).where(Memory.project_id == project_id)
            if terms:
                stmt = stmt.where(or_(*[func.lower(Memory.content).contains(t) for t in terms]))
            rows = s.exec(stmt).all()
            scored = sorted(rows, key=lambda m: (sum(m.content.lower().count(t) for t in terms)
                                                 + m.importance + (1 if m.pinned else 0)), reverse=True)
            return [{"kind": m.kind, "content": m.content, "chapter": m.chapter, "source": m.source}
                    for m in scored[:max(1, min(limit, 50))]]

    @mcp.tool()
    def remember(project_id: str, content: str, kind: str = "fact", chapter: Optional[int] = None,
                 importance: float = 0.6) -> dict[str, Any]:
        """Record a new fact or decision in shared memory so every agent can recall it."""
        with Session(engine()) as s:
            _project(s, project_id)
            m = Memory(project_id=project_id, agent_id=None, kind=kind, content=content, chapter=chapter,
                       source="mcp", importance=importance)
            s.add(m)
            s.commit()
            return {"ok": True, "id": m.id}

    @mcp.tool()
    def run_continuity(project_id: str, chapter: Optional[int] = None) -> dict[str, Any]:
        """Run the deterministic continuity checks and return findings (critical, warning, info)."""
        with Session(engine()) as s:
            _project(s, project_id)
            findings = continuity_findings(s, project_id, chapter)
            return {"count": len(findings), "findings": findings}

    return mcp


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Novel OS MCP server")
    ap.add_argument("--http", action="store_true", help="serve Streamable HTTP instead of stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    server = build_server(args.host, args.port)
    server.run("streamable-http" if args.http else "stdio")


if __name__ == "__main__":
    main()
