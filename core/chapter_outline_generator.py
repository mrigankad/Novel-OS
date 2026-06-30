"""
Generate a structured chapter outline (beat sheet).

Modes:
- **notes** — forward-plan from author direction (no prose required)
- **draft / revised / final** — reverse-engineer outline from existing chapter text

Uses the Architect agent. Preview → keep / discard before writing chapter_NNN_outline.md.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

from chapter_regenerator import ChapterRegenerator, VALID_SOURCES
from llm_client import LLMClient, LLMError
from state_parser import _KNOWN_TAGS, _strip_model_reasoning, extract_block

OUTLINE_SOURCES = frozenset(VALID_SOURCES | {"notes"})


def extract_chapter_outline(text: str) -> str:
    """Pull beat-sheet markdown from an Architect response."""
    block = extract_block(text, "CHAPTER_OUTLINE")
    if block:
        return block.strip()

    cleaned = _strip_model_reasoning(text)
    for tag in _KNOWN_TAGS:
        cleaned = re.sub(
            rf"\[{re.escape(tag)}\].*?\[/{re.escape(tag)}\]",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
    cleaned = re.sub(r"\[/?[A-Z_]+\]", "", cleaned)
    # Drop leading conversational preamble before first markdown heading
    lines = cleaned.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            return "\n".join(lines[i:]).strip()
    return cleaned.strip()


def _outline_prompt(
    chapter_number: int,
    source_label: str,
    source_text: str,
    *,
    title: str,
    pov: str,
    instructions: str,
    plot_context: str = "",
) -> str:
    extra = f"\n\n## Additional instructions\n{instructions.strip()}" if instructions.strip() else ""
    plot_block = f"\n{plot_context}\n" if plot_context.strip() else ""
    return f"""# OUTLINE FROM PROSE — Chapter {chapter_number}

You are the **Architect**. Read the chapter prose below and produce a **beat-sheet outline**
that captures what actually happens — not what was planned. This reverse-engineers structure
from finished (or draft) text so the outline can guide revisions or later chapters.

- **Chapter title:** {title or "Untitled"}
- **POV:** {pov or "unspecified"}
- **Source stage:** {source_label}
- **Prose word count:** {len(source_text.split())}
{plot_block}
## Chapter prose ({source_label})

```markdown
{source_text}
```
{extra}

## Output contract

Return:
1. Optional brief note (2–3 sentences) on structure you inferred.
2. `[CHAPTER_OUTLINE]` … `[/CHAPTER_OUTLINE]` containing the **complete** beat-sheet in Markdown:

```
# Chapter {chapter_number}: <title>

**POV:** … | **Source:** reverse-engineered from {source_label}

## Chapter Goal
<what changes by end of chapter>

## Beats
1. **<beat name>** — <what happens>
2. …
(4–10 beats matching the prose)

## Characters & threads
- <who appears, plot threads advanced>

## Continuity Notes
- <facts to preserve>

## Ending Hook
<how the chapter ends>
```

3. Do **not** emit chain-of-thought or reasoning blocks.
4. Outline only — **no new prose**, dialogue, or narrative paragraphs.

Write the beat-sheet now.
"""


def _bible_context(state) -> str:
    bible = state.story_bible or {}
    parts: list[str] = []
    logline = str(bible.get("logline", "")).strip()
    if logline:
        parts.append(f"- **Logline:** {logline}")
    tone = str(bible.get("tone", "")).strip()
    if tone:
        parts.append(f"- **Tone:** {tone}")
    for key, label in (
        ("premise_beats", "Premise beats"),
        ("themes", "Themes"),
    ):
        raw = bible.get(key)
        if isinstance(raw, list) and raw:
            lines = [str(x).strip() for x in raw[:6] if str(x).strip()]
            if lines:
                parts.append(f"- **{label}:** " + "; ".join(lines))
    return "\n".join(parts)


def _notes_outline_prompt(
    chapter_number: int,
    *,
    title: str,
    pov: str,
    target_words: int,
    instructions: str,
    plot_context: str,
    character_context: str,
    bible_context: str,
    existing_outline: str,
) -> str:
    existing_block = ""
    if existing_outline.strip():
        existing_block = f"""
## Current outline (revise or replace using author notes)

```markdown
{existing_outline.strip()}
```
"""
    bible_block = f"\n## Story bible\n{bible_context}\n" if bible_context.strip() else ""
    char_block = f"\n## Relevant characters\n{character_context}\n" if character_context.strip() else ""
    plot_block = f"\n{plot_context}\n" if plot_context.strip() else ""

    return f"""# OUTLINE FROM AUTHOR NOTES — Chapter {chapter_number}

