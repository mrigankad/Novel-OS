"""
Story-level background block extraction via the Lorekeeper agent.

Processes pasted worldbuilding, character backstory, and author notes —
updates characters, plot threads, and story bible (not chapter prose).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from llm_client import LLMClient, LLMError
from state_manager import StoryState
from state_parser import apply_background_to_state, parse_lorekeeper


def _user_prompt(text: str, label: str, project_title: str) -> str:
    return f"""# BACKGROUND EXTRACTION — Story-Level

Analyze the following **background material** for the novel **{project_title}**.
This is NOT a chapter of prose — it is author notes, worldbuilding, character backstory, or series bible content.

- **Source label:** {label}
- **Word count:** {len(text.split())}

Extract characters, plot premise, relationships, and story bible data per your OUTPUT CONTRACT.
Emit `[BACKGROUND_STATE_UPDATE]` as your final block.

---

## BACKGROUND TEXT

{text}

---

Summarize briefly, then emit `[BACKGROUND_STATE_UPDATE]`.
"""


class BackgroundExtractor:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.background_dir = self.outputs_dir / "background"
        self.sources_dir = self.background_dir / "sources"
        self.reports_dir = self.background_dir / "reports"
        self.state = StoryState(str(self.project_path))
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def _ensure_dirs(self) -> None:
        for d in (self.sources_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)

    def extract(
        self,
        text: str,
        *,
        label: str = "Background",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[str], str]:
        """Extract story-level metadata from a background prose block."""
        log_fn = on_progress or (lambda msg: None)
        text = text.strip()
        if not text:
            raise ValueError("Empty background text")

        self._ensure_dirs()
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "background"
        src_path = self.sources_dir / f"{slug}.txt"
        src_path.write_text(text, encoding="utf-8")

        title = self.state.metadata.get("title", "Untitled")
        user_prompt = _user_prompt(text, label, title)
        prompt_path = self.reports_dir / f"{slug}_prompt.md"
        prompt_path.write_text(user_prompt, encoding="utf-8")

        if dry_run:
            log_fn(f"Dry-run — prompt saved to {prompt_path}")
            return [], str(prompt_path)

        log_fn(f"Extracting story metadata from {label!r} via Lorekeeper...")
        try:
            result = self._get_llm().run_agent("lorekeeper", user_prompt)
        except LLMError as e:
            raise RuntimeError(f"Background extraction failed: {e}") from e

        report_path = self.reports_dir / f"{slug}_report.md"
        report_path.write_text(result, encoding="utf-8")

        parsed = parse_lorekeeper(result)
        if not parsed:
            raise RuntimeError("Lorekeeper returned no [BACKGROUND_STATE_UPDATE] block")

        changes = apply_background_to_state(
            self.state, parsed, source="lorekeeper", label=label,
        )
        for line in changes:
            log_fn(f"    • {line}")

        # Refresh character profile markdown for any new/updated characters
        try:
            from import_pipeline import ImportPipeline  # noqa: WPS433
            ImportPipeline(str(self.project_path), llm=self._llm).write_character_profiles()
        except Exception:  # noqa: BLE001
            pass

        self.state.save_state()
        log_fn(f"=== BACKGROUND DONE: {len(changes)} updates ===")
        return changes, str(report_path)
