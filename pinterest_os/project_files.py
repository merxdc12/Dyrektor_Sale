"""Portable ITHutir project folders and verified ZIP backups.

Project layout: project.sqlite3, assets/, manifest.json.
Imports always create a NEW folder; no destructive in-place restore.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from .workspace import backup_database, verify_database

DB_NAME = "project.sqlite3"
MANIFEST = "manifest.json"
FORMAT = "ithutir-pinterest-project-v1"
MAX_ARCHIVE_BYTES = 2 * 1024**3


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _asset_source(value: str, folder: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = folder / path
    return path.resolve()


def _copy_assets(db: sqlite3.Connection, folder: Path, source_root: Path | None = None) -> None:
    """Collect referenced files and store only project-relative asset paths."""
    source_root = source_root or folder
    folder_assets = folder / "assets"
    folder_assets.mkdir(exist_ok=True)
    rows = db.execute("SELECT pin_id,project_json,png_path FROM pin_designs").fetchall()
    updates = []
    for pin_id, raw, png in rows:
        project = json.loads(raw)
        for index, layer in enumerate(project.get("layers", [])):
            if layer.get("kind") != "image" or not layer.get("path"):
                continue
            source = _asset_source(layer["path"], source_root)
            if not source.is_file():
                raise FileNotFoundError(f"Missing image asset: {source}")
            extension = source.suffix.lower()
            if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise ValueError(f"Unsupported image asset: {source}")
            relative = f"assets/pin-{pin_id}-layer-{index}{extension}"
            destination = folder / relative
            if source != destination:
                shutil.copy2(source, destination)
            layer["path"] = relative
        if png:
            source = _asset_source(png, source_root)
            if not source.is_file():
                raise FileNotFoundError(f"Missing exported PNG: {source}")
            relative = f"assets/pin-{pin_id}-export.png"
            destination = folder / relative
            if source != destination:
                shutil.copy2(source, destination)
            png = relative
        updates.append((json.dumps(project, ensure_ascii=False), png, pin_id))
    with db:
        db.executemany(
            "UPDATE pin_designs SET project_json=?,png_path=? WHERE pin_id=?",
            updates
        )


def _manifest(folder: Path) -> dict:
    files = {
        p.relative_to(folder).as_posix(): _sha(p)
        for p in folder.rglob("*") if p.is_file() and p.name != MANIFEST
    }
    return {"format": FORMAT, "files": files}


def verify_project(folder: str | Path) -> None:
    folder = Path(folder).resolve()
    data = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    if data.get("format") != FORMAT or not isinstance(data.get("files"), dict):
        raise ValueError("Unsupported project manifest")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*")
              if p.is_file() and p.name != MANIFEST}
    if actual != set(data["files"]):
        raise ValueError("Project file list differs from manifest")
    for name, digest in data["files"].items():
        path = folder / name
        if not _inside(path, folder) or path.is_symlink() or _sha(path) != digest:
            raise ValueError(f"Project file failed validation: {name}")
    ok, reason = verify_database(folder / DB_NAME)
    if not ok:
        raise ValueError(f"SQLite integrity failure: {reason}")


def create_project(source: sqlite3.Connection, destination: str | Path) -> Path:
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Project destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        staged = Path(tmp) / "project"
        staged.mkdir()
        backup_database(source, staged / DB_NAME)
        db = sqlite3.connect(staged / DB_NAME)
        try:
            source_db = Path(source.execute("PRAGMA database_list").fetchone()[2]).resolve()
            _copy_assets(db, staged, source_db.parent)
        finally:
            db.close()
        (staged / MANIFEST).write_text(
            json.dumps(_manifest(staged), indent=2), encoding="utf-8")
        verify_project(staged)
        staged.rename(destination)
    return destination


def save_project(connection: sqlite3.Connection, folder: str | Path) -> None:
    """Bundle new assets on every Save and update the project manifest."""
    folder = Path(folder).resolve()
    db_path = Path(connection.execute("PRAGMA database_list").fetchone()[2]).resolve()
    if db_path != folder / DB_NAME:
        raise ValueError("Save requires the currently opened project")
    connection.commit()
    _copy_assets(connection, folder)
    ok, reason = verify_database(folder / DB_NAME)
    if not ok:
        raise ValueError(f"Database integrity failure: {reason}")
    (folder / MANIFEST).write_text(
        json.dumps(_manifest(folder), indent=2), encoding="utf-8")
    verify_project(folder)


def backup_project(folder: str | Path, destination: str | Path) -> Path:
    folder = Path(folder).resolve()
    verify_project(folder)
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError("Backup destination already exists")
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(folder).as_posix())
    return destination


def restore_project(archive_path: str | Path, destination: str | Path) -> Path:
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError("Restore destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        staged = Path(tmp) / "project"
        staged.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            if sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError("Archive exceeds 2 GiB uncompressed limit")
            for entry in entries:
                path = staged / entry.filename
                mode = entry.external_attr >> 16
                if (not _inside(path, staged) or entry.filename.startswith("/")
                        or (mode & 0o170000) == 0o120000):
                    raise ValueError("Unsafe archive entry")
                if entry.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as src, path.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
        verify_project(staged)
        staged.rename(destination)
    return destination
