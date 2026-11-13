# Novel OS 2: build contract

Read this before changing anything. It's the agreement every part of the app builds against.

## Run it

```bash
pip install -r requirements.txt
uvicorn server.main:app --port 8000 --reload     # API + agents (FastAPI)
cd web && npm install && npm run dev             # Studio on http://localhost:3000
```

Next proxies `/api/*` to port 8000 (see `web/next.config.ts`), so the browser only ever talks to :3000.

## Layout

| Path | What lives there |
|---|---|
| `server/main.py` | App factory. **Auto-mounts every `server/routers/*.py` that defines `router`** under `/api`. Don't edit it to add routes. |
| `server/models/` | SQLModel tables. `book.py` (Project, Chapter, ChapterVersion, CodexEntry, CodexLink, PlotThread, ContinuityExemption, Media), `agents.py` (Agent, Memory, Thread, Message, Run), `studio.py` (research, voice, publishing, Connection). |
| `server/db.py` | Engine (SQLite WAL in `./data`, or `NOVEL_OS_DATABASE_URL`), `get_session` dependency, `session_scope()` for jobs. |
| `server/llm.py` | **The only way to call a model.** `complete(session, system, user, agent=...)` resolves agent override, then default Connection, then env. |
| `server/jobs.py` | `jobs.submit(project_id, task, fn, agent_id=, chapter=, input=)` runs `fn(run_id) -> dict` on a thread pool, tracked as a `Run`, with progress events. |
| `server/events.py` | `events.publish(project_id, "<domain>.<verb>", data)`. The web app's SSE hook invalidates `["p", id, "<domain>"]` queries. |
| `core/` | Engine reused from Novel OS 1: `llm_client`, `continuity_engine`, `compile_*`, `style_stats`, `prose_sanitize`, `model_catalog`, `codex_extract`, `context_pack`. Port logic out of `core/state_manager.py` (JSON StoryState); **the database is now the source of truth**. |
| `agents/*/prompt.md` | Role prompts (architect, scribe, editor, continuity_guardian, style_curator). |
| `web/app/` | Next.js App Router pages. `/` Library, `/p/[id]/...` project screens, `/settings/...`. |
| `web/lib/api.ts` | `api.get/post/patch/put/del` (same-origin `/api`), `projectsApi`, query keys `qk`. Put feature calls and types in `web/lib/api/<feature>.ts`. |
| `web/lib/events.ts` | `useProjectEvents(id)`, already active in `app/p/[id]/layout.tsx`. |
| `web/components/ui/` | `Button` (primary / secondary / ghost / ai / danger), `Input`, `Textarea`, `Field`, `Page`, `PageHeader`, `SectionLabel`, `EmptyState`, `Badge`, `Skeleton`, `useToast`. Use these. |

## Rules

1. **Stay in your lane.** Edit only the files listed for your area. If you need something from another area, add a small function in your own module rather than editing theirs.
2. **New tables** go in `server/models/<area>_extra.py` and get registered with one appended import line in `server/models/__init__.py`. Don't change existing columns.
3. **Query keys** are `["p", projectId, "<domain>", ...]`, where domain matches the event prefix (chapter, codex, run, message, memory, research, voice, publish).
4. **Never call an LLM directly.** Use `server.llm.complete`. Long work goes through `jobs.submit`, never inside a request.
5. **Tests**: put API tests in `tests/api/test_<area>.py` using the `client` and `project` fixtures. Stub models by monkeypatching `server.llm.complete`. Run them with `python -m pytest tests/api -q`. Web: `cd web && npm run typecheck && npm run lint && npx next build`.
6. **Design**: white paper, ink `#14131a`, one accent `gall #3b2be0` reserved for AI. Urbanist 700 for display, Inter Tight for UI, Newsreader for book prose. **No monospace anywhere.** Icons come from `lucide-react` at `strokeWidth={1.75}`. Prefer text on surfaces over boxing everything in cards. Use Swiss-style scale contrast.
7. **Speed**: server components where nothing is interactive, React Query caching, lazy-load heavy editors (`next/dynamic`), SQL aggregates instead of Python loops, and indexes on every foreign key (already in place).
8. **Secrets**: API keys live only in the `connection` table / `.env`. Never return them to the browser (expose `has_key`).

## Database migrations

Schema changes go through Alembic. The server applies migrations on startup (`server/db.py:init_db`).

```bash
# after changing a model in server/models/
python -m alembic revision --autogenerate -m "add cover rating"
python -m alembic upgrade head        # or just restart the server
```

`tests/api/test_migrations.py` fails if a model changes without a migration.
