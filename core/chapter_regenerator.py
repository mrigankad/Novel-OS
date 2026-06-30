"""
Regenerate chapter prose from existing text via the Editor agent.

Writes a preview file only — the user keeps or discards before anything is committed
to draft / revised / final.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

from llm_client import LLMClient, LLMError
from state_manager import StoryState
from state_parser import _KNOWN_TAGS, _strip_model_reasoning, extract_block


VALID_SOURCES = frozenset({"draft", "revised", "final"})


def extract_chapter_prose(text: str) -> str:
    """Pull chapter prose from an Editor response."""
    block = extract_block(text, "REVISED_CHAPTER")
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
    return cleaned.strip()


def _regenerate_prompt(
    chapter_number: int,
    source_label: str,
    source_text: str,
    *,
    title: str,
    pov: str,
    instructions: str,
    tone: str,
    plot_context: str = "",
) -> str:
    extra = f"\n\n## Additional instructions\n{instructions.strip()}" if instructions.strip() else ""
    plot_block = f"\n{plot_context}\n" if plot_context.strip() else ""
    return f"""# CHAPTER REGENERATION — Chapter {chapter_number}

Rewrite the chapter below. Preserve the same plot events, character beats, and POV.
Improve clarity, pacing, voice, and prose quality. Do not summarize — output the **full chapter**.

- **Chapter title:** {title or "Untitled"}
- **POV:** {pov or "unspecified"}
- **Source stage:** {source_label}
- **Word count:** {len(source_text.split())}
- **Tone to maintain:** {tone or "match the original"}
{plot_block}
## Original chapter ({source_label})

```markdown
{source_text}
```
{extra}

## Output contract

1. Optional brief note (2–3 sentences) on what you changed.
2. `[REVISED_CHAPTER]` … `[/REVISED_CHAPTER]` containing the **complete** regenerated chapter prose.
3. Do **not** emit chain-of-thought or reasoning blocks.

Regenerate the chapter now.
"""


class ChapterRegenerator:
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
        return self.manuscript_dir / f"chapter_{self._nnn(number)}_regenerate_preview.md"

    def meta_path(self, number: int) -> Path:
        return self.feedback_dir / f"chapter_{self._nnn(number)}_regenerate_meta.json"

    def source_path(self, number: int, source: str) -> Path:
        nnn = self._nnn(number)
        if source == "draft":
            return self.manuscript_dir / f"chapter_{nnn}_draft.md"
        if source == "revised":
            return self.manuscript_dir / f"chapter_{nnn}_revised.md"
        if source == "final":
            return self.manuscript_dir / f"chapter_{nnn}_final.md"
        raise ValueError(f"Invalid source {source!r}")

    def read_source(self, number: int, source: str) -> str:
        if source not in VALID_SOURCES:
            raise ValueError(f"Invalid source {source!r}")
        path = self.source_path(number, source)
        if not path.exists():
            raise FileNotFoundError(f"No {source} text for chapter {number}")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"Chapter {number} {source} is empty")
        return text

    def regenerate(
        self,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, str]:
        """Run LLM regeneration; save preview + meta. Returns (preview_text, report_path)."""
        log = on_progress or (lambda msg: None)
        source = source if source in VALID_SOURCES else "draft"
        source_text = self.read_source(number, source)

        chapter = self.state.get_chapter(number)
        if not chapter:
            chapter = self.state.create_chapter(number)

        self.manuscript_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

        from plot_prompts import format_plot_threads_block  # noqa: WPS433
        plot_context = format_plot_threads_block(
            self.state.get_active_plot_threads(), max_threads=8,
        )

        user_prompt = _regenerate_prompt(
            number,
            source,
            source_text,
            title=chapter.title or "",
            pov=chapter.pov_character or "",
            instructions=instructions,
            tone=self.state.style_profile.tone if self.state.style_profile else "",
            plot_context=plot_context,
        )
        prompt_path = self.feedback_dir / f"chapter_{self._nnn(number)}_regenerate_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log(f"Dry-run — prompt saved to {prompt_path}")
            return "", str(prompt_path)

        log(f"Regenerating chapter {number} from {source} via Editor…")
        try:
            raw = self._get_llm().run_agent("editor", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Chapter regeneration failed: {e}") from e

        report_path = self.feedback_dir / f"chapter_{self._nnn(number)}_regenerate_report.md"
        report_path.write_text(raw, encoding="utf-8")

        preview = extract_chapter_prose(raw)
        if not preview:
            raise RuntimeError("Editor returned no chapter prose ([REVISED_CHAPTER] block missing)")

        preview_path = self.preview_path(number)
        preview_path.write_text(preview, encoding="utf-8")
        meta = {
            "source": source,
            "instructions": instructions.strip(),
            "original_word_count": len(source_text.split()),
            "preview_word_count": len(preview.split()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.meta_path(number).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        log(f"Preview ready ({meta['preview_word_count']} words)")
        return preview, str(report_path)
