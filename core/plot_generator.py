"""
Generate or refine a plot thread description from its subplots and story bible context.

The story bible supplies supporting material only — never new plot threads or subplots.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from llm_client import LLMClient, LLMError
from state_manager import PlotThread, StoryState
from state_parser import extract_block, parse_fields, _as_list


_BIBLE_SECTIONS = (
    ("logline", "Logline"),
    ("tone", "Tone"),
    ("themes", "Themes"),
    ("setting_summary", "Setting"),
    ("historical_context", "Historical context"),
    ("premise_beats", "Premise beats"),
    ("world_rules", "World rules"),
    ("import_notes", "Story notes"),
)


def _format_bible_section(label: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        lines = [str(item).strip() for item in value if str(item).strip()]
        if not lines:
            return ""
        return f"### {label}\n" + "\n".join(f"- {line}" for line in lines)
    text = str(value).strip()
    if not text or text.lower() in ("none", "unknown", "n/a", "{}"):
        return ""
    return f"### {label}\n{text}"


def collect_bible_supporting_context(state: StoryState) -> str:
    """Story bible excerpts for enrichment — not for inventing new plot threads."""
    parts: List[str] = []
    bible = state.story_bible or {}
    for key, label in _BIBLE_SECTIONS:
        block = _format_bible_section(label, bible.get(key))
        if block:
            parts.append(block)
    setting = bible.get("setting")
    if isinstance(setting, dict) and setting:
        bits = []
        for field in ("place", "time", "atmosphere", "summary"):
            val = setting.get(field)
            if val and str(val).strip():
                bits.append(f"- {field}: {val}")
        if bits:
            parts.append("### Setting (structured)\n" + "\n".join(bits))
    if not parts:
        return "(Story bible is empty — rely on the plot thread and subplots only.)"
    return "\n\n".join(parts)


def parse_plot_thread_update(text: str) -> Dict[str, Any]:
    block = extract_block(text, "PLOT_THREAD_UPDATE")
    if not block:
        return {}
    fields = parse_fields(block)
    description = str(fields.get("Description") or fields.get("description") or "").strip()
    suggestions_raw = fields.get("Bible_Suggestions") or fields.get("bible_suggestions") or []
    suggestions = _as_list(suggestions_raw) if suggestions_raw else []
    suggestions = [str(s).strip() for s in suggestions if str(s).strip()]
    return {"description": description, "bible_suggestions": suggestions}


def _plot_prompt(
    *,
    project_title: str,
    genre: str,
    thread: PlotThread,
    other_threads: List[PlotThread],
    bible_context: str,
    author_prompt: str = "",
) -> str:
    subplots = "\n".join(f"- {line}" for line in thread.subplots if line.strip()) or "(none yet)"
    others = "\n".join(
        f"- {t.name} ({t.thread_type})"
        for t in other_threads
        if t.id != thread.id
    ) or "(none)"

    extra = ""
    if author_prompt.strip():
        extra = f"\n## Author direction\n\n{author_prompt.strip()}\n"

    return f"""# PLOT THREAD DESCRIPTION GENERATION

Write or refine the **description** for one existing plot thread. Use the thread name, current description, and **subplots list** as primary source material.

**Critical rules:**
- Do **NOT** invent new plot threads or new subplot lines.
- Do **NOT** output `[PLOT_THREADS]` or any directive that creates threads.
- The story bible below is **supporting context only** — cite relevant themes, setting, or rules that could enrich *this* thread's description.
- `Bible_Suggestions` are optional bullets the author may copy manually; they must not become new plots/subplots by themselves.

- **Project:** {project_title or "Untitled"}
- **Genre:** {genre or "unspecified"}

## Target plot thread

- **Name:** {thread.name}
- **Type:** {thread.thread_type}
- **Status:** {thread.status}
- **Current description:** {thread.description or "(empty)"}

### Subplots (authoritative — do not replace or extend this list in output)

{subplots}

## Other plot threads (for context only — do not merge or duplicate)

{others}

## Story bible (supporting material only)

{bible_context}
{extra}
---

1. Brief note (2–4 sentences) on how subplots and bible context inform this plot.
2. Emit `[PLOT_THREAD_UPDATE]` as your **final** block:

- `Description` — 2–6 sentences summarizing this plot thread for downstream prompts. Incorporate subplots; weave in bible support where relevant.
- `Bible_Suggestions` — bulleted list (or `[None]`) of specific bible facts/themes/settings the author might add to this plot or its subplots manually. Each bullet must reference existing bible material, not new plot threads.

Use exact field names. No code fences inside the block.
"""


class PlotGenerator:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.feedback_dir = self.project_path / "outputs" / "feedback"
        self.state = StoryState(str(self.project_path))
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def preview_path(self, thread_id: str) -> Path:
        return self.feedback_dir / f"plot_generate_{thread_id}_preview.json"

    def generate(
        self,
        thread_id: str,
        *,
        prompt: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        log = on_progress or (lambda msg: None)
        thread = self.state.plot_threads.get(thread_id)
        if thread is None:
            raise ValueError(f"Unknown plot thread {thread_id!r}")

        meta = self.state.metadata
        bible_context = collect_bible_supporting_context(self.state)
        others = list(self.state.plot_threads.values())
        user_prompt = _plot_prompt(
            project_title=meta.get("title", ""),
            genre=meta.get("genre", "") or str(self.state.story_bible.get("genre", "")),
            thread=thread,
            other_threads=others,
            bible_context=bible_context,
            author_prompt=prompt,
        )
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = self.feedback_dir / f"plot_generate_{thread_id}_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return {}

        log(f"Generating plot description for {thread.name!r}…")
        try:
            raw = self._get_llm().run_agent("lorekeeper", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Plot generation failed: {e}") from e

        report_path = self.feedback_dir / f"plot_generate_{thread_id}_report.md"
        report_path.write_text(raw, encoding="utf-8")

        parsed = parse_plot_thread_update(raw)
        description = parsed.get("description", "")
        if not description:
            raise RuntimeError("Agent returned no [PLOT_THREAD_UPDATE] Description.")

        preview = {
            "thread_id": thread_id,
            "thread_name": thread.name,
            "prompt": prompt.strip(),
            "description": description,
            "previous_description": thread.description or "",
            "bible_suggestions": parsed.get("bible_suggestions") or [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.preview_path(thread_id).write_text(json.dumps(preview, indent=2), encoding="utf-8")
        log("Plot description ready")
        return preview
