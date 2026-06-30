"""
Expand [[expand: instruction]] placeholders in chapter prose via the Editor agent.

Placeholders mark spots where the author wants AI-generated prose inserted in context.
Preview → keep / discard, same pattern as chapter_regenerator.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from llm_client import LLMClient, LLMError
from state_manager import StoryState
from state_parser import _KNOWN_TAGS, _strip_model_reasoning, extract_block

from chapter_regenerator import VALID_SOURCES


# [[expand: describe the market crowd]]  or  [[ai: same thing]]
PLACEHOLDER_RE = re.compile(
    r"\[\[(?:expand|ai)\s*:\s*(.+?)\]\]",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class PlaceholderMatch:
    start: int
    end: int
    instruction: str
    raw: str


def find_placeholders(text: str) -> List[PlaceholderMatch]:
    return [
        PlaceholderMatch(m.start(), m.end(), m.group(1).strip(), m.group(0))
        for m in PLACEHOLDER_RE.finditer(text)
    ]


def extract_expanded_chapter(text: str) -> str:
    """Pull prose from [EXPANDED_CHAPTER] or fall back like regenerator."""
    block = extract_block(text, "EXPANDED_CHAPTER")
    if block:
        return block.strip()
    from chapter_regenerator import extract_chapter_prose
    return extract_chapter_prose(text)


def _expand_prompt(
    chapter_number: int,
    source_label: str,
    source_text: str,
    placeholders: List[PlaceholderMatch],
    *,
    title: str,
    pov: str,
    tone: str,
    plot_context: str = "",
    instructions: str = "",
) -> str:
    ph_lines = "\n".join(
        f"- `{p.raw}` → expand as: {p.instruction}" for p in placeholders
    )
    extra = f"\n\n## Additional instructions\n{instructions.strip()}" if instructions.strip() else ""
    plot_block = f"\n{plot_context}\n" if plot_context.strip() else ""
    return f"""# EXPAND PLACEHOLDERS — Chapter {chapter_number}

The chapter below mixes **finished prose** with **placeholder markers** the author inserted.
Each placeholder uses the syntax `[[expand: brief instruction]]` (or `[[ai: …]]`).

Your job: replace **every** placeholder with full scene prose that fits seamlessly.
Keep all non-placeholder text **verbatim** unless a tiny connective tweak is required for flow.

- **Chapter title:** {title or "Untitled"}
- **POV:** {pov or "unspecified"}
- **Source stage:** {source_label}
- **Placeholders to expand:** {len(placeholders)}
- **Tone:** {tone or "match surrounding prose"}
{plot_block}
## Placeholders in this chapter

{ph_lines}
{extra}

## Chapter text (with placeholders)

```markdown
{source_text}
```

## Rules

1. Output the **complete chapter** with placeholders replaced by prose — no summaries.
2. Remove the `[[expand: …]]` / `[[ai: …]]` markers entirely from the output.
3. Match voice, tense, and POV of the surrounding text.
4. Do not add plot events the placeholders do not imply.
5. Emit `[EXPANDED_CHAPTER]` … `[/EXPANDED_CHAPTER]` with the full chapter only.
6. No chain-of-thought blocks.

Expand the placeholders now.
"""


class ChapterExpander:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.manuscript_dir = self.outputs_dir / "manuscript"
        self.feedback_dir = self.outputs_dir / "feedback"
        self.state = StoryState(str(self.project_path))
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _nnn(self, number: int) -> str:
        return f"{number:03d}"

    def preview_path(self, number: int) -> Path:
        return self.manuscript_dir / f"chapter_{self._nnn(number)}_expand_preview.md"

    def meta_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_expand_meta.json"

    def source_path(self, number: int, source: str) -> Path:
        from chapter_regenerator import ChapterRegenerator
        return ChapterRegenerator(str(self.project_path)).source_path(number, source)

    def read_source(self, number: int, source: str) -> str:
        from chapter_regenerator import ChapterRegenerator
        return ChapterRegenerator(str(self.project_path)).read_source(number, source)

    def expand(
        self,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, str]:
        log = on_progress or (lambda msg: None)
        source = source if source in VALID_SOURCES else "draft"
        source_text = self.read_source(number, source)
        placeholders = find_placeholders(source_text)
        if not placeholders:
            raise ValueError(
                "No [[expand: …]] placeholders found. "
                "Add markers like [[expand: describe the harbor at dawn]] in your text."
            )

        chapter = self.state.get_chapter(number) or self.state.create_chapter(number)
        self.manuscript_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        from plot_prompts import format_plot_threads_block  # noqa: WPS433
        plot_context = format_plot_threads_block(
            self.state.get_active_plot_threads(), max_threads=8,
        )

        user_prompt = _expand_prompt(
            number,
            source,
            source_text,
            placeholders,
            title=chapter.title or "",
            pov=chapter.pov_character or "",
            tone=self.state.style_profile.tone if self.state.style_profile else "",
            plot_context=plot_context,
            instructions=instructions,
        )
        prompt_path = self.feedback_dir / f"chapter_{self._nnn(number)}_expand_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return "", str(prompt_path)

        log(f"Expanding {len(placeholders)} placeholder(s) in chapter {number} ({source})…")
        try:
            raw = self._get_llm().run_agent("editor", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Placeholder expansion failed: {e}") from e

        report_path = self.feedback_dir / f"chapter_{self._nnn(number)}_expand_report.md"
        report_path.write_text(raw, encoding="utf-8")

        preview = extract_expanded_chapter(raw)
        if not preview:
            raise RuntimeError("Editor returned no chapter prose ([EXPANDED_CHAPTER] block missing)")

        if PLACEHOLDER_RE.search(preview):
            log("Warning: preview still contains placeholder markers — review before keeping")

        preview_path = self.preview_path(number)
        preview_path.write_text(preview, encoding="utf-8")
        meta = {
            "source": source,
            "instructions": instructions.strip(),
            "placeholder_count": len(placeholders),
            "original_word_count": len(source_text.split()),
            "preview_word_count": len(preview.split()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path(number).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"Expand preview ready ({meta['preview_word_count']} words)")
        return preview, str(report_path)
