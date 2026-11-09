"""Offline workspace backup and verification.

Backups are SQLite snapshots. External image assets are not included yet.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def verify_database(path: str | Path) -> tuple[bool, str]:
    source = Path(path)
    if not source.is_file():
        return False, "Database file not found"
    try:
        conn = sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            return result == "ok", str(result)
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, str(exc)


def backup_database(connection: sqlite3.Connection, destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Backup already exists: {destination}")
    # Exclusive create prevents accidental overwrite of existing backups.
    with destination.open("xb"):
        pass
    try:
        target = sqlite3.connect(destination)
        try:
            connection.backup(target)
        finally:
            target.close()
        valid, reason = verify_database(destination)
        if not valid:
            raise RuntimeError(f"Backup integrity check failed: {reason}")
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise
