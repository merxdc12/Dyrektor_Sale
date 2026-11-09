"""SQLite persistence with validated table/field operations."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, target_url TEXT NOT NULL DEFAULT '',
 category TEXT NOT NULL DEFAULT 'POD', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS boards (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pins (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', destination_url TEXT NOT NULL DEFAULT '',
 product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
 board_id INTEGER REFERENCES boards(id) ON DELETE SET NULL,
 status TEXT NOT NULL DEFAULT 'DRAFT'
 CHECK(status IN ('DRAFT','IN_REVIEW','READY','PUBLISHED')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_sessions (
 id INTEGER PRIMARY KEY, started_at TEXT NOT NULL,
 ended_at TEXT, active_seconds INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS time_entries (
 id INTEGER PRIMARY KEY,
 session_id INTEGER NOT NULL REFERENCES work_sessions(id),
 task TEXT NOT NULL, pin_id INTEGER REFERENCES pins(id),
 seconds INTEGER NOT NULL CHECK(seconds >= 0),
 created_at TEXT NOT NULL
);
"""
FIELDS = {
 "products": ("name", "target_url", "category"),
 "boards": ("name", "url", "description"),
 "pins": ("title", "description", "destination_url", "product_id", "board_id", "status"),
}
REQUIRED = {"products": "name", "boards": "name", "pins": "title"}
STATUSES = {"DRAFT", "IN_REVIEW", "READY", "PUBLISHED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        # Non-destructive upgrades of Phase 1 databases.
        for table, additions in {
            "products": {"category": "TEXT NOT NULL DEFAULT 'POD'"},
            "boards": {"description": "TEXT NOT NULL DEFAULT ''"},
            "pins": {"destination_url": "TEXT NOT NULL DEFAULT ''"},
        }.items():
            present = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            for field, sql_type in additions.items():
                if field not in present:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {field} {sql_type}")
        self.conn.commit()

    def _validate(self, table: str, values: dict) -> dict:
        if table not in FIELDS:
            raise ValueError("Unsupported table")
        if set(values) - set(FIELDS[table]):
            raise ValueError("Unsupported field")
        cleaned = {}
        for key, value in values.items():
            cleaned[key] = value.strip() if isinstance(value, str) else value
        field = REQUIRED[table]
        if field in cleaned and not cleaned[field]:
            raise ValueError(f"{field} is required")
        if table == "pins" and "status" in cleaned and cleaned["status"] not in STATUSES:
            raise ValueError("Invalid pin status")
        return cleaned

    def create(self, table: str, **values) -> int:
        values = self._validate(table, values)
        if not values.get(REQUIRED[table]):
            raise ValueError(f"{REQUIRED[table]} is required")
        columns = [*values, "created_at"]
        params = [*values.values(), utc_now()]
        sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
        with self.conn:
            cursor = self.conn.execute(sql, params)
        return int(cursor.lastrowid)

    def update(self, table: str, row_id: int, **values) -> bool:
        values = self._validate(table, values)
        if not values:
            return False
        sql = f"UPDATE {table} SET " + ", ".join(f"{field}=?" for field in values) + " WHERE id=?"
        with self.conn:
            cursor = self.conn.execute(sql, [*values.values(), row_id])
        return cursor.rowcount > 0

    def get(self, table: str, row_id: int) -> dict | None:
        if table not in FIELDS:
            raise ValueError("Unsupported table")
        self.conn.row_factory = sqlite3.Row
        try:
            row = self.conn.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
            return dict(row) if row else None
        finally:
            self.conn.row_factory = None

    def all(self, table: str) -> list[dict]:
        if table not in FIELDS:
            raise ValueError("Unsupported table")
        self.conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in self.conn.execute(f"SELECT * FROM {table} ORDER BY id DESC")]
        finally:
            self.conn.row_factory = None

    def add_board(self, name: str, url: str = "") -> int:
        return self.create("boards", name=name, url=url)

    def add_pin(self, title: str) -> int:
        return self.create("pins", title=title)

    def list_rows(self, table: str) -> list[tuple]:
        field = {"boards": "name", "pins": "title"}.get(table)
        if field is None:
            raise ValueError("Unsupported table")
        return [(row["id"], row[field]) for row in self.all(table)]

    def start_session(self) -> int:
        with self.conn:
            cursor = self.conn.execute("INSERT INTO work_sessions(started_at) VALUES(?)", (utc_now(),))
        return int(cursor.lastrowid)

    def save_elapsed(self, session_id: int, seconds: int, task: str = "General") -> None:
        if seconds <= 0:
            return
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE work_sessions SET active_seconds=active_seconds+? WHERE id=? AND ended_at IS NULL",
                (seconds, session_id),
            )
            if cursor.rowcount:
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
