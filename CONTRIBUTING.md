# Contributing to Novel OS

Thanks for helping. Novel OS is licensed under **AGPL-3.0-or-later**, and contributions are
accepted under the same license.

## Setup

Requires Python 3.10+ and Node 20+ (CI uses 22).

```bash
python -m pip install -r requirements-dev.txt   # server + test deps
pip install -e .                                # optional: adds the `novel-os` command
python -m novel_os                              # API :8000 + studio :3000, opens the browser
```

The launcher checks prerequisites, offers `npm install` in `web/`, prefixes logs with `[api]` and
`[web]`, and stops both on Ctrl+C. Flags: `--api-port`, `--web-port`, `--no-browser`, `--reload`,
`--yes`. It works the same in PowerShell, Git Bash, macOS and Linux.

Manual start, if you prefer two terminals:

```bash
uvicorn server.main:app --port 8000 --reload
cd web && npm install && npm run dev
```

Copy `.env.example` to `.env` for keys, or add connections in the studio.

## The build contract

Read [`docs/BUILD.md`](docs/BUILD.md) first. In short: routers in `server/routers/*.py` are
auto-mounted; every model call goes through `server/llm.py`; long work goes through
`jobs.submit`; events are `<domain>.<verb>` and query keys are `["p", id, "<domain>"]`;
secrets never reach the browser. Agent behaviour is described in [`AGENTS.md`](AGENTS.md).

## Tests

```bash
python -m pytest tests -q                         # all server tests, incl. tests/api
cd web && npm run typecheck && npm run lint && npx vitest run && npx next build
```

Tests never reach a network: stub models by monkeypatching `server.llm.complete`. API tests go in
`tests/api/test_<area>.py` using the `client` and `project` fixtures. CI
(`.github/workflows/ci.yml`) runs all of the above on Python 3.10, 3.11 and 3.13, plus an
`alembic upgrade head` on a fresh SQLite database.

`fastapi` is capped below 0.120 and `mcp` below 2 in `requirements.txt` until a route-order issue and a test import are updated; see the comments there.

## Migrations

Schema changes go through Alembic; the server applies them on startup.

```bash
python -m alembic revision --autogenerate -m "describe the change"
python -m alembic upgrade head
```

Review the generated file. `tests/api/test_migrations.py` fails if a model changes without a
migration. New tables go in `server/models/<area>_extra.py`; don't change existing columns.

## Design rules

- **No monospace anywhere**, including numbers and code-like labels.
- Use the design tokens (CSS variables) rather than raw colours; the one accent (gall) is
  reserved for AI. Every screen must work in **dark mode** ("inkwell at night") and at phone width.
- Urbanist for display, Inter Tight for UI, Newsreader for book prose.
- Icons from `lucide-react` at `strokeWidth={1.75}`. Use the shared `web/components/ui` parts and
  the custom dropdown, not native `<select>`.
- Prefer text on surfaces to boxing everything in cards.

## Adding a model provider

1. OpenAI-compatible: add an entry to the provider table in `core/llm_client.py`
   (base URL, default model, env key) and its env var to `server/llm.py`'s key map.
   Anything else: add a client branch in `core/llm_client.py`.
2. Make it selectable in Connections (provider list and icon in the web settings).
3. Document the env var in `.env.example`, and add a test with a fake transport.

## Adding an image service

1. Add an `ImageProvider` to `PROVIDERS` in `server/imagegen.py` (id = `Connection.provider`).
2. Write an adapter `_yourservice(client, prompt, aspect, model, key, ...) -> bytes` and route to it
   in `generate`. Map aspect ratios; turn HTTP errors into readable `ImageGenError`s.
3. Test it in `tests/api/test_images.py` with an `httpx.MockTransport`; document the key format
   in `.env.example`.

## Pull requests

Keep changes in your area, write a clear message, add a `CHANGELOG.md` line under "Unreleased",
and make sure CI is green. Don't commit `web/package-lock.json` unless you changed dependencies.
