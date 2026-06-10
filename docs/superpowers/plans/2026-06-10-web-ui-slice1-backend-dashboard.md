# Novel OS Web UI — Slice 1 (Backend API + Dashboard) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a FastAPI backend that exposes Novel OS project state read-only, plus a React dashboard that lists projects and renders a project's chapters, outlines, and drafts.

**Architecture:** A new `api/` package wraps the existing `StoryState` (no changes to `core/`). A thin `ProjectService` is the only code that touches disk; FastAPI routes call it and return Pydantic models. A Vite + React + TypeScript app in `web/` consumes the API through a typed client. Projects are folders under a configurable root containing `outputs/state/story_state.json`.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, pytest + FastAPI `TestClient`; React 18, TypeScript, Vite, React Router, Vitest + Testing Library, `react-markdown`.

---

## Reference facts (from the codebase — do not re-derive)

- `core/state_manager.py` → `StoryState(project_path: str)` loads `<project_path>/outputs/state/story_state.json` in `__init__`. It is the read API.
- Useful fields/methods on a `StoryState` instance `s`:
  - `s.metadata` → dict with keys `title`, `genre`, `author` (strings; may be missing).
  - `s.chapters` → `Dict[int, ChapterState]`. `ChapterState` has `.number`, `.title`, `.status`, `.word_count`, `.target_word_count`, `.pov_character`.
  - `s.get_all_characters()` → `List[Character]`; `Character` has `.id`, `.full_name`, `.role`.
  - `s.style_profile` → `StyleProfile` with `.tone`, `.point_of_view`, `.prose_style`.
- Per-chapter files (number is zero-padded to 3 digits, e.g. `001`):
  - Outline: `<project>/outputs/chapter_{NNN}_outline.md`
  - Draft: `<project>/outputs/manuscript/chapter_{NNN}_draft.md`
- `core/` modules import each other by top-level name, so anything importing them must put `core/` on `sys.path`. The API package does this once in `api/services.py`.

---

## File structure

- `api/__init__.py` — marks the package; exposes `create_app`.
- `api/services.py` — `ProjectService`: project discovery + state reads. The ONLY disk/state access.
- `api/models.py` — Pydantic response models.
- `api/routes.py` — FastAPI `APIRouter` with the read endpoints; calls `ProjectService`.
- `api/main.py` — `create_app()` builds the FastAPI app, mounts the router, configures CORS; `app` module-level instance for uvicorn.
- `tests/test_api.py` — backend tests via `TestClient` against a seeded temp projects dir.
- `web/` — Vite React TS app:
  - `web/src/api/client.ts` — typed fetch client + response types.
  - `web/src/components/ChapterBoard.tsx`, `web/src/components/ProjectCard.tsx`
  - `web/src/routes/ProjectsList.tsx`, `web/src/routes/ProjectDashboard.tsx`, `web/src/routes/ChapterView.tsx`
  - `web/src/App.tsx` — shell + routing.
  - `web/src/test/*.test.tsx` — Vitest component tests.
- `requirements.txt` — add `fastapi`, `uvicorn[standard]`.
- `README.md` — "Run the web UI" section.

---

## Task 1: Backend scaffold + health endpoint

**Files:**
- Create: `api/__init__.py`, `api/main.py`, `api/routes.py`
- Modify: `requirements.txt`
- Test: `tests/test_api.py`

- [ ] **Step 1: Add dependencies**

In `requirements.txt` append:

```
fastapi>=0.110.0            # web UI backend
uvicorn[standard]>=0.29.0   # ASGI server for the web UI
```

Then run: `pip install "fastapi>=0.110.0" "uvicorn[standard]>=0.29.0"`

- [ ] **Step 2: Write the failing test**

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient

from api.main import create_app


def test_health_ok():
    client = TestClient(create_app())
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_health_ok -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api'`.

- [ ] **Step 4: Create the package and app**

`api/__init__.py`:

```python
from .main import create_app

__all__ = ["create_app"]
```

`api/routes.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}
```

