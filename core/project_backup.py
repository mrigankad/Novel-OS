"""
Project-level backup and restore — zips outputs/ plus a SQLite export.

Named backups live in backups/named/{id}.zip.
Quick save uses backups/_quick/current.zip (previous slot rotated).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
QUICK_DIR = "_quick"
NAMED_DIR = "named"
QUICK_CURRENT = "current.zip"
QUICK_PREVIOUS = "previous.zip"
QUICK_PRE_RESTORE = "pre_restore.zip"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return out.strip("-") or "backup"


def backups_root(project_dir: Path) -> Path:
    return project_dir / "backups"


def manifest_path(project_dir: Path) -> Path:
    return backups_root(project_dir) / MANIFEST_NAME


def _load_manifest(project_dir: Path) -> dict:
    path = manifest_path(project_dir)
    if not path.exists():
        return {"version": BACKUP_VERSION, "named": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_manifest(project_dir: Path, data: dict) -> None:
    root = backups_root(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path(project_dir).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _quick_path(project_dir: Path, name: str) -> Path:
    return backups_root(project_dir) / QUICK_DIR / name


def _quick_meta(project_dir: Path) -> dict:
    out: dict[str, Optional[dict]] = {
        "current": None,
        "previous": None,
        "pre_restore": None,
    }
    for key, fname in (
        ("current", QUICK_CURRENT),
        ("previous", QUICK_PREVIOUS),
        ("pre_restore", QUICK_PRE_RESTORE),
    ):
        p = _quick_path(project_dir, fname)
        if p.exists():
            stat = p.stat()
            out[key] = {
                "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "size_bytes": stat.st_size,
            }
    return out


def list_backups(project_dir: Path) -> dict:
    manifest = _load_manifest(project_dir)
    named = []
    for entry in manifest.get("named", []):
        zip_path = backups_root(project_dir) / NAMED_DIR / entry.get(
            "filename", f"{entry['id']}.zip"
        )
        if not zip_path.exists():
            continue
        named.append({**entry, "size_bytes": zip_path.stat().st_size})
    named.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"named": named, "quick": _quick_meta(project_dir)}


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def create_archive(
    project_dir: Path,
    dest: Path,
    *,
    db_export: dict,
    on_progress: Optional[Callable[[str], None]] = None,
) -> int:
    """Zip outputs/ and db_export.json. Returns archive size in bytes."""
    outputs = project_dir / "outputs"
    if not outputs.is_dir():
        raise ValueError("Project has no outputs/ directory to back up.")

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    file_count = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "db_export.json",
            json.dumps(db_export, ensure_ascii=False, indent=2),
        )
        for path in sorted(outputs.rglob("*")):
            if not path.is_file():
                continue
            arc = path.relative_to(project_dir).as_posix()
            zf.write(path, arc)
            file_count += 1
            if on_progress and file_count % 10 == 0:
                on_progress(f"Archived {file_count} files…")

    os.replace(tmp, dest)
    if on_progress:
        on_progress(f"Backup complete ({file_count} files)")
    return dest.stat().st_size


def restore_archive(
    project_dir: Path,
    zip_path: Path,
    *,
    import_db: Callable[[dict], None],
    sync_artifacts: Callable[[], None],
) -> None:
    """Replace outputs/ and DB rows from a backup archive."""
    if not zip_path.exists():
        raise FileNotFoundError(f"Backup not found: {zip_path}")

    extract_root = project_dir / "backups" / "_restore_tmp"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_root)

        db_file = extract_root / "db_export.json"
        if not db_file.exists():
            raise ValueError("Backup is missing db_export.json")
        db_data = json.loads(db_file.read_text(encoding="utf-8"))
        if db_data.get("version") != BACKUP_VERSION:
            raise ValueError(f"Unsupported backup version: {db_data.get('version')}")

        outputs_src = extract_root / "outputs"
        if not outputs_src.is_dir():
            raise ValueError("Backup is missing outputs/")

        outputs_dest = project_dir / "outputs"
        if outputs_dest.exists():
            shutil.rmtree(outputs_dest)
        shutil.copytree(outputs_src, outputs_dest)

        import_db(db_data)
        sync_artifacts()
    finally:
        if extract_root.exists():
            shutil.rmtree(extract_root)


def _write_named_backup(
    project_dir: Path,
    label: str,
    *,
    db_export: dict,
) -> dict:
    manifest = _load_manifest(project_dir)
    bid = uuid.uuid4().hex[:10]
    created = _now()
    slug = _slug(label)[:40]
    zip_name = f"{bid}_{slug}.zip"
    zip_path = backups_root(project_dir) / NAMED_DIR / zip_name
    size = create_archive(project_dir, zip_path, db_export=db_export)
    entry = {
        "id": bid,
        "label": label.strip() or "Backup",
        "created_at": created,
        "filename": zip_name,
        "size_bytes": size,
    }
    manifest.setdefault("named", []).append(entry)
    _save_manifest(project_dir, manifest)
    return entry


def create_named_backup(project_dir: Path, label: str, *, db_export: dict) -> dict:
    return _write_named_backup(project_dir, label, db_export=db_export)


def delete_named_backup(project_dir: Path, backup_id: str) -> bool:
    manifest = _load_manifest(project_dir)
    named: List[dict] = manifest.get("named", [])
    kept: List[dict] = []
    removed = False
    for entry in named:
        if entry.get("id") == backup_id:
            zip_path = backups_root(project_dir) / NAMED_DIR / entry.get("filename", f"{backup_id}.zip")
            if zip_path.exists():
                zip_path.unlink()
            removed = True
        else:
            kept.append(entry)
    if not removed:
        return False
    manifest["named"] = kept
    _save_manifest(project_dir, manifest)
    return True


def restore_named_backup(
    project_dir: Path,
    backup_id: str,
    *,
    import_db: Callable[[dict], None],
    sync_artifacts: Callable[[], None],
) -> dict:
    manifest = _load_manifest(project_dir)
    entry = next((e for e in manifest.get("named", []) if e.get("id") == backup_id), None)
    if entry is None:
        raise FileNotFoundError(f"Unknown backup {backup_id!r}")
    zip_path = backups_root(project_dir) / NAMED_DIR / entry.get("filename", f"{backup_id}.zip")
    restore_archive(project_dir, zip_path, import_db=import_db, sync_artifacts=sync_artifacts)
    return entry


def quick_save(project_dir: Path, *, db_export: dict) -> dict:
    quick_dir = backups_root(project_dir) / QUICK_DIR
    quick_dir.mkdir(parents=True, exist_ok=True)
    current = _quick_path(project_dir, QUICK_CURRENT)
    previous = _quick_path(project_dir, QUICK_PREVIOUS)
    if current.exists():
        if previous.exists():
            previous.unlink()
        os.replace(current, previous)
    size = create_archive(project_dir, current, db_export=db_export)
    return {
        "created_at": _now(),
        "size_bytes": size,
        "quick": _quick_meta(project_dir),
    }


def quick_restore(
    project_dir: Path,
    *,
    db_export: dict,
    import_db: Callable[[dict], None],
    sync_artifacts: Callable[[], None],
) -> dict:
    current = _quick_path(project_dir, QUICK_CURRENT)
    if not current.exists():
        raise FileNotFoundError("No quick save found — use Quick Save first.")

    pre = _quick_path(project_dir, QUICK_PRE_RESTORE)
    if pre.exists():
        pre.unlink()
    create_archive(project_dir, pre, db_export=db_export)

    restore_archive(project_dir, current, import_db=import_db, sync_artifacts=sync_artifacts)
    return {"restored_from": "current", "quick": _quick_meta(project_dir)}


def undo_quick_restore(
    project_dir: Path,
    *,
    import_db: Callable[[dict], None],
    sync_artifacts: Callable[[], None],
) -> dict:
    pre = _quick_path(project_dir, QUICK_PRE_RESTORE)
    if not pre.exists():
        raise FileNotFoundError("Nothing to undo — no pre-restore snapshot.")
    restore_archive(project_dir, pre, import_db=import_db, sync_artifacts=sync_artifacts)
    return {"restored_from": "pre_restore", "quick": _quick_meta(project_dir)}
