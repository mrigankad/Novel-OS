# Novel OS — Workflows

Step-by-step recipes for using Novel OS day to day.

---

## 🚀 First-time setup

```bash
git clone https://github.com/mrigankad/Novel-OS.git
cd Novel-OS
pip install -r requirements.txt
cp .env.example .env
# edit .env and set ONE provider key (Anthropic / OpenAI / Gemini / Kimi / NVIDIA / etc.)
```

The first key found is auto-detected. Override with `NOVEL_OS_LLM_PROVIDER` if you have several keys set.

---

## 📚 Standard chapter loop

```mermaid
flowchart LR
    P[plan chapter] --> W[write]
    W --> E[edit]
    E --> Ck[check]
    Ck --> V[validate]
    V --> A[approve]
    A -.next.-> P
```

```bash
# 1. Plan — Architect expands the chapter outline
python core/orchestrator.py plan chapter --number 1 --pov "Lena Vasquez"

# 2. Write — Scribe drafts the prose
python core/orchestrator.py write --chapter 1

# 3. Edit — Editor refines (pick a mode)
python core/orchestrator.py edit --chapter 1 --mode line
# Modes: line | developmental | pacing | dialogue | tension

# 4. Check — free deterministic continuity scan
python core/orchestrator.py check --chapter 1

# 5. Validate — LLM Guardian validates (pre-check findings are included automatically)
python core/orchestrator.py validate --chapter 1

# 6. Approve — gated on Status: FAIL
python core/orchestrator.py approve --chapter 1
```

---

## 🧪 Dry-run mode (no API calls)

Every LLM-backed command supports `--dry-run`. It writes the prompt to disk so you can run it yourself in a chat UI, then submit the output via the `--draft-file` / `--edited-file` flags.

```bash
python core/orchestrator.py write --chapter 1 --dry-run
# -> outputs/chapter_001_scribe_prompt.md

# Run that prompt in ChatGPT/Claude/etc, save the response, then:
python core/orchestrator.py write --chapter 1 --draft-file my_response.md
```

Submitted files still get parsed — `[SCRIBE_STATE_UPDATE]` / `[EDITOR_STATE_UPDATE]` blocks update state regardless of how the chapter was produced.

---

## 🔬 Auditing an existing project

```bash
python core/orchestrator.py status            # dashboard
python core/orchestrator.py check             # whole-project continuity scan
python core/orchestrator.py check --chapter 12   # as-of a specific chapter
python core/orchestrator.py character list    # full cast with arc state
python core/orchestrator.py plot list         # threads by priority
```

The continuity engine exits non-zero on critical findings — wire it into CI if you care.

---

## ✍️ Hand-edited prose

Want to edit a chapter manually instead of running the Editor agent?

```bash
# Skip 'edit' entirely, then:
python core/orchestrator.py write --chapter N --draft-file my_revised.md
# Or replace the file directly:
# outputs/manuscript/chapter_NNN_revised.md
python core/orchestrator.py validate --chapter N   # Guardian still runs
python core/orchestrator.py approve  --chapter N
```

---

## 🔄 Re-running a phase

Phases are idempotent — re-running overwrites the corresponding artifact and re-parses.

```bash
python core/orchestrator.py edit --chapter 3 --mode tension   # re-edit
python core/orchestrator.py validate --chapter 3              # re-validate
```

---

## 📦 Exporting

```bash
python core/orchestrator.py export --format markdown
# -> outputs/Your_Title.md
```

Only chapters with status `complete` are included. Approve everything before exporting.

---

## 🎯 Progress checkpoints

| Milestone | Typical % | What should be true |
|---|---|---|
| Story bible done | 5% | Setting, themes, world rules filled in |
| All characters defined | 10% | Each has desire, goal, fear, arc start |
| Outline approved | 15% | `outline.json` reviewed, acts sized |
| Act 1 complete | 25% | Catalyst landed, debate resolved |
| Midpoint | 50% | Stakes irreversibly raised |
| All-is-lost | 75% | Protagonist at lowest point |
| First draft complete | 100% | All chapters `approve`d, `export` runs |

---

*Workflows v1.1*
