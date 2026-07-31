"""Tenancy schema and workspace-scoped project resolution (PLAN.md P0.5).

Schema only there is no auth yet. What matters here is that (a) local
single-user layout is unchanged, and (b) a project id cannot be used to reach
outside its workspace.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import db, tenancy
from api.main import create_app
from api.services import ProjectNotFound, ProjectService


def _seed(root: Path, slug: str, title: str = "Book") -> None:
    state_dir = root / slug / "outputs" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "story_state.json").write_text(json.dumps({
        "metadata": {"title": title, "genre": "SF", "author": "A"},
        "characters": {}, "plot_threads": {}, "chapters": {},
        "timeline": [], "style_profile": {}, "session_log": [],
    }), encoding="utf-8")


@pytest.fixture
def configured_db(tmp_path):
    db.configure(f"sqlite:///{(tmp_path / 'tenancy.db').as_posix()}")
    db._clear_all()
    return tmp_path


# ----------------------------------------------------------------- id validation

@pytest.mark.parametrize("bad", [
    "", "..", "../evil", "../../etc/passwd", "a/b", "a\\b", "/abs", "C:\\win",
    ".hidden", "-leading",
])
def test_invalid_project_ids_are_rejected(bad):
    assert tenancy.valid_project_id(bad) is False


@pytest.mark.parametrize("good", ["book", "the-last-signal", "book_2", "a.b", "Book1"])
def test_valid_project_ids_are_accepted(good):
    assert tenancy.valid_project_id(good) is True


def test_project_dir_refuses_traversal(tmp_path):
    with pytest.raises(tenancy.TenancyError):
        tenancy.project_dir(tmp_path, "../outside")


# ------------------------------------------------------------------- namespacing

def test_default_workspace_keeps_the_existing_flat_layout(tmp_path):
    """An existing local install must not need its folders moved."""
    assert tenancy.workspace_dir(tmp_path, None) == tmp_path
    assert tenancy.project_dir(tmp_path, "book") == (tmp_path / "book").resolve()


def test_other_workspaces_are_namespaced(configured_db):
    root = configured_db
    ws = db.workspace_create(id="w2", name="Second", slug="second")
    assert tenancy.workspace_dir(root, ws) == root / "ws-second"
    assert tenancy.project_dir(root, "book", ws) == (root / "ws-second" / "book").resolve()


def test_default_workspace_is_created_once(configured_db):
    first = tenancy.ensure_default_workspace()
    second = tenancy.ensure_default_workspace()
    assert first.id == second.id == tenancy.DEFAULT_WORKSPACE_ID
    assert len(db.workspaces_list()) == 1


def test_slugify_produces_a_path_safe_segment():
    assert tenancy.slugify("Mriga's  Studio!") == "mriga-s-studio"
    assert tenancy.slugify("") == "workspace"


# ------------------------------------------------------------------- membership

def test_roles_are_ordered_owner_editor_viewer(configured_db):
    tenancy.ensure_default_workspace()
    user = db.user_create(email="a@example.com", display_name="A")
    db.membership_add(user.id, tenancy.DEFAULT_WORKSPACE_ID, role="editor")

    assert tenancy.can_access(user.id, tenancy.DEFAULT_WORKSPACE_ID, "viewer") is True
    assert tenancy.can_access(user.id, tenancy.DEFAULT_WORKSPACE_ID, "editor") is True
    # An editor is not an owner.
    assert tenancy.can_access(user.id, tenancy.DEFAULT_WORKSPACE_ID, "owner") is False


def test_non_members_have_no_access(configured_db):
    tenancy.ensure_default_workspace()
    user = db.user_create(email="b@example.com")
    assert tenancy.can_access(user.id, tenancy.DEFAULT_WORKSPACE_ID) is False


def test_membership_add_is_idempotent_and_updates_role(configured_db):
    tenancy.ensure_default_workspace()
    user = db.user_create(email="c@example.com")
    db.membership_add(user.id, tenancy.DEFAULT_WORKSPACE_ID, role="viewer")
    db.membership_add(user.id, tenancy.DEFAULT_WORKSPACE_ID, role="owner")
    assert db.membership_get(user.id, tenancy.DEFAULT_WORKSPACE_ID).role == "owner"


# -------------------------------------------------------------------- ownership

def test_project_claim_records_and_updates_the_owning_workspace(configured_db):
    db.project_claim("book", "default")
    assert db.project_workspace("book") == "default"
    db.project_claim("book", "w2")
    assert db.project_workspace("book") == "w2"
    assert db.projects_for_workspace("w2") == ["book"]


# ---------------------------------------------------- ProjectService integration

def test_service_defaults_to_the_flat_root(tmp_path):
    _seed(tmp_path, "book")
    svc = ProjectService(tmp_path)
    assert [p.id for p in svc.list_projects()] == ["book"]


def test_service_scoped_to_a_workspace_sees_only_its_own_projects(configured_db):
    root = configured_db
    _seed(root, "default-book")
    ws = db.workspace_create(id="w2", name="Second", slug="second")
    _seed(root / "ws-second", "tenant-book")

    assert [p.id for p in ProjectService(root).list_projects()] == ["default-book"]
    assert [p.id for p in ProjectService(root, ws).list_projects()] == ["tenant-book"]


def test_a_workspace_cannot_read_another_workspaces_project(configured_db):
    root = configured_db
    _seed(root, "default-book")
    ws = db.workspace_create(id="w2", name="Second", slug="second")

    with pytest.raises(ProjectNotFound):
        ProjectService(root, ws).project_detail("default-book")


def test_traversal_in_a_project_id_reads_as_not_found(configured_db):
    """It must not be distinguishable from a missing project."""
    root = configured_db
    _seed(root, "book")
    ws = db.workspace_create(id="w2", name="Second", slug="second")
    with pytest.raises(ProjectNotFound):
        ProjectService(root, ws).project_detail("../book")


def test_creating_a_project_claims_it_for_the_workspace(configured_db, monkeypatch):
    root = configured_db

    class _FakeOrch:
        def __init__(self, folder): self.folder = Path(folder)
        def init_project(self, title, genre, author):
            _seed(self.folder.parent, self.folder.name, title)

    monkeypatch.setattr("api.services.build_orchestrator", _FakeOrch)

    svc = ProjectService(root)
    created = svc.create_project("The Last Signal", "Sci-Fi")
    assert db.project_workspace(created.id) == tenancy.DEFAULT_WORKSPACE_ID


def test_api_404s_on_a_traversing_project_id(tmp_path):
    root = tmp_path / "projects"
    _seed(root, "book")
    client = TestClient(create_app(
        projects_root=root, db_url=f"sqlite:///{(tmp_path / 'a.db').as_posix()}"))
    # Encoded traversal reaches the handler as a literal id.
    assert client.get("/api/projects/..%2F..%2Fetc/binder").status_code == 404