`api/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Novel OS API", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py::test_health_ok -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/ tests/test_api.py requirements.txt
git commit -m "feat(api): scaffold FastAPI app with health endpoint"
```

---

## Task 2: ProjectService.list_projects + a test fixture

**Files:**
- Create: `api/services.py`, `api/models.py`
- Test: `tests/test_api.py` (add fixture + test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py` (top, after imports):

```python
import json
from pathlib import Path

import pytest


def _seed_project(root: Path, slug: str, title: str, genre: str,
                  chapters: dict | None = None) -> None:
    state_dir = root / slug / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "metadata": {"title": title, "genre": genre, "author": "Test Author"},
        "characters": {},
        "plot_threads": {},
        "chapters": chapters or {},
        "timeline": [],
        "style_profile": {},
        "session_log": [],
    }
    (state_dir / "story_state.json").write_text(json.dumps(state), encoding="utf-8")


@pytest.fixture
def projects_root(tmp_path):
    _seed_project(tmp_path, "the-last-signal", "The Last Signal", "Sci-Fi Thriller")
    return tmp_path
```

Then add the test:

```python
from api.services import ProjectService


def test_list_projects(projects_root):
    svc = ProjectService(projects_root)
    projects = svc.list_projects()
    assert len(projects) == 1
    assert projects[0].id == "the-last-signal"
    assert projects[0].title == "The Last Signal"
    assert projects[0].chapter_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_list_projects -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.services'`.

- [ ] **Step 3: Create the Pydantic models**

`api/models.py`:

```python
from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    chapter_count: int
    status: str


class ChapterSummary(BaseModel):
    number: int
    title: str
    status: str
    word_count: int
    pov: str


class ChapterDetail(ChapterSummary):
    outline: str | None
    draft: str | None


class CharacterSummary(BaseModel):
    id: str
    full_name: str
    role: str


class ProjectDetail(BaseModel):
    id: str
    title: str
    genre: str
    author: str
    chapter_count: int
    status: str
    style: dict
```

- [ ] **Step 4: Create the service**

`api/services.py`:

```python
import sys
from pathlib import Path

from .models import (
    ChapterDetail, ChapterSummary, CharacterSummary, ProjectDetail, ProjectSummary,
)

# core/ modules import each other by top-level name; put core/ on the path once.
_CORE = Path(__file__).resolve().parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from state_manager import StoryState  # noqa: E402


class ProjectNotFound(Exception):
    pass


class ChapterNotFound(Exception):
    pass


class ProjectService:
    """Reads Novel OS projects (folders containing outputs/state/story_state.json)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    # --- discovery
    def _project_dir(self, project_id: str) -> Path:
        d = self.root / project_id
        if not (d / "outputs" / "state" / "story_state.json").exists():
            raise ProjectNotFound(project_id)
        return d

    def _load(self, project_id: str) -> StoryState:
        return StoryState(str(self._project_dir(project_id)))

    def list_projects(self) -> list[ProjectSummary]:
        out: list[ProjectSummary] = []
        if not self.root.exists():
            return out
        for child in sorted(self.root.iterdir()):
            state_file = child / "outputs" / "state" / "story_state.json"
            if not state_file.exists():
                continue
            s = StoryState(str(child))
            out.append(ProjectSummary(
                id=child.name,
                title=s.metadata.get("title", child.name),
                genre=s.metadata.get("genre", ""),
                chapter_count=len(s.chapters),
                status=s.metadata.get("status", "in_progress"),
            ))
        return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py::test_list_projects -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/services.py api/models.py tests/test_api.py
git commit -m "feat(api): ProjectService.list_projects over on-disk projects"
```

---

## Task 3: GET /api/projects wired to the service

**Files:**
- Modify: `api/routes.py`, `api/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def _client(projects_root):
    app = create_app(projects_root=projects_root)
    return TestClient(app)


def test_get_projects_endpoint(projects_root):
    resp = _client(projects_root).get("/api/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id"] == "the-last-signal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py::test_get_projects_endpoint -v`
