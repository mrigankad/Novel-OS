"""
Portable project export/import — zip archives for sharing between installations.

Format matches project backups (outputs/ + db_export.json) with an optional
package_manifest.json for validation. Backup zips without a manifest import fine.
"""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Tuple

from project_backup import BACKUP_VERSION

PACKAGE_FORMAT = "novel-os-project"
PACKAGE_VERSION = 1
MANIFEST_NAME = "package_manifest.json"
DB_EXPORT_NAME = "db_export.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def package_manifest(*, project_id: str, title: str) -> dict:
    return {
        "format": PACKAGE_FORMAT,
        "version": PACKAGE_VERSION,
        "backup_version": BACKUP_VERSION,
        "exported_at": _now(),
        "source_project_id": project_id,
        "title": title,
    }


def build_package_bytes(
    project_dir: Path,
    db_export: dict,
    *,
    project_id: str,
    title: str,
) -> bytes:
    """Build a portable .zip containing outputs/ and DB export."""
    outputs = project_dir / "outputs"
    if not outputs.is_dir():
        raise ValueError("Project has no outputs/ directory to export.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            MANIFEST_NAME,
            json.dumps(package_manifest(project_id=project_id, title=title), indent=2),
        )
        zf.writestr(
            DB_EXPORT_NAME,
            json.dumps(db_export, ensure_ascii=False, indent=2),
        )
        for path in sorted(outputs.rglob("*")):
            if not path.is_file():
                continue
            arc = path.relative_to(project_dir).as_posix()
            zf.write(path, arc)
    return buf.getvalue()


def _read_title(extract_root: Path, db_data: dict) -> str:
    proj = db_data.get("project") or {}
    title = (proj.get("title") or "").strip()
    if title:
        return title
    state_file = extract_root / "outputs" / "state" / "story_state.json"
    if state_file.exists():
        meta = json.loads(state_file.read_text(encoding="utf-8")).get("metadata", {})
        title = (meta.get("title") or "").strip()
        if title:
            return title
    return "Imported project"


def validate_package(extract_root: Path) -> tuple[dict, Path]:
    """Validate extracted archive contents. Returns (db_export, outputs_dir)."""
    manifest_path = extract_root / MANIFEST_NAME
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") not in (PACKAGE_FORMAT, None):
            raise ValueError(f"Unsupported package format: {manifest.get('format')!r}")

    db_file = extract_root / DB_EXPORT_NAME
    if not db_file.exists():
        raise ValueError("Package is missing db_export.json")
    db_data = json.loads(db_file.read_text(encoding="utf-8"))
    if db_data.get("version") != BACKUP_VERSION:
        raise ValueError(f"Unsupported backup version: {db_data.get('version')}")

    outputs_src = extract_root / "outputs"
    if not outputs_src.is_dir():
        raise ValueError("Package is missing outputs/")
    state_file = outputs_src / "state" / "story_state.json"
    if not state_file.exists():
        raise ValueError("Package outputs/ is missing state/story_state.json")

    return db_data, outputs_src


def allocate_project_folder(root: Path, title: str, slugify: Callable[[str], str]) -> Path:
    """Pick a unique project folder name under root."""
    slug = slugify(title.strip() or "imported-project")
    folder = root / slug
    n = 2
    while folder.exists():
        folder = root / f"{slug}-{n}"
        n += 1
    return folder


def import_package_bytes(
    projects_root: Path,
    zip_bytes: bytes,
    *,
    import_db: Callable[[str, dict], None],
    sync_artifacts: Callable[[str], None],
    slugify: Callable[[str], str],
) -> Tuple[str, str]:
    """
    Import a portable package as a new project.
    Returns (project_id, title).
    """
    projects_root.mkdir(parents=True, exist_ok=True)
    extract_root = projects_root / "_import_tmp"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            zf.extractall(extract_root)

        db_data, outputs_src = validate_package(extract_root)
        title = _read_title(extract_root, db_data)
        project_dir = allocate_project_folder(projects_root, title, slugify)
        project_dir.mkdir(parents=True)
        shutil.copytree(outputs_src, project_dir / "outputs")

        project_id = project_dir.name
        import_db(project_id, db_data)
        sync_artifacts(project_id)
        return project_id, title
    finally:
        if extract_root.exists():
            shutil.rmtree(extract_root)
