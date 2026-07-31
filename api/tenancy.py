"""Tenancy workspaces, users, and project ownership (PLAN.md P0.5).

Schema only. There is no auth UI yet; P7 adds sign-in on top of these tables.
The point of doing it now is that project resolution, path namespacing and
ownership are decided *before* features are built against a single-tenant
assumption that would then have to be unpicked.

Two rules shape the design:

* **Local single-user usage must not change.** Projects live at
  `<root>/<project_id>` exactly as they do today. That layout is the default
  workspace. Only additional workspaces get a `ws-<slug>/` prefix, so an
  existing install keeps working with no migration and no moved folders.
* **Per-project files stay canonical** (design spec §4.1). These tables hold
  who may see a project, never the story itself.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from . import db

DEFAULT_WORKSPACE_ID = "default"
DEFAULT_WORKSPACE_SLUG = "default"

ROLES = ("owner", "editor", "viewer")

_SLUG = re.compile(r"[^a-z0-9-]+")

# A project id is a directory name. Anything outside this set cannot be part of
# one, which is what makes path construction safe rather than merely checked.
_PROJECT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class TenancyError(ValueError):
    pass


def slugify(text: str) -> str:
    return _SLUG.sub("-", (text or "").strip().lower()).strip("-") or "workspace"


def valid_project_id(project_id: str) -> bool:
    """Reject anything that is not a plain directory name.

    `..`, absolute paths, drive letters and separators all fail here, so a
    caller cannot walk out of the projects root or into another tenant.
    """
    return bool(project_id) and bool(_PROJECT_ID.fullmatch(project_id)) and project_id != ".."


def ensure_default_workspace() -> db.Workspace:
    """The workspace a local install implicitly runs in."""
    ws = db.workspace_get(DEFAULT_WORKSPACE_ID)
    if ws is None:
        ws = db.workspace_create(
            id=DEFAULT_WORKSPACE_ID, name="My Workspace", slug=DEFAULT_WORKSPACE_SLUG
        )
    return ws


def workspace_dir(root: Path, workspace: Optional[db.Workspace]) -> Path:
    """Where a workspace's projects live.

    The default workspace maps to the root itself so existing installs are
    untouched; every other workspace is namespaced under `ws-<slug>`.
    """
    root = Path(root)
    if workspace is None or workspace.id == DEFAULT_WORKSPACE_ID:
        return root
    return root / f"ws-{workspace.slug}"


def project_dir(root: Path, project_id: str,
                workspace: Optional[db.Workspace] = None) -> Path:
    """Resolve a project directory, refusing anything outside its workspace."""
    if not valid_project_id(project_id):
        raise TenancyError(f"Invalid project id {project_id!r}")
    base = workspace_dir(root, workspace).resolve()
    candidate = (base / project_id).resolve()
    # Belt and braces: the id pattern already forbids traversal, but resolving
    # through a symlink could still land outside the workspace.
    if candidate != base and base not in candidate.parents:
        raise TenancyError(f"Project {project_id!r} escapes its workspace")
    return candidate


def can_access(user_id: str, workspace_id: str, need: str = "viewer") -> bool:
    """Whether a user holds at least `need` on a workspace.

    Roles are ordered: owner > editor > viewer.
    """
    if need not in ROLES:
        raise TenancyError(f"Unknown role {need!r}")
    m = db.membership_get(user_id, workspace_id)
    if m is None:
        return False
    return ROLES.index(m.role) <= ROLES.index(need)