Expected: FAIL — `create_app()` takes no `projects_root`, and `/api/projects` 404s.

- [ ] **Step 3: Make the service injectable + add the route**

Replace `api/routes.py` with:

```python
import os
from pathlib import Path

from fastapi import APIRouter, Depends

from .models import ProjectSummary
from .services import ProjectService

router = APIRouter(prefix="/api")


def get_service() -> ProjectService:
    root = Path(os.environ.get("NOVEL_OS_PROJECTS_DIR", "./projects"))
    return ProjectService(root)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(svc: ProjectService = Depends(get_service)):
    return svc.list_projects()
```

Update `api/main.py` `create_app` to accept an optional root and override the dependency:

```python
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router, get_service
from .services import ProjectService


def create_app(projects_root: Optional[Path] = None) -> FastAPI:
    app = FastAPI(title="Novel OS API", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    if projects_root is not None:
        app.dependency_overrides[get_service] = lambda: ProjectService(projects_root)
    return app


app = create_app()
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_api.py -v`
Expected: all PASS (health, list_projects, get_projects_endpoint).

- [ ] **Step 5: Commit**

```bash
git add api/routes.py api/main.py tests/test_api.py
git commit -m "feat(api): GET /api/projects endpoint with injectable projects root"
```

---

## Task 4: Project detail + chapters endpoints

**Files:**
- Modify: `api/services.py`, `api/routes.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
def test_project_detail(projects_root):
    resp = _client(projects_root).get("/api/projects/the-last-signal")
    assert resp.status_code == 200
    assert resp.json()["author"] == "Test Author"


def test_project_detail_404(projects_root):
    resp = _client(projects_root).get("/api/projects/nope")
    assert resp.status_code == 404


def test_chapters_list(tmp_path):
    chapters = {"1": {"number": 1, "title": "Opening", "status": "drafted",
                      "word_count": 2300, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    resp = _client(tmp_path).get("/api/projects/p/chapters")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows[0]["number"] == 1
    assert rows[0]["pov"] == "Lena"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py -k "project_detail or chapters_list" -v`
Expected: FAIL — endpoints/methods do not exist (404).

- [ ] **Step 3: Add service methods**

Append to `ProjectService` in `api/services.py`:

```python
    def project_detail(self, project_id: str) -> ProjectDetail:
        s = self._load(project_id)
        return ProjectDetail(
            id=project_id,
            title=s.metadata.get("title", project_id),
            genre=s.metadata.get("genre", ""),
            author=s.metadata.get("author", ""),
            chapter_count=len(s.chapters),
            status=s.metadata.get("status", "in_progress"),
            style={
                "tone": s.style_profile.tone,
                "point_of_view": s.style_profile.point_of_view,
                "prose_style": s.style_profile.prose_style,
            },
        )

    def list_chapters(self, project_id: str) -> list[ChapterSummary]:
        s = self._load(project_id)
        return [
            ChapterSummary(
                number=c.number,
                title=c.title or "",
                status=c.status,
                word_count=c.word_count,
                pov=c.pov_character or "",
            )
            for c in sorted(s.chapters.values(), key=lambda c: c.number)
        ]
```

- [ ] **Step 4: Add routes + 404 handling**

In `api/routes.py` add imports and routes:

```python
from fastapi import HTTPException

from .models import ChapterSummary, ProjectDetail
from .services import ProjectNotFound


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def project_detail(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.project_detail(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterSummary])
def list_chapters(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_chapters(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_api.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/services.py api/routes.py tests/test_api.py
git commit -m "feat(api): project detail and chapters list endpoints"
```

---

## Task 5: Chapter detail (outline + draft), characters, raw state

**Files:**
- Modify: `api/services.py`, `api/routes.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py`:

