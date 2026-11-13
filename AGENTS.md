# Agents in Novel OS 2

Novel OS 2 replaces the old five-step JSON pipeline with a **cast**: per-book agents that share
memory, talk in the writers' room, hand work to each other and stream their replies live.
Code lives in `server/agents/` (`runtime.py`, `context.py`, `memory.py`, `suggest.py`, `extract.py`);
role prompts live in `agents/<role>/prompt.md`.

## The cast

Every book gets a default cast on first use (`runtime.ensure_cast`). Each agent is a row in the
`agent` table: a role, a name, a brief, a model route, a temperature, an autonomy setting and
whether it reads the author's Voice DNA.

| Role | Default task | Does |
|---|---|---|
| Architect | `plan` | Synopsis, beats, structure and stakes per chapter. Also proposes Codex entries (`extract.py`). |
| Scribe | `draft` | Drafts chapter prose from the beats, in the author's voice. |
| Editor | `edit` / `revise` | Line and structural edits; produces inline suggestions on the writing screen (`suggest.py`). |
| Guardian | `check` | Continuity: deterministic findings (`services/continuity.py`) plus a model pass. |
| Curator | `voice` | Keeps prose consistent with Voice DNA and the style guide. |
| Researcher | `chat` | Real-world facts, flagged uncertainty, citations; works with the research swarm. |
| Custom | any | Authors can add agents. They build on the Scribe prompt plus their brief. |

Tasks are `plan, draft, revise, edit, check, voice, chat`. A chapter can be **assigned** to a
specific Scribe (`Chapter.assigned_agent_id`); the assignments matrix in the studio edits this.
`start_pipeline` chains `plan -> draft -> edit -> check` for one chapter.

## Context: rulings are binding, memory is recalled

`context.build` assembles a token-conscious pack for each run:

- **Author rulings (binding).** Memories of kind `decision` ("this is intentional") and
  `preference` ("Iris never swears"), plus anything pinned, bypass ranking and go to every
  agent, every run (capped at 24, pinned first). Agents must not contradict them.
- **Recalled memory.** Facts (canon from drafts), research notes and the rest are *ranked*
  (`memory.recall`): lexical overlap, embeddings when available, importance, recency and
  chapter proximity. Only the top results enter the prompt. Rejected edits become taste
  hints, not rulings.
- Relevant Codex entries, beats, plot threads, the tail of the previous chapter, and the Voice
  DNA / style guide for voice-sensitive tasks.

The author can pin, edit or delete any memory in the studio.

## Handoffs

An agent hands off by writing a line `HANDOFF @Name: request` in its reply. The runtime strips
it from what the author sees, infers the task from the request, and either runs the target
(autopilot) or posts an Approve / Skip card (ask). Chains stop after `MAX_HOPS = 4`; the author
replies to continue. Follow-up runs start only after the current run's DB session closes, so
nested runs never fight over a write lock.

## Autonomy

`Agent.autonomy` is `ask` (default) or `autopilot`.

- **ask**: edits and revisions are saved as a `ChapterVersion` and proposed with Accept / Reject;
  handoffs wait for approval.
- **autopilot**: the agent applies its revision to the chapter and hands off without asking.

Every change is versioned either way, so nothing is lost.

## Runs, streaming and cancel

All work goes through `jobs.submit` and is tracked as a `Run` (status, model, token usage,
progress). Chat replies stream token by token via `llm.complete_streaming` into a draft
`Message`, published as SSE events (`message.*`, `run.updated`) that the studio's
`useProjectEvents` hook turns into React Query invalidations.

Cancel is cooperative: `jobs.cancel(run_id)` marks queued runs cancelled immediately and flags
running ones; the streaming callback checks the flag and stops, keeping the text written so far
marked as stopped. Runs interrupted by a server restart are recovered on startup
(`server/recovery.py`).

## Models, per book and per agent

Every model call goes through `server/llm.py`. The route is resolved in this order:

1. the agent's own `provider` / `model` (set per book in the agent editor),
2. the role default (`RoleDefault`, Settings > Connections),
3. the default `Connection`,
4. environment variables (`.env`, see `.env.example`).

Keys never leave the server; the browser only sees `has_key`.

## Adding a role

1. Add `agents/<dir>/prompt.md` and map it in `context.ROLE_PROMPT_DIR`.
2. Add it to `DEFAULT_CAST` (new books) and `DEFAULT_TASK` / `TASK_ROLE` as needed.
3. Test it in `tests/api/test_agents.py` with `server.llm.complete` monkeypatched.

## External agents (MCP)

`python -m novel_os mcp` (same as `python -m server.mcp_server`) lets Claude Code, Cursor or
Codex read canon, write chapters and run continuity:
`claude mcp add novel-os -- python -m novel_os mcp`.
