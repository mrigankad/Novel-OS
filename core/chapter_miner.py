"""
Focused chapter text miners — extract plots, characters, or story bible separately.

Each mode runs the Archivist (or Lorekeeper for bible) with a narrow prompt and applies
only the relevant state updates.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple

from chapter_regenerator import ChapterRegenerator, VALID_SOURCES
from llm_client import LLMClient, LLMError
from state_manager import StoryState, project_state_lock
from state_parser import (
    apply_chapter_bible_mine,
    apply_chapter_character_mine,
    apply_chapter_plot_mine,
    parse_chapter_bible,
    parse_chapter_character,
    parse_chapter_plot,
)

MINE_KINDS = frozenset({"plots", "characters", "bible"})


def _plot_prompt(chapter_number: int, text: str, source: str, title: str, threads_block: str) -> str:
    return f"""# CHAPTER PLOT MINING — Chapter {chapter_number}

Read this chapter prose and extract **plot threads and subplot beats only**.
Do not rewrite the chapter. Do not extract character sheets or world bible — plots only.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source}
- **Word count:** {len(text.split())}

{threads_block}

## Hierarchy rules (critical)

- **Major arcs** (`main`) are the only top-level plot threads.
- **Related plots** (`subplot`, `character_arc`, `mystery`) must be stored **under** a major arc — never as separate top-level threads.
- Use `Subplot_Threads` for each related plot: `Parent Major Arc | Subplot Name | one-sentence description`
- Use `Subplot_Beats` for chapter-specific beats on any thread: `Thread or Parent Name | beat in this chapter`
- Use `Resolved_Subplots` for subplots **concluded or settled** in this chapter (remove from active tracking). Format: `Parent Major Arc | Subplot Name | optional one-line resolution`
- Review **Subplots** under each existing major arc above — if one is resolved in this chapter, list it in `Resolved_Subplots`.

## Chapter text

{text}

---

1. Brief summary (2–4 sentences) of plot movement in this chapter.
2. Emit `[CHAPTER_PLOT_UPDATE]` as your **final** block with these fields:

- `Plot_Threads` — bulleted **major arcs only**. Format: `Thread Name | main | one-sentence description | related characters (comma-separated)`
- `Subplot_Threads` — bulleted related plots to nest under a parent. Format: `Parent Major Arc | Subplot Name | one-sentence description`
- `Subplot_Beats` — bulleted. Format: `Parent or Thread Name | one-line beat that happens in this chapter`
- `Resolved_Subplots` — bulleted subplots concluded in this chapter (removed from active list). Format: `Parent Major Arc | Subplot Name | optional resolution note`
- `Plot_Events` — bulleted one-sentence plot beats (chapter-level, if not tied to a named thread)

Use exact field names. No code fences.
"""


def _character_prompt(chapter_number: int, text: str, source: str, title: str) -> str:
    return f"""# CHAPTER CHARACTER MINING — Chapter {chapter_number}

Read this chapter prose and extract **character information only** — who appears, how they change, new cast.
Do not extract plot thread lists or story bible world rules.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source}
- **Word count:** {len(text.split())}

## Chapter text

{text}

---

1. Brief note (2–3 sentences) on character focus in this chapter.
2. Emit `[CHAPTER_CHARACTER_UPDATE]` as your **final** block:

- `Characters_Present` — bulleted full names of characters in this chapter
- `New_Characters` — bulleted. Format: `Full Name | role | one-sentence description`. Roles: protagonist, antagonist, supporting, minor
- `Character_Updates` — bulleted. Format: `Full Name: field=value` (fields: location, emotional_state, desire, goal, fear, weakness, strength, secret, notes, physical_description, age, alias, aliases)
- `Emotional_Shifts` — bulleted. Format: `Full Name: new emotional state`

Use exact field names. No code fences.
"""


def _bible_prompt(chapter_number: int, text: str, source: str, title: str) -> str:
    return f"""# CHAPTER STORY BIBLE MINING — Chapter {chapter_number}

Read this chapter prose and extract **durable worldbuilding and story bible facts** established here.
Do not list plot thread arcs or full character sheets — bible / world / relationship facts only.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source}
- **Word count:** {len(text.split())}

## Chapter text

{text}

---

1. Brief note (2–3 sentences) on what world or story bible facts this chapter establishes.
2. Emit `[CHAPTER_BIBLE_UPDATE]` as your **final** block:

