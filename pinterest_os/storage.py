"""Local SQLite persistence. No network access or external APIs."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                target_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS boards (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pins (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                product_id INTEGER REFERENCES products(id),
                board_id INTEGER REFERENCES boards(id),
                status TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK(status IN ('DRAFT', 'IN_REVIEW', 'READY', 'PUBLISHED')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS work_sessions (
                id INTEGER PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                active_seconds INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS time_entries (
                id INTEGER PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES work_sessions(id),
                task TEXT NOT NULL,
                pin_id INTEGER REFERENCES pins(id),
                seconds INTEGER NOT NULL CHECK(seconds >= 0),
                created_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def add_board(self, name: str, url: str = "") -> int:
        name = name.strip()
        if not name:
            raise ValueError("Board name is required")
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO boards(name,url,created_at) VALUES(?,?,?)",
                (name, url.strip(), utc_now()),
            )
        return int(cursor.lastrowid)

    def add_pin(self, title: str) -> int:
        title = title.strip()
        if not title:
            raise ValueError("Pin title is required")
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO pins(title,created_at) VALUES(?,?)", (title, utc_now())
            )
        return int(cursor.lastrowid)

    def list_rows(self, table: str) -> list[tuple]:
        if table not in {"boards", "pins"}:
            raise ValueError("Unsupported table")
        return self.conn.execute(f"SELECT id, name FROM boards ORDER BY id DESC" if table == "boards"
                                 else "SELECT id, title FROM pins ORDER BY id DESC").fetchall()

    def start_session(self) -> int:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO work_sessions(started_at) VALUES(?)", (utc_now(),)
            )
        return int(cursor.lastrowid)

    def save_elapsed(self, session_id: int, seconds: int, task: str = "General") -> None:
        if seconds <= 0:
            return
        with self.conn:
            self.conn.execute(
                "UPDATE work_sessions SET active_seconds=active_seconds+? WHERE id=? AND ended_at IS NULL",
                (seconds, session_id),
            )
            self.conn.execute(
                "INSERT INTO time_entries(session_id,task,seconds,created_at) VALUES(?,?,?,?)",
                (session_id, task, seconds, utc_now()),
            )

    def end_session(self, session_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE work_sessions SET ended_at=? WHERE id=? AND ended_at IS NULL",
                (utc_now(), session_id),
            )

    def close(self) -> None:
        self.conn.close()
