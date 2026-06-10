# Novel OS — Claude Code Backend + Setup Wizard

**Date:** 2026-06-10
**Status:** Approved design, ready for implementation plan

## Goal

Make Novel OS adapt to whatever an individual user already has, with as close to
zero configuration as possible. Different users arrive with different things:

- **Subscription user** — has Claude Pro/Max and the `claude` Claude Code CLI; wants
  to run Novel OS **without paying per-token API fees**. Not possible today.
- **API-key user** — has some provider key in their environment; works today, but
  setup is hand-edited env vars and errors are cryptic.
- **Local / free user** — Ollama or LM Studio; works, but must know the incantation.
- **Power user** — wants control; out of scope for this pass beyond clean config.

The connecting thread: Novel OS should meet the user where they are. This spec
delivers two pieces toward that — a key-free Claude Code backend and an onboarding
wizard — without changing the orchestrator or agent contracts.

## Scope

**In scope**
1. A `claude_cli` LLM backend that shells out to the installed `claude` CLI.
2. A `novel-os init` setup wizard that detects, presents, tests, and persists config.

**Out of scope (YAGNI for this pass)**
- Per-agent / mixed-model routing.
- Streaming output, automatic provider fallback, retries, cost/token tracking.

The wizard writes plain `.env` config (`NOVEL_OS_LLM_PROVIDER`, `NOVEL_OS_MODEL`,
optional key), so a future router/robustness layer can extend it without rework.

## Component 1 — `claude_cli` backend

Lives in `core/llm_client.py`, alongside the existing backends. The `complete(system, user)`
public signature is unchanged, so `core/orchestrator.py` needs **no changes**.

- **Detection:** `shutil.which("claude")`. If present and no paid provider key is set,
  `claude_cli` becomes the auto-resolved provider (zero-config, zero-cost).
- **Invocation:** call the CLI in non-interactive print mode:
  `claude -p <user> --append-system-prompt <system> --output-format json`
  plus `--model <model>` when a model is configured. Read the assistant text from the
  parsed JSON result. Pass prompts via argv/stdin (not a shell string) to avoid quoting
  and injection issues.
- **Integration points:** new branch in `_resolve_provider`, `_build_backend`, and a new
  `_complete_claude_cli(system, user)` method dispatched from `complete()`.
- **Config:** optional `NOVEL_OS_MODEL` maps to `--model`; if unset, omit the flag and let
  the CLI use its default. No API key required.
- **Failure handling:** if the CLI is missing, not logged in, or returns nonzero/invalid
  JSON, raise `LLMError` with an actionable message (e.g. "run `claude login`").

### Provider precedence

When both a paid key and the `claude` CLI are available:
1. An explicit `NOVEL_OS_LLM_PROVIDER` always wins.
2. Otherwise, if a paid provider key is configured, it is preferred (do not silently
   override a power user's configured API key with the CLI).
3. The `claude_cli` auto-pick only triggers when no paid key resolves.

The wizard (Component 2) is where an interactive user chooses between options when more
than one is available.

## Component 2 — `novel-os init` setup wizard

New module `core/setup_wizard.py`, runnable as `python -m core.setup_wizard`.

- **Scan:** detect known API keys in the environment, the `claude` CLI (`shutil.which`),
  and reachable local servers (Ollama `:11434`, LM Studio `:1234` via a short HTTP probe
  with a tight timeout).
- **Present:** a ranked menu of what was found, e.g.
  - `✓ Claude Code CLI (free, uses your subscription) — recommended`
  - `✓ OPENAI_API_KEY detected`
  - `○ Ollama running locally`
  - `+ Enter an API key / custom endpoint manually`
- **Test:** before writing anything, run a tiny live `complete()` against the chosen
  provider and report success or a clear failure.
- **Persist:** write `NOVEL_OS_LLM_PROVIDER` / `NOVEL_OS_MODEL` (and a key if entered) to
  `.env`. Never overwrite an existing `.env` without explicit confirmation; merge keys
  rather than clobbering the file.
- **Auto-offer:** the orchestrator offers to run the wizard when no provider resolves
  (i.e. `LLMClient()` would raise), via a `--setup` flag and a first-run prompt.

## Data flow

```
user runs `novel-os init`
        |
   scan environment ──> {claude_cli?, paid keys, local servers}
        |
   present ranked menu ──> user selects (or enters key/endpoint)
        |
   build LLMClient(provider=...) ──> live complete() smoke test
        |                                   |
     success                             failure ──> show error, re-prompt
        |
   write/merge .env  ──>  done; orchestrator now resolves a provider
```

## Error handling

- Missing/!logged-in `claude` CLI → `LLMError` with "run `claude login`".
- Local server probe failure → that option is shown as unavailable, not an exception.
- Wizard smoke-test failure → surface the provider's error, return to the menu; do not
  write `.env`.
- Existing `.env` → confirm before overwrite; merge new keys, preserve unrelated lines.

## Testing

- **Detection:** unit tests over a faked environment (monkeypatched `os.environ`,
  `shutil.which`, and local-server probe) asserting the resolved provider and menu order.
- **`claude_cli` backend:** mock the subprocess call; assert correct argv construction,
  JSON parsing, and `LLMError` on nonzero exit / bad JSON. No network, no real
  subscription needed in CI.
- **Precedence:** tests for the env-wins / paid-key-wins / cli-fallback rules.
- **Wizard persistence:** test `.env` write + merge + no-clobber-without-confirm using a
  temp directory.

## Affected files

- `core/llm_client.py` — add `claude_cli` detection, build, and completion.
- `core/setup_wizard.py` — new module + `__main__`.
- `core/orchestrator.py` — `--setup` flag and first-run offer (minimal).
- `tests/` — new tests for detection, backend, precedence, wizard.
- `README.md` — document `novel-os init` and the key-free Claude Code path.
