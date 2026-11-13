"""
Novel OS - MCP server

Lets Claude Code, Claude Desktop, Cursor, Codex or any MCP client work on a
Novel OS book: read the story state, read and write chapters, search the Codex
and run the continuity checks. It goes through the same ProjectService the
Studio uses, so edits made here show up in the Studio and vice versa.

Claude Code (stdio):

    claude mcp add novel-os -- python -m core.mcp_server --projects ./projects

Any client over Streamable HTTP:

    python -m core.mcp_server --projects ./projects --http --port 8765
    claude mcp add --transport http novel-os http://localhost:8765/mcp

The host's own model does the writing; this server only exposes the book.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

INSTRUCTIONS = """\
Novel OS holds a novel's canonical story state: characters, plot threads,
timeline, Codex and chapter text. Before drafting or editing a chapter,
call get_story_state and get_chapter so you write from canon, not memory.
After writing, call run_continuity for that chapter and fix or explain any
critical findings. Never invent Codex facts silently - add them with
add_codex_entry so the rest of the book stays consistent."""


def _dump(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    return obj


def build_server(projects_dir: Path, *, host: str = "127.0.0.1", port: int = 8765) -> FastMCP:
    # Imported lazily so `--help` works without the API extras installed.
    from api.services import ProjectService

    svc = ProjectService(projects_dir)
    mcp = FastMCP("novel-os", instructions=INSTRUCTIONS, host=host, port=port)

    @mcp.tool()
    def list_projects() -> list[dict]:
        """List the novels in this workspace (id, title, genre, chapter and word counts)."""
        return _dump(svc.list_projects())

    @mcp.tool()
    def get_story_state(project_id: str) -> dict:
        """The book's canonical story state: bible, characters, plot threads, timeline, style profile."""
        return svc.raw_state(project_id)

    @mcp.tool()
    def list_chapters(project_id: str) -> list[dict]:
        """Chapters with number, title, POV, status and word count."""
        return _dump(svc.list_chapters(project_id))

    @mcp.tool()
    def get_chapter(project_id: str, number: int) -> dict:
        """One chapter: outline, metadata and the current final text (if any)."""
        detail = _dump(svc.chapter_detail(project_id, number))
        detail["final_text"] = svc.get_final_text(project_id, number)
        return detail

    @mcp.tool()
    def write_chapter(project_id: str, number: int, text: str) -> dict:
        """Save Markdown as the chapter's final text. Replaces the current final text.

        Earlier versions are kept by the Studio's provenance history.
        """
        svc.ensure_chapter(project_id, number)
        words = svc.save_final(project_id, number, text)
        return {"saved": True, "chapter": number, "word_count": words}

    @mcp.tool()
    def search_codex(project_id: str, query: str, limit: int = 12) -> list[dict]:
        """Keyword search across Codex entries (characters, places, items, lore) and chapter titles."""
        return _dump(svc.search(project_id, query, limit=limit))

    @mcp.tool()
    def list_codex(project_id: str, entry_type: Optional[str] = None) -> list[dict]:
        """All Codex entries, optionally filtered by type (character, location, item, lore...)."""
        return _dump(svc.list_codex(project_id, entry_type))

    @mcp.tool()
    def add_codex_entry(
        project_id: str, entry_type: str, name: str, summary: str = "", notes: str = "",
    ) -> list[dict]:
        """Record a new fact-bearing entity in the Codex so every agent sees it."""
        return _dump(svc.add_codex_entry(project_id, entry_type, name, summary=summary, notes=notes))

    @mcp.tool()
    def run_continuity(project_id: str, chapter: Optional[int] = None) -> dict:
        """Run the deterministic continuity checks (free, instant).

        Returns findings with severity critical / warning / info. Findings the
        author marked "intentional" are already filtered out.
        """
        findings = svc.continuity_findings(project_id, chapter)
        return {
            "critical": sum(1 for f in findings if f.get("severity") == "critical"),
            "findings": findings,
        }

    @mcp.resource("novel://{project_id}/chapter/{number}")
    def chapter_text(project_id: str, number: int) -> str:
        """A chapter's final text as Markdown."""
        return svc.get_final_text(project_id, int(number)) or ""

    return mcp


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(prog="novel-os mcp", description=__doc__.split("\n\n")[0])
    ap.add_argument("--projects", default=os.environ.get("NOVEL_OS_PROJECTS_DIR", "./projects"),
                    help="Workspace folder containing Novel OS projects (default: ./projects)")
    ap.add_argument("--http", action="store_true", help="Serve Streamable HTTP instead of stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)

    server = build_server(Path(args.projects).resolve(), host=args.host, port=args.port)
    server.run(transport="streamable-http" if args.http else "stdio")


if __name__ == "__main__":
    main()
