# Novel OS — System Architecture

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│  web/  — React + Vite + Tailwind v4 (the studio UI)          │
│         Library · Dashboard · Chapter (binder/flow/editor)    │
└───────────────▲──────────────────────────────────────────────┘
                │  HTTP / JSON  (polls jobs)
┌───────────────┴──────────────────────────────────────────────┐
│  api/  — FastAPI (system-of-record for the UI)               │
│   routes  →  services (ProjectService)  →  db (SQLite)        │
│                         │                                     │
│                    JobRunner (threads) → core/ orchestrator   │
└───────────────┬──────────────────────────────────────────────┘
                │  reads/writes files                          
┌───────────────┴──────────────────────────────────────────────┐
│  core/  — multi-agent engine (file-based)                    │
│   orchestrator · agents · StoryState · continuity_engine      │
│   LLMClient (claude_cli / anthropic / openai / …)             │
└──────────────────────────────────────────────────────────────┘
```

## Two stores, one bridge

Novel OS deliberately keeps **two** stores and an ingest bridge between them:

1. **Filesystem — the agent engine's working store.**
   `core/` is file-based and unchanged: each project is a folder under
   `NOVEL_OS_PROJECTS_DIR` with `outputs/state/story_state.json` and per-chapter
   stage files (`outline`, `draft`, `revised`, `final`). Agents read/write these.

2. **SQLite database — the API's system-of-record.** (`api/db.py`, via SQLModel)
   Stores everything the UI owns and queries:
   - `Project`, `Chapter` — registry/metadata
   - `Artifact` — the **text** of each stage (`outline/draft/revised/final`) — "files in the DB"
   - `Snapshot` — version history (label, text, word count, timestamp)
   - `Comment` — annotations (body, optional quote, resolved)

   DB location: `NOVEL_OS_DB` (default `sqlite:///./novel_os.db`).

3. **Ingest bridge** (`db.ingest_project`). After agents produce files, reading a
   chapter's stages mirrors those files into `Artifact` rows. The **Final** is
   DB-first: human edits write to the DB (and to the file, so the engine/export
   keep working); ingest never overwrites a saved Final from an older file.

### Why two stores?
The agents are a mature file-based pipeline; rewriting them to be DB-native is
risk with no near-term payoff. The DB gives the UI fast queries, version history,
comments, and a real schema **without touching the engine**. The bridge keeps them
in sync. Over time, more reads move DB-first (the ingest path already populates it).

## Request lifecycle examples

- **View a chapter:** `GET /chapters/{n}/stages` → `ProjectService` reads stage files,
  best-effort `ingest_project` mirrors them into the DB → returns stages.
- **Edit Final:** `PUT /chapters/{n}/final` → atomic file write **and**
  `db.upsert_artifact(final)` (DB is system-of-record for human content).
- **Run an agent:** `POST /run` → `JobRunner` runs the orchestrator on a daemon
  thread; the UI polls `GET /jobs/{id}`; on completion the UI refetches (which
  re-ingests).
- **Snapshot / restore:** snapshots live in the DB; restore writes the snapshot
  text back to Final (file + DB) after auto-snapshotting the current Final.

## Persistence schema (SQLite)

| Table | Key fields |
|---|---|
| `project` | id (slug), title, genre, author, status |
| `chapter` | project_id, number, title, status, pov, word_count |
| `artifact` | project_id, chapter, stage, text, word_count |
| `snapshot` | project_id, chapter, label, source, text, word_count, created_at |
| `comment` | project_id, chapter, body, quote, resolved, created_at |

## Conventions
- Agent phases never run inline in a request — always via `JobRunner` (threads),
  polled by the UI.
- Human-owned content (Final, snapshots, comments) is DB-first; engine artifacts
  (outline/draft/revised) are file-first, ingested into the DB.
- Writes to Final are atomic (temp + `os.replace`); drafts/revisions are immutable
  provenance.

## Roadmap (DB-forward)
- Move list/detail reads fully DB-first (ingest already populates the rows).
- Persist job history in the DB.
- Codex (characters/locations/world) and outliner metadata as first-class tables.
- See `docs/superpowers/plans/2026-06-10-novel-os-frontend-product-roadmap.md`.