You are the **Architect**. The author has provided direction for this chapter's beat-sheet.
Produce a structured **outline** the Scribe will later expand into prose. **No dialogue or narrative paragraphs.**

- **Chapter title:** {title or "Propose a fitting title"}
- **POV:** {pov or "Specify from notes or cast"}
- **Target word count:** {target_words}
{bible_block}{char_block}{plot_block}{existing_block}
## Author direction (required)

{instructions.strip()}

## Output contract

Return:
1. Optional brief note (2–3 sentences) on how you interpreted the author's direction.
2. `[CHAPTER_OUTLINE]` … `[/CHAPTER_OUTLINE]` containing the **complete** beat-sheet in Markdown:

```
# Chapter {chapter_number}: <title>

**POV:** … | **Target:** {target_words} words

## Chapter Goal
<what must change by end of chapter>

## Beats
1. **<beat name>** — <1-2 sentence summary; conflict/turn>
2. …
(4–7 beats)

## Continuity Notes
- <facts the Scribe must honor>

## Ending Hook
<pull into next chapter>
```

3. Do **not** emit chain-of-thought or reasoning blocks.
4. Outline only — honor the author's notes; use story context to fill gaps.

Write the beat-sheet now.
"""


class ChapterOutlineGenerator:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.feedback_dir = self.outputs_dir / "feedback"
        self._reader = ChapterRegenerator(project_path, llm=llm)
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _nnn(self, number: int) -> str:
        return f"{number:03d}"

    def preview_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_outline_preview.md"

    def meta_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_outline_preview_meta.json"

    def _read_existing_outline(self, number: int) -> str:
        path = self.outputs_dir / f"chapter_{self._nnn(number)}_outline.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def generate(
        self,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, str]:
        log = on_progress or (lambda msg: None)
        if source not in OUTLINE_SOURCES:
            source = "draft"

        state = self._reader.state
        chapter = state.get_chapter(number)
        if not chapter:
            chapter = state.create_chapter(number)

        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        from plot_prompts import format_plot_threads_block  # noqa: WPS433
        plot_context = format_plot_threads_block(
            state.get_active_plot_threads(), max_threads=8,
        )

        if source == "notes":
            if not instructions.strip():
                raise ValueError("Outline notes / direction are required for notes-based generation.")
            char_lines: list[str] = []
            for char in state.get_all_characters():
                if char.last_appearance_chapter >= number - 3 or char.last_appearance_chapter == 0:
                    char_lines.append(
                        f"- **{char.full_name}** ({char.role}) — "
                        f"{char.current_location or 'unknown location'}, "
                        f"{char.emotional_state or 'unknown mood'}"
                    )
            user_prompt = _notes_outline_prompt(
                number,
                title=chapter.title or "",
                pov=chapter.pov_character or "",
                target_words=chapter.target_word_count or 2500,
                instructions=instructions,
                plot_context=plot_context,
                character_context="\n".join(char_lines[:12]),
                bible_context=_bible_context(state),
                existing_outline=self._read_existing_outline(number),
            )
            source_text = ""
            original_wc = 0
        else:
            source_text = self._reader.read_source(number, source)
            user_prompt = _outline_prompt(
                number,
                source,
                source_text,
                title=chapter.title or "",
                pov=chapter.pov_character or "",
                instructions=instructions,
                plot_context=plot_context,
            )
            original_wc = len(source_text.split())

        prompt_path = self.feedback_dir / f"chapter_{self._nnn(number)}_outline_generate_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return "", str(prompt_path)

        label = "author notes" if source == "notes" else source
        log(f"Generating outline for chapter {number} from {label} via Architect…")
        try:
            raw = self._get_llm().run_agent("architect", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Outline generation failed: {e}") from e

        report_path = self.feedback_dir / f"chapter_{self._nnn(number)}_outline_generate_report.md"
        report_path.write_text(raw, encoding="utf-8")

        preview = extract_chapter_outline(raw)
        if not preview:
            raise RuntimeError("Architect returned no outline ([CHAPTER_OUTLINE] block missing)")

        preview_path = self.preview_path(number)
        preview_path.write_text(preview, encoding="utf-8")
        meta = {
            "source": source,
            "instructions": instructions.strip(),
            "original_word_count": original_wc,
            "preview_word_count": len(preview.split()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path(number).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"Outline preview ready ({len(preview.split())} words)")
        return preview, str(report_path)