- `World_Facts` — bulleted setting rules, locations, technology, culture, or constraints revealed
- `Story_Bible_Notes` — bulleted durable notes for the author bible (themes, tone hints, series lore)
- `Relationships` — bulleted. Format: `Name A & Name B: relationship description`
- `Setting_Details` — bulleted place/time/atmosphere facts, or `[None]`

Use exact field names. No code fences.
"""


class ChapterMiner:
    def __init__(self, project_path: str, llm: Optional[LLMClient] = None):
        self.project_path = Path(project_path)
        self.outputs_dir = self.project_path / "outputs"
        self.feedback_dir = self.outputs_dir / "feedback"
        self.state = StoryState(str(self.project_path))
        self._reader = ChapterRegenerator(project_path, llm=llm)
        self._llm = llm

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    def read_source(self, number: int, source: str = "draft") -> str:
        source = source if source in VALID_SOURCES else "draft"
        return self._reader.read_source(number, source)

    def mine(
        self,
        number: int,
        kind: str,
        *,
        source: str = "draft",
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[str], str]:
        if kind not in MINE_KINDS:
            raise ValueError(f"Unknown mine kind {kind!r}; expected plots, characters, or bible")

        log_fn = on_progress or (lambda msg: None)
        source = source if source in VALID_SOURCES else "draft"
        text = self.read_source(number, source)

        chapter = self.state.get_chapter(number) or self.state.create_chapter(number)
        title = chapter.title or ""

        if kind == "plots":
            from plot_prompts import format_plot_threads_block  # noqa: WPS433

            threads = self.state.get_active_plot_threads() or list(self.state.plot_threads.values())
            threads_block = format_plot_threads_block(
                threads,
                heading="### Existing major plot threads (nest related plots as their subplots)",
                max_threads=16,
            )
            prompt = _plot_prompt(number, text, source, title, threads_block)
            agent = "archivist"
            tag = "CHAPTER_PLOT_UPDATE"
        elif kind == "characters":
            prompt = _character_prompt(number, text, source, title)
            agent = "archivist"
            tag = "CHAPTER_CHARACTER_UPDATE"
        else:
            prompt = _bible_prompt(number, text, source, title)
            agent = "lorekeeper"
            tag = "CHAPTER_BIBLE_UPDATE"

        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        nnn = f"{number:03d}"
        prompt_path = self.feedback_dir / f"chapter_{nnn}_mine_{kind}_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        if dry_run:
            log_fn(f"Dry-run — prompt saved to {prompt_path}")
            return [], str(prompt_path)

        log_fn(f"Mining {kind} from chapter {number} ({source})…")
        try:
            raw = self._get_llm().run_agent(agent, prompt)
        except LLMError as e:
            raise RuntimeError(f"Chapter {kind} mining failed: {e}") from e

        report_path = self.feedback_dir / f"chapter_{nnn}_mine_{kind}_report.md"
        report_path.write_text(raw, encoding="utf-8")

        if kind == "plots":
            parsed = parse_chapter_plot(raw)
            if not parsed:
                raise RuntimeError(f"Agent returned no [{tag}] block")
            apply_fn = lambda st: apply_chapter_plot_mine(st, number, parsed, source=f"mine_{kind}")
        elif kind == "characters":
            parsed = parse_chapter_character(raw)
            if not parsed:
                raise RuntimeError(f"Agent returned no [{tag}] block")
            apply_fn = lambda st: apply_chapter_character_mine(st, number, parsed, source=f"mine_{kind}")
        else:
            parsed = parse_chapter_bible(raw)
            if not parsed:
                raise RuntimeError(f"Agent returned no [{tag}] block")
            apply_fn = lambda st: apply_chapter_bible_mine(
                st, number, parsed, source=f"mine_{kind}", label=f"Ch{number}",
            )

        lock = project_state_lock(str(self.project_path))
        with lock:
            self.state._load_state()
            changes = apply_fn(self.state)

            for line in changes:
                log_fn(f"    • {line}")

            try:
                from import_pipeline import ImportPipeline  # noqa: WPS433
                ImportPipeline(str(self.project_path), llm=self._llm).write_character_profiles()
            except Exception:  # noqa: BLE001
                pass

            self.state.save_state()

        log_fn(f"=== MINE {kind.upper()} DONE: {len(changes)} updates ===")
        return changes, str(report_path)