```python
def test_chapter_detail_with_files(tmp_path):
    chapters = {"1": {"number": 1, "title": "Opening", "status": "drafted",
                      "word_count": 5, "pov_character": "Lena"}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    proj = tmp_path / "p"
    (proj / "outputs" / "chapter_001_outline.md").write_text("# Beat sheet", encoding="utf-8")
    (proj / "outputs" / "manuscript").mkdir(parents=True, exist_ok=True)
    (proj / "outputs" / "manuscript" / "chapter_001_draft.md").write_text("Prose here", encoding="utf-8")
    resp = _client(tmp_path).get("/api/projects/p/chapters/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["outline"] == "# Beat sheet"
    assert body["draft"] == "Prose here"


def test_chapter_detail_missing_files(tmp_path):
    chapters = {"2": {"number": 2, "title": "", "status": "planned",
                      "word_count": 0, "pov_character": ""}}
    _seed_project(tmp_path, "p", "P", "Drama", chapters=chapters)
    body = _client(tmp_path).get("/api/projects/p/chapters/2").json()
    assert body["outline"] is None
    assert body["draft"] is None


def test_chapter_404(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    resp = _client(tmp_path).get("/api/projects/p/chapters/9")
    assert resp.status_code == 404


def test_characters_endpoint(tmp_path):
    _seed_project(tmp_path, "p", "P", "Drama")
    # inject a character into the seeded state
    sf = tmp_path / "p" / "outputs" / "state" / "story_state.json"
    data = json.loads(sf.read_text())
    data["characters"] = {"char_001": {"id": "char_001", "full_name": "Lena", "role": "protagonist"}}
    sf.write_text(json.dumps(data), encoding="utf-8")
    rows = _client(tmp_path).get("/api/projects/p/characters").json()
    assert rows[0]["full_name"] == "Lena"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py -k "chapter_detail or chapter_404 or characters_endpoint" -v`
Expected: FAIL — routes/methods missing.

- [ ] **Step 3: Add service methods**

Append to `ProjectService`:

