# 🎭 Novel OS: Multi-Agent Fiction Writing Framework

A production-grade, multi-agent architecture for writing professional novels with long-term memory, continuity management, and collaborative agent workflows.

## 🏛️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NOVEL OS ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│   │  ARCHITECT  │◄──►│   SCRIBE    │◄──►│   EDITOR    │◄──►│  CONTINUITY │  │
│   │  (Planner)  │    │  (Drafter)  │    │  (Refiner)  │    │  (Guardian) │  │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│          │                  │                  │                  │         │
│          └──────────────────┴──────────────────┴──────────────────┘         │
│                                     │                                        │
│                                     ▼                                        │
│                          ┌─────────────────────┐                             │
│                          │   STATE MANAGER     │                             │
│                          │  (Central Memory)   │                             │
│                          └─────────────────────┘                             │
│                                     │                                        │
│                                     ▼                                        │
│                    ┌───────────────────────────────┐                         │
│                    │     STYLE CURATOR (Opt)       │                         │
│                    └───────────────────────────────┘                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🧠 Core Philosophy

| Traditional AI Writing | Novel OS |
|------------------------|----------|
| Single prompt, single output | Multi-agent collaboration |
| No memory between sessions | Persistent state management |
| Inconsistent characters | Character database tracking |
| Forgotten plot threads | Active plot thread monitoring |
| Style drift | Style lock with curator |
| Manual continuity checking | Automated continuity validation |

## 📁 Directory Structure

```
novel-os/
├── README.md                 # This file
├── AGENTS.md                 # Agent definitions and protocols
├── core/
│   ├── state_manager.py      # Central state management
│   ├── orchestrator.py       # Workflow orchestration
│   ├── continuity_engine.py  # Continuity validation
│   └── style_engine.py       # Style enforcement
├── agents/
│   ├── architect/            # Planning agent
│   ├── scribe/               # Drafting agent
│   ├── editor/               # Refinement agent
│   ├── continuity_guardian/  # Fact-checking agent
│   └── style_curator/        # Style consistency agent
├── templates/
│   ├── story_bible/          # World-building templates
│   ├── character/            # Character profile templates
│   ├── outline/              # Story structure templates
│   └── chapter/              # Chapter templates
├── examples/
│   ├── demo_project/         # Example novel project
│   └── workflows/            # Example workflows
└── outputs/
    ├── manuscript/           # Generated chapters
    ├── state/                # Persistent state files
    └── feedback/             # Agent feedback logs
```

## 🚀 Quick Start

### 1. Setup NVIDIA NIM API

Create a `.env` file in the root directory and add your NIM API key:
```env
NVIDIA_NIM_API_KEY="nvapi-your-key-here"
```
Install the necessary requirements:
```bash
pip install requests python-dotenv
```

### 2. Initialize a New Novel Project

```bash
python core/orchestrator.py init --title "My Novel" --genre "Sci-Fi" --author "Your Name"
```

### 3. Build Your Story State

Add characters and plot threads to the central state:
```bash
python core/orchestrator.py character add --name "Elara Vance" --role "protagonist"
python core/orchestrator.py plot add --name "The Obsidian Threat" --description "Dark energy anomaly." --type "main"
```

### 4. Plan the Outline & Chapters

Generate an AI-powered story outline:
```bash
python core/orchestrator.py plan outline --chapters 10 --words 20000
```
Plan individual chapters:
```bash
python core/orchestrator.py plan chapter --number 1 --pov "Elara Vance" --summary "Elara explores a derelict ship."
```

### 5. Write Chapters with Token Management

Leverage the **Smart Chunked Generation** pipeline to write massive chapters safely without hitting LLM output limits:
```bash
# Writes Chapter 1 sequentially in 1200-word chunks 
python core/orchestrator.py --chunk-limit 1200 write --chapter 1
```

### 6. Review and Refine

Pass the text to the AI Editor:
```bash
python core/orchestrator.py edit --chapter 1 --mode line
```

## 🎭 The Agents

### 1. **The Architect** (Planner)
- Creates story structure
- Designs character arcs
- Plans narrative beats
- Validates plot logic

### 2. **The Scribe** (Drafter)
- Writes prose
- Deep POV immersion
- Scene-by-scene execution
- Dialogue crafting

### 3. **The Editor** (Refiner)
- Line editing
- Structural fixes
- Pacing optimization
- Tension enhancement

### 4. **The Continuity Guardian**
- Fact verification
- Timeline checking
- Character consistency
- World-rule validation

### 5. **The Style Curator** (Optional)
- Voice consistency
- Prose styling
- Genre convention enforcement
- Rhythm management

## 🔄 The Workflow Loop

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  PLAN    │────►│  DRAFT   │────►│  EDIT    │────►│ VALIDATE │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │                │                │                │
     ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                      STATE UPDATE                            │
│         (Update character positions, plot threads,           │
│          timeline, emotional states, etc.)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  NEXT CHAPTER?  │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
               ┌─────────┐       ┌─────────┐
               │   YES   │       │   NO    │
               │ (Loop)  │       │ (Export)│
               └─────────┘       └─────────┘
```

## 📊 State Management

Every operation updates the **Story State** - a central JSON file tracking:

- **Story Bible**: World rules, magic systems, setting details
- **Character Database**: Arcs, motivations, relationships, positions
- **Plot Tracker**: Active threads, foreshadowing, unresolved conflicts
- **Timeline**: Chronological events, chapter mapping
- **Style Profile**: Tone, voice, stylistic constraints

## 🎯 Use Cases

| Use Case | Recommended Mode |
|----------|------------------|
| Commercial Fiction | Standard 5-Agent Loop |
| Epic Fantasy | + World-Builder Agent |
| Mystery/Thriller | + Clue-Tracker Agent |
| Romance | + Emotional Arc Agent |
| Literary Fiction | + Theme Weaver Agent |
| Series Writing | + Canon Manager Agent |

## 📖 Documentation

- [Agent Definitions](AGENTS.md) - Detailed agent prompts and protocols
- [State Protocol](docs/STATE_PROTOCOL.md) - State management specification
- [Workflow Guide](docs/WORKFLOWS.md) - Step-by-step usage instructions
- [API Reference](docs/API.md) - Programmatic interface

## 🔧 Configuration

Edit `config/novel-os.yaml` to customize:
- Agent personalities
- Style constraints
- Genre templates
- Output formats

---

**Novel OS** - Write novels like a professional author, with an entire editorial team at your command.
