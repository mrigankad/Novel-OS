# Contributing

Thanks for considering it. This file exists so you don't have to guess what I'll
ask for in review.

## Running it

```bash
# Engine + API
pip install -r requirements-dev.txt
uvicorn api.main:app --reload --port 8000

# Studio, in a second terminal
cd web && npm install && npm run dev
```

Windows PowerShell uses `$env:NAME = "value"` instead of `export`.

## The four checks

CI runs these on every pull request, and they're the same four commands I run
locally. Nothing merges red.

```bash
pytest -q                 # engine + API
cd web
npx tsc -b                # types
npm run lint              # eslint, zero errors
npm test                  # vitest
npm run build             # production build
```

## What I'll ask about in review

These aren't style preferences; each one is a rule the architecture depends on.

**Files are the story, SQL is an index.** Each project's
`outputs/state/story_state.json` and its per-chapter markdown are the truth. If
the database were deleted, the CLI and the tests must still produce the novel
from disk. A change that makes SQL the only home for a chapter is the wrong
change.

**Only Final is editable.** `outline`, `draft` and `revised` are immutable
provenance — a record of what each agent produced. Final is the manuscript.

**AI proposes, the human disposes.** Every AI output needs a review surface with
accept and reject. Nothing an agent produces may overwrite a writer's words
silently. This is enforced in storage rather than in the UI: the markdown
projection of a document is the *reject-all* view, so a pending suggestion is
never handed to an agent or an export as though it had been accepted.

**Agents never run inside an HTTP request.** They go through the job registry in
`api/jobs.py`. A handler that blocks on a model is a timeout waiting to happen.

**Agent prompts are not rewritten to suit the UI.** If the interface needs
different context, that's a `core/context_pack.py` change, not an
`agents/*/prompt.md` change.

**Deterministic beats inferred.** If a check can be computed from state, compute
it — it's free, instant and always right. AI inference is labelled `predicted`
and never presented as fact.

**No chart libraries.** Analytics visuals are in-house SVG.

**Backends are added, not swapped.** `llm_client.py` is provider-agnostic on
purpose. New providers are welcome; removing an existing path is not — the
`claude_cli` backend in particular is the reason the project can run with no API
key and no per-token cost.

## Pull requests

**Small and focused beats comprehensive.** One idea per PR. A 500-line PR gets
reviewed in days; a 15,000-line one across 90 files can't honestly be reviewed at
all, however good the code is.

Tests come with behaviour changes. If you're fixing a bug, the ideal shape is a
test that fails before your fix and passes after — I'd rather see the bug pinned
than described.

Commit messages: say *why*, not just what. The diff already says what.

## Where things live

| Path | What it is |
|---|---|
| `core/` | The engine. File-based, no web dependencies, runs headless |
| `api/` | FastAPI. `routes` → `services` → engine. `ProjectService` is the only thing that touches both stores |
| `web/` | React 19 · Vite · Tailwind v4 · TipTap |
| `agents/` | One `prompt.md` per agent, each with an OUTPUT CONTRACT |
| `tests/` | pytest. `web/src/test/` for vitest |

Longer reasoning lives in [`PLAN.md`](PLAN.md) (what's shipped and what's next),
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (the layers and the two stores),
and the design notes linked from the README.

## Reporting a bug

Tell me what you expected, what happened, and your OS plus Python and Node
versions. If it's in the studio, the browser console usually holds the real
error — a blank page with data missing is almost always CORS
(`NOVEL_OS_CORS_ORIGINS`).

Please don't run scripts posted in issue comments. Everything this project needs
is in `requirements.txt` and `web/package.json`.