```python
    def chapter_detail(self, project_id: str, number: int) -> ChapterDetail:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        proj = self._project_dir(project_id)
        nnn = f"{number:03d}"
        outline_path = proj / "outputs" / f"chapter_{nnn}_outline.md"
        draft_path = proj / "outputs" / "manuscript" / f"chapter_{nnn}_draft.md"
        return ChapterDetail(
            number=c.number,
            title=c.title or "",
            status=c.status,
            word_count=c.word_count,
            pov=c.pov_character or "",
            outline=outline_path.read_text(encoding="utf-8") if outline_path.exists() else None,
            draft=draft_path.read_text(encoding="utf-8") if draft_path.exists() else None,
        )

    def list_characters(self, project_id: str) -> list[CharacterSummary]:
        s = self._load(project_id)
        return [
            CharacterSummary(id=c.id, full_name=c.full_name, role=c.role)
            for c in s.get_all_characters()
        ]

    def raw_state(self, project_id: str) -> dict:
        import json as _json
        sf = self._project_dir(project_id) / "outputs" / "state" / "story_state.json"
        return _json.loads(sf.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Add routes**

In `api/routes.py` add imports `ChapterDetail, CharacterSummary` and `ChapterNotFound`, then:

```python
@router.get("/projects/{project_id}/chapters/{number}", response_model=ChapterDetail)
def chapter_detail(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        return svc.chapter_detail(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.get("/projects/{project_id}/characters", response_model=list[CharacterSummary])
def list_characters(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_characters(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/state")
def raw_state(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.raw_state(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
```

- [ ] **Step 5: Run the full backend suite**

Run: `python -m pytest tests/test_api.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/services.py api/routes.py tests/test_api.py
git commit -m "feat(api): chapter detail, characters, and raw state endpoints"
```

---

## Task 6: Frontend scaffold + typed API client

**Files:**
- Create: `web/` (Vite app), `web/src/api/client.ts`
- Modify: `web/package.json` (scripts), `web/vite.config.ts`

- [ ] **Step 1: Scaffold the app**

Run from repo root:

```bash
npm create vite@latest web -- --template react-ts
cd web && npm install && npm install react-router-dom react-markdown && npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

- [ ] **Step 2: Configure Vitest**

In `web/vite.config.ts`, add a `test` block:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: "./src/test/setup.ts" },
});
```

Create `web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom";
```

Add to `web/package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 3: Write the typed client**

Create `web/src/api/client.ts`:

```ts
const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface ProjectSummary {
  id: string; title: string; genre: string; chapter_count: number; status: string;
}
export interface ChapterSummary {
  number: number; title: string; status: string; word_count: number; pov: string;
}
export interface ChapterDetail extends ChapterSummary {
  outline: string | null; draft: string | null;
}
export interface ProjectDetail {
  id: string; title: string; genre: string; author: string;
  chapter_count: number; status: string; style: Record<string, string>;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

export const api = {
  projects: () => get<ProjectSummary[]>("/api/projects"),
  project: (id: string) => get<ProjectDetail>(`/api/projects/${id}`),
  chapters: (id: string) => get<ChapterSummary[]>(`/api/projects/${id}/chapters`),
  chapter: (id: string, n: number) => get<ChapterDetail>(`/api/projects/${id}/chapters/${n}`),
};
```

- [ ] **Step 4: Verify the app builds**

Run: `cd web && npm run build`
Expected: build succeeds (no type errors).

- [ ] **Step 5: Commit**

```bash
git add web/
git commit -m "feat(web): scaffold Vite React app with typed API client"
```

---

## Task 7: Projects list screen (component test first)

**Files:**
- Create: `web/src/components/ProjectCard.tsx`, `web/src/routes/ProjectsList.tsx`, `web/src/test/ProjectsList.test.tsx`

- [ ] **Step 1: Write the failing component test**

Create `web/src/test/ProjectsList.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import ProjectsList from "../routes/ProjectsList";
import * as client from "../api/client";

test("renders project cards from the API", async () => {
  vi.spyOn(client.api, "projects").mockResolvedValue([
    { id: "the-last-signal", title: "The Last Signal", genre: "Sci-Fi", chapter_count: 3, status: "in_progress" },
  ]);
  render(<MemoryRouter><ProjectsList /></MemoryRouter>);
  expect(await screen.findByText("The Last Signal")).toBeInTheDocument();
  expect(screen.getByText(/3 chapters/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- ProjectsList`
Expected: FAIL — module `../routes/ProjectsList` not found.

- [ ] **Step 3: Implement the components**

`web/src/components/ProjectCard.tsx`:

```tsx
import { Link } from "react-router-dom";
import type { ProjectSummary } from "../api/client";

export default function ProjectCard({ p }: { p: ProjectSummary }) {
  return (
    <Link to={`/projects/${p.id}`} className="project-card">
      <h3>{p.title}</h3>
      <p>{p.genre}</p>
      <span>{p.chapter_count} chapters · {p.status}</span>
    </Link>
  );
}
```

`web/src/routes/ProjectsList.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api, type ProjectSummary } from "../api/client";
import ProjectCard from "../components/ProjectCard";

export default function ProjectsList() {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects().then(setProjects).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error">Failed to load projects: {error}</div>;
  if (!projects) return <div>Loading…</div>;
  if (projects.length === 0)
    return <div>No projects yet. Create one with the CLI: <code>python core/orchestrator.py init …</code></div>;
  return (
    <div className="projects-grid">
      {projects.map((p) => <ProjectCard key={p.id} p={p} />)}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- ProjectsList`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): projects list screen"
```

---

## Task 8: Project dashboard + chapter board

**Files:**
- Create: `web/src/components/ChapterBoard.tsx`, `web/src/routes/ProjectDashboard.tsx`, `web/src/test/ProjectDashboard.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/test/ProjectDashboard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";
import ProjectDashboard from "../routes/ProjectDashboard";
import * as client from "../api/client";

test("shows project title and chapter cards", async () => {
  vi.spyOn(client.api, "project").mockResolvedValue({
    id: "p", title: "My Novel", genre: "Drama", author: "A",
    chapter_count: 1, status: "in_progress", style: {},
  });
  vi.spyOn(client.api, "chapters").mockResolvedValue([
    { number: 1, title: "Opening", status: "drafted", word_count: 2300, pov: "Lena" },
  ]);
  render(
    <MemoryRouter initialEntries={["/projects/p"]}>
      <Routes><Route path="/projects/:id" element={<ProjectDashboard />} /></Routes>
    </MemoryRouter>
  );
  expect(await screen.findByText("My Novel")).toBeInTheDocument();
  expect(screen.getByText("Opening")).toBeInTheDocument();
  expect(screen.getByText(/drafted/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- ProjectDashboard`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`web/src/components/ChapterBoard.tsx`:

```tsx
import { Link, useParams } from "react-router-dom";
import type { ChapterSummary } from "../api/client";

export default function ChapterBoard({ chapters }: { chapters: ChapterSummary[] }) {
  const { id } = useParams();
  return (
    <div className="chapter-board">
      {chapters.map((c) => (
        <Link key={c.number} to={`/projects/${id}/chapters/${c.number}`} className="chapter-card">
          <strong>Ch {c.number}</strong>
          <span>{c.title || "Untitled"}</span>
          <span className={`pill ${c.status}`}>{c.status}</span>
          <span>{c.word_count} words</span>
        </Link>
      ))}
    </div>
  );
}
```

`web/src/routes/ProjectDashboard.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type ProjectDetail, type ChapterSummary } from "../api/client";
import ChapterBoard from "../components/ChapterBoard";

export default function ProjectDashboard() {
  const { id = "" } = useParams();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.project(id).then(setProject).catch((e) => setError(String(e)));
    api.chapters(id).then(setChapters).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <div className="error">Failed to load: {error}</div>;
  if (!project) return <div>Loading…</div>;
  return (
    <div className="dashboard">
      <header>
        <h2>{project.title}</h2>
        <p>{project.genre} · by {project.author || "Unknown"}</p>
      </header>
      <ChapterBoard chapters={chapters} />
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- ProjectDashboard`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): project dashboard with chapter board"
```

---

## Task 9: Chapter view (outline + draft as Markdown)

**Files:**
- Create: `web/src/routes/ChapterView.tsx`, `web/src/test/ChapterView.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/test/ChapterView.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi } from "vitest";
import ChapterView from "../routes/ChapterView";
import * as client from "../api/client";

test("renders outline and draft, with a fallback when missing", async () => {
  vi.spyOn(client.api, "chapter").mockResolvedValue({
    number: 1, title: "Opening", status: "drafted", word_count: 5, pov: "Lena",
    outline: "# Beats", draft: null,
  });
  render(
    <MemoryRouter initialEntries={["/projects/p/chapters/1"]}>
      <Routes><Route path="/projects/:id/chapters/:n" element={<ChapterView />} /></Routes>
    </MemoryRouter>
  );
  expect(await screen.findByText("Beats")).toBeInTheDocument();
  expect(screen.getByText(/not generated yet/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- ChapterView`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

`web/src/routes/ChapterView.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { api, type ChapterDetail } from "../api/client";

export default function ChapterView() {
  const { id = "", n = "0" } = useParams();
  const [chapter, setChapter] = useState<ChapterDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.chapter(id, Number(n)).then(setChapter).catch((e) => setError(String(e)));
  }, [id, n]);

  if (error) return <div className="error">Failed to load: {error}</div>;
  if (!chapter) return <div>Loading…</div>;
  return (
    <div className="chapter-view">
      <header>
        <h2>Chapter {chapter.number}: {chapter.title || "Untitled"}</h2>
        <span>{chapter.status} · {chapter.word_count} words · POV {chapter.pov || "—"}</span>
      </header>
      <div className="panes">
        <section>
          <h3>Outline</h3>
          {chapter.outline ? <ReactMarkdown>{chapter.outline}</ReactMarkdown>
                           : <p className="muted">Outline not generated yet.</p>}
        </section>
        <section>
          <h3>Draft</h3>
          {chapter.draft ? <ReactMarkdown>{chapter.draft}</ReactMarkdown>
                         : <p className="muted">Draft not generated yet.</p>}
        </section>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- ChapterView`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src
git commit -m "feat(web): chapter view rendering outline and draft markdown"
```

---

## Task 10: App shell + routing + README

**Files:**
- Modify: `web/src/App.tsx`, `web/src/main.tsx`
- Modify: `README.md`
- Test: `web/src/test/App.test.tsx`

- [ ] **Step 1: Write the failing routing test**

Create `web/src/test/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App from "../App";
import * as client from "../api/client";

test("renders the app shell with the wordmark", async () => {
  vi.spyOn(client.api, "projects").mockResolvedValue([]);
  render(<App />);
  expect(screen.getByText(/Novel OS/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- App`
Expected: FAIL — `App` does not export the shell/router yet.

- [ ] **Step 3: Implement the shell + router**

Replace `web/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import ProjectsList from "./routes/ProjectsList";
import ProjectDashboard from "./routes/ProjectDashboard";
import ChapterView from "./routes/ChapterView";

export default function App() {
  return (
    <BrowserRouter>
      <header className="topbar">
        <Link to="/" className="wordmark">🦉 Novel OS</Link>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<ProjectsList />} />
          <Route path="/projects/:id" element={<ProjectDashboard />} />
          <Route path="/projects/:id/chapters/:n" element={<ChapterView />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
```

Ensure `web/src/main.tsx` renders `<App />` (Vite default already does; remove any leftover demo markup/CSS imports that break the build).

- [ ] **Step 4: Run the full frontend suite + build**

Run: `cd web && npm run test && npm run build`
Expected: all tests PASS, build succeeds.

- [ ] **Step 5: Document how to run it**

Add a "Run the web UI" section to `README.md`:

````markdown
## 🖥️ Web UI (local)

Two processes — the API and the React dev server:

```bash
# 1. Backend (from repo root)
pip install -r requirements.txt
export NOVEL_OS_PROJECTS_DIR=./projects   # folder of project dirs
uvicorn api.main:app --reload --port 8000

# 2. Frontend (in another terminal)
cd web && npm install && npm run dev      # http://localhost:5173
```

Each project is a folder under `NOVEL_OS_PROJECTS_DIR` containing
`outputs/state/story_state.json` (created by `python core/orchestrator.py init …`).
````

- [ ] **Step 6: Commit**

```bash
git add web/src README.md
git commit -m "feat(web): app shell, routing, and web UI run docs"
```

---

## Task 11: End-to-end smoke (manual, documented)

**Files:** none (verification only)

- [ ] **Step 1: Seed a project**

```bash
mkdir -p projects && cd projects
python ../core/orchestrator.py init --title "Smoke Novel" --genre "Drama"
cd ..
```

Note: `init` writes to `./projects/outputs/...`. For the UI, the project must be its
own subfolder. Move it: `mkdir -p projects/smoke-novel && mv projects/outputs projects/smoke-novel/`.
(Folder-per-project creation from the UI/CLI is a later slice; this is a manual step for the smoke test.)

- [ ] **Step 2: Run both servers and verify**

Start `uvicorn api.main:app --port 8000` and `cd web && npm run dev`. Open
`http://localhost:5173`. Expected: "Smoke Novel" card appears; clicking it shows the
dashboard; chapters (if any planned) render; a chapter shows outline/draft or the
"not generated yet" fallback.

- [ ] **Step 3: Confirm the backend suite is green**

Run: `python -m pytest tests/ -v`
Expected: all PASS (existing 17 + new API tests).

---

## Notes for the executor

- Run backend tests with `python -m pytest tests/test_api.py` from repo root.
- Run frontend tests with `npm run test` inside `web/`.
- The `NOVEL_OS_PROJECTS_DIR` default is `./projects`; tests inject a temp dir via
  `create_app(projects_root=...)`, so they never touch the real folder.
- Do not modify anything under `core/` — the API only reads through `StoryState`.
