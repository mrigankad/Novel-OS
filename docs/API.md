# Novel OS — Programmatic API

Everything Novel OS does is available as importable Python — the CLI is just a thin layer.

---

## Module map

```
core/
├── orchestrator.py          NovelOrchestrator — workflow + CLI
├── state_manager.py         StoryState, Character, PlotThread, ChapterState, ...
├── llm_client.py            LLMClient (13+ providers), LLMError
├── state_parser.py          ingest_agent_output, parse_*, apply_to_state
└── continuity_engine.py     run_all, Finding, individual check_* fns
```

---

## StoryState

```python
import sys; sys.path.insert(0, "core")
from state_manager import StoryState, Character, PlotThread

state = StoryState("/path/to/project")

# Characters
state.add_character(Character(
    id="char_001", full_name="Lena Vasquez", role="protagonist",
    internal_desire="uncover the truth", external_goal="find her brother",
    fear="being silenced", weakness="trusts too easily",
))
lena = state.get_character_by_name("Lena Vasquez")
state.update_character_location(lena.id, "Observatory rooftop", chapter=1)

# Plot threads
state.add_plot_thread(PlotThread(
    id="plot_001", name="The Theta-7 Signal",
    description="An impossible transmission predates the colony",
    thread_type="main", priority=5, start_chapter=1,
    target_resolution_chapter=28,
))

# Chapters
ch = state.create_chapter(1, title="First Contact")
state.update_chapter(1, {"status": "drafted", "word_count": 2451})

# Persist (atomic, .bak rollback)
state.save_state()
```

---

## LLMClient — any provider

```python
from llm_client import LLMClient

# Auto-detect from env keys
client = LLMClient()
print(client.provider, client.model)

# Or explicit
client = LLMClient(provider="nvidia", model="meta/llama-3.3-70b-instruct")
client = LLMClient(provider="openai_compatible",
                   base_url="https://my-endpoint/v1",
                   api_key="...", model="my-model")

# Single-turn completion
text = client.complete(system="You are terse.", user="Reply: pong")

# Run an agent (loads agents/<name>/prompt.md as system message)
draft = client.run_agent("scribe", user_prompt="Write chapter 1 about...")
```

Supported providers: `anthropic`, `openai`, `azure`, `gemini`, `nvidia`, `kimi`, `groq`, `together`, `openrouter`, `deepseek`, `mistral`, `fireworks`, `ollama`, `lmstudio`, `openai_compatible`.

---

## State parser — agent output → state mutations

```python
from state_parser import ingest_agent_output

changes = ingest_agent_output(
    state=state,
    chapter_number=1,
    agent_name="scribe",          # or "editor" / "continuity_guardian" / "style_curator"
    agent_output=raw_llm_response,
)
for entry in changes:
    print(entry)
state.save_state()
```

The parser recognizes `[SCRIBE_STATE_UPDATE]`, `[EDITOR_ANALYSIS]`, `[EDITOR_STATE_UPDATE]`, `[CONTINUITY_REPORT]`, `[CONTINUITY_STATE_UPDATE]`, `[STYLE_ANALYSIS]`, `[STYLE_STATE_UPDATE]` blocks. Both `[TAG]…[/TAG]` and unclosed `[TAG]…` (stops at next known tag) are supported.

Individual parsers and the applier are exposed if you need them:

```python
from state_parser import (
    extract_block, parse_fields,
    parse_scribe, parse_editor, parse_continuity, parse_style,
    apply_to_state,
)
```

---

## Continuity engine — deterministic checks

```python
from continuity_engine import run_all, Finding
from pathlib import Path

findings = run_all(state, Path("/path/to/project"), as_of_chapter=12)
for f in findings:
    print(f.format())   # human-readable
    d = f.to_dict()     # serializable
```

`Finding` fields: `severity` (`critical` | `warning` | `info`), `category`, `message`, `suggestion`, `chapter`, `entity_id`.

Individual checks are exposed too:

```python
from continuity_engine import (
    check_dormant_threads, check_overdue_threads,
    check_unresolved_foreshadowing, check_absent_characters,
    check_dead_characters_reappearing, check_chapter_file_consistency,
    check_required_character_fields,
)
```

---

## NovelOrchestrator — high-level workflow

```python
from orchestrator import NovelOrchestrator

orch = NovelOrchestrator("/path/to/project")

orch.init_project("My Novel", "Sci-Fi Thriller", author="Mriganka")
orch.add_character("Lena Vasquez", "protagonist")
orch.plan_outline(num_chapters=32, target_words=80000)

orch.plan_chapter(1, pov="Lena Vasquez")             # Architect (real LLM)
orch.plan_chapter(1, pov="Lena Vasquez", dry_run=True)  # save prompt only

orch.write_chapter(1)                                # Scribe
orch.edit_chapter(1, mode="line")                    # Editor
critical = orch.run_checks(chapter_number=1)         # deterministic
orch.validate_chapter(1)                             # Guardian (LLM)
orch.approve_chapter(1)                              # gates on FAIL
orch.export(format="markdown")
```

Constructor injection for tests:

```python
orch = NovelOrchestrator("/tmp/test_project")
orch._llm = my_fake_llm_client       # bypass real LLM calls
```

---

## Environment configuration

| Variable | Purpose |
|---|---|
| `NOVEL_OS_LLM_PROVIDER` | Override provider auto-detection |
| `NOVEL_OS_MODEL` | Override the default model for the active provider |
| `NOVEL_OS_MAX_TOKENS` | Per-call cap (default 8192) |
| `NOVEL_OS_API_KEY` | Generic key for `openai_compatible` / aliases |
| `NOVEL_OS_BASE_URL` | Endpoint URL for `openai_compatible` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / etc. | Provider-native keys |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION` | Azure-specific |
| `KIMI_BASE_URL`, `<PROVIDER>_BASE_URL` | Override an alias's endpoint |

`.env` files in the project root are auto-loaded (with or without `python-dotenv`).

---

*API v1.1*
