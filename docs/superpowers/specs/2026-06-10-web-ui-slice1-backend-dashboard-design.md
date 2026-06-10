# Novel OS Web UI — Slice 1: Backend API + Project Dashboard

**Date:** 2026-06-10
**Status:** Approved approach (FastAPI + React, full interactive workflow, decomposed into slices). This spec covers **Slice 1** only.

## Context

Novel OS is a Python multi-agent novel-writing pipeline driven today by a CLI
(`core/orchestrator.py`): `init → character → plot → plan → write → edit →
validate → approve → export`. The goal is a **local web app** (FastAPI backend,
React frontend) exposing the full workflow to non-terminal users, matching the
project's owl/comic brand.

The full UI is decomposed into four slices, each its own spec → plan → build:

1. **Slice 1 (this doc):** Backend API + project list + dashboard (read state).
2. Slice 2: Run phases with live output (job model + SSE), approve gate.
3. Slice 3: In-browser draft editing + export download.
4. Slice 4: First-run setup screen, continuity panel, brand polish.

## Slice 1 goal

Stand up the full stack end-to-end with **read + navigation only**: a writer can
open the app, see their projects, open one, and view its chapters, status, drafts,
and story state — all served by a FastAPI layer that wraps the existing
orchestrator/state without duplicating logic. No agent triggering yet (that is
Slice 2). This proves the architecture and de-risks everything downstream.

## Architecture

```
React (Vite, :5173) ──HTTP/JSON──> FastAPI (:8000) ──> StoryState / project files
                                        │
                                   reads outputs/, state/, manuscript/
```

- **Backend** lives in a new top-level `api/` package, separate from `core/` so the
  CLI is untouched. It imports `StoryState` (and read helpers) directly.
- **Projects are folders on disk.** A project is any directory containing
  `outputs/state/story_state.json`. A configurable root (env `NOVEL_OS_PROJECTS_DIR`,
  default `./projects`) holds them. Multi-project from day one.
- **Frontend** is a Vite + React + TypeScript app in `web/`, talking to the API via a
  small typed client. Styling deferred to Slice 4, but the component structure and
  brand tokens (navy `#0a0e1a`, amber `#fbbf24`) are set up now.

## Backend API (Slice 1 endpoints — all read-only)

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/health` | `{status, version}` |
| `GET` | `/api/projects` | list of `{id, title, genre, chapter_count, status}` |
| `GET` | `/api/projects/{id}` | project detail: title, genre, author, style profile, counts |
| `GET` | `/api/projects/{id}/chapters` | chapters: `{number, title, status, word_count, pov}` |
| `GET` | `/api/projects/{id}/chapters/{n}` | chapter detail + outline + draft text (if present) |
| `GET` | `/api/projects/{id}/characters` | characters from state |
| `GET` | `/api/projects/{id}/state` | raw `story_state.json` (for a state inspector panel) |

- A `ProjectService` (in `api/services.py`) is the only thing that touches disk/state;
  routes are thin. This keeps the boundary clean and testable.
- `id` is the project folder name (slugified), not a DB id.
- Errors: unknown project/chapter → `404` with `{detail}`. Malformed state → `422`.

## Frontend (Slice 1 screens)

- **Projects list** — cards per project (title, genre, chapter progress). Empty state
  explains how to create one via CLI (creation UI arrives in a later slice).
- **Project dashboard** — chapter board (a column/grid of chapter cards showing
  number, title, status pill, word count) + project meta sidebar.
- **Chapter view** — outline (beat-sheet) and draft rendered as Markdown, read-only,
  side by side; status and word count in a header.
- **App shell** — top bar with owl/wordmark, project switcher, routing
  (`/`, `/projects/:id`, `/projects/:id/chapters/:n`) via React Router.

State fetched with a typed `apiClient`; light data-fetching (React Query or simple
hooks — decided in the plan). No global store needed at this size.

## Data flow

```
load app ─GET /api/projects─> render project cards
click card ─GET /api/projects/{id} + /chapters─> dashboard chapter board
click chapter ─GET /chapters/{n}─> render outline + draft (Markdown)
```

## Error handling

- API: typed error responses; `404`/`422` as above; CORS enabled for the Vite dev origin.
- Frontend: per-route loading + error states; a failed fetch shows a retry, never a
  blank screen. Missing draft/outline renders an explicit "not generated yet" panel
  (it's expected, not an error).

## Testing

- **Backend:** pytest over `ProjectService` and routes using FastAPI `TestClient`
  against a temp projects dir seeded with a sample `story_state.json` — assert project
  listing, chapter listing, detail, and 404s. No network, no LLM.
- **Frontend:** component tests (Vitest + Testing Library) for the project list,
  chapter board, and chapter view against a mocked apiClient. One smoke test that the
  app renders and routes.

## Out of scope for Slice 1

- Triggering any agent/phase (Slice 2).
- Editing prose or exporting from the browser (Slice 3).
- Setup wizard screen, continuity panel, final visual polish (Slice 4).
- Auth, hosting, multi-user — local single-user only for now.

## Affected / new files

- `api/__init__.py`, `api/main.py` (FastAPI app + CORS), `api/routes.py`,
  `api/services.py`, `api/models.py` (Pydantic response models).
- `web/` — Vite React TS app (`src/api/client.ts`, `src/routes/*`, `src/components/*`).
- `tests/test_api.py` — backend API tests.
- `requirements.txt` — add `fastapi`, `uvicorn[standard]`.
- `README.md` — "Run the web UI" section.
