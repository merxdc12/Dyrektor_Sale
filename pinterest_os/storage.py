"""SQLite persistence with validated table/field operations."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS pin_designs (
 pin_id INTEGER PRIMARY KEY REFERENCES pins(id) ON DELETE CASCADE,
 project_json TEXT NOT NULL,
 png_path TEXT NOT NULL DEFAULT '',
 canva_design_id TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, target_url TEXT NOT NULL DEFAULT '',
 category TEXT NOT NULL DEFAULT 'POD', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS boards (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL DEFAULT '',
 description TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Other', created_at TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS carousels (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS carousel_slides (
 carousel_id INTEGER NOT NULL REFERENCES carousels(id) ON DELETE CASCADE,
 pin_id INTEGER NOT NULL REFERENCES pins(id) ON DELETE CASCADE,
 position INTEGER NOT NULL,
 PRIMARY KEY(carousel_id,pin_id), UNIQUE(carousel_id,position)
);
CREATE TABLE IF NOT EXISTS pinterest_metrics (
 date TEXT NOT NULL,
 pin_id INTEGER NOT NULL REFERENCES pins(id) ON DELETE CASCADE,
 impressions INTEGER NOT NULL CHECK(impressions >= 0),
 outbound_clicks INTEGER NOT NULL CHECK(outbound_clicks >= 0),
 saves INTEGER NOT NULL CHECK(saves >= 0),
 PRIMARY KEY(date,pin_id)
);
CREATE TABLE IF NOT EXISTS business_metrics (
 date TEXT NOT NULL,
 pin_id INTEGER NOT NULL REFERENCES pins(id) ON DELETE CASCADE,
 currency TEXT NOT NULL CHECK(length(currency)=3),
 site_visits INTEGER NOT NULL CHECK(site_visits>=0),
 conversions INTEGER NOT NULL CHECK(conversions>=0),
 revenue_cents INTEGER NOT NULL CHECK(revenue_cents>=0),
 reported_cost_cents INTEGER NOT NULL CHECK(reported_cost_cents>=0),
 PRIMARY KEY(date,pin_id,currency)
);
CREATE TABLE IF NOT EXISTS cost_entries (
 id INTEGER PRIMARY KEY,
 date TEXT NOT NULL,
 pin_id INTEGER REFERENCES pins(id) ON DELETE SET NULL,
 currency TEXT NOT NULL CHECK(length(currency)=3),
 category TEXT NOT NULL CHECK(category IN ('DIRECT','ALLOCATED')),
 description TEXT NOT NULL,
 amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS labor_rates (
 currency TEXT PRIMARY KEY CHECK(length(currency)=3),
 hourly_cents INTEGER NOT NULL CHECK(hourly_cents>=0),
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_sessions (
 id INTEGER PRIMARY KEY, started_at TEXT NOT NULL,
 ended_at TEXT, active_seconds INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pin_schedule (
 id INTEGER PRIMARY KEY,
 pin_id INTEGER NOT NULL REFERENCES pins(id) ON DELETE CASCADE,
 scheduled_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'PLANNED'
 CHECK(status IN ('PLANNED','READY','PUBLISHED','CANCELLED')),
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pin_schedule_date ON pin_schedule(scheduled_at);
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
 "boards": ("name", "url", "description", "category"),
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
            "boards": {"description": "TEXT NOT NULL DEFAULT ''",
                       "category": "TEXT NOT NULL DEFAULT 'Other'"},
            "pins": {"destination_url": "TEXT NOT NULL DEFAULT ''"},
        }.items():
            present = {row[1] for row in self.conn.execute(f"PRAGMA table_info({table})")}
            for field, sql_type in additions.items():
                if field not in present:
                    self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {field} {sql_type}")
        present = {row[1] for row in self.conn.execute("PRAGMA table_info(pin_designs)")}
        if "canva_design_id" not in present:
            self.conn.execute("ALTER TABLE pin_designs ADD COLUMN canva_design_id TEXT NOT NULL DEFAULT ''")
        self.conn.commit()

    def set_canva_design_id(self, pin_id: int, design_id: str) -> None:
        from .canva_bridge import validate_canva_design_id
        validate_canva_design_id(design_id)
        if not self.get("pins", pin_id):
            raise ValueError("Pin does not exist")
        with self.conn:
            self.conn.execute(
                """INSERT INTO pin_designs(pin_id,project_json,canva_design_id,updated_at)
                   VALUES(?,?,?,?)
                   ON CONFLICT(pin_id) DO UPDATE SET
                   canva_design_id=excluded.canva_design_id,
                   updated_at=excluded.updated_at""",
                (pin_id, '{"version":1}', design_id, utc_now()),
            )

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
        if table == "boards":
            from .board_logic import CATEGORIES
            if "category" in cleaned and cleaned["category"] not in CATEGORIES:
                raise ValueError("Invalid board category")
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

    def search_products(self, query: str = "", category: str = "ALL") -> list[dict]:
        if category not in {"ALL", "POD", "KDP", "DIGITAL", "FREE_TOOL", "OTHER"}:
            raise ValueError("Invalid product category filter")
        query = query.strip().casefold()
        return [
            row for row in self.all("products")
            if (category == "ALL" or row["category"] == category)
            and (not query or any(query in str(row[key]).casefold()
                                  for key in ("name", "category", "target_url")))
        ]

    def search_boards(self, query: str = "") -> list[dict]:
        needle = query.strip().casefold()
        return [
            row for row in self.all("boards")
            if not needle or any(needle in str(row.get(field) or "").casefold()
                                 for field in ("name", "description", "url"))
        ]

    def board_pin_count(self, board_id: int) -> int:
        return int(self.conn.execute(
            "SELECT COUNT(*) FROM pins WHERE board_id=?", (board_id,)
        ).fetchone()[0])

    def board_pin_counts(self) -> dict[int, int]:
        return {int(board_id): int(count) for board_id, count in
                self.conn.execute("SELECT board_id, COUNT(*) FROM pins "
                                  "WHERE board_id IS NOT NULL GROUP BY board_id")}

    def delete_board(self, board_id: int) -> bool:
        """Delete the board; associated pins survive with NULL board_id."""
        with self.conn:
            result = self.conn.execute("DELETE FROM boards WHERE id=?", (board_id,))
        return result.rowcount > 0

    def search_pins(self, query: str = "", status: str = "ALL") -> list[dict]:
        if status not in {"ALL", *STATUSES}:
            raise ValueError("Invalid pin status filter")
        needle = query.strip().casefold()
        return [
            row for row in self.all("pins")
            if (status == "ALL" or row["status"] == status)
            and (not needle or any(needle in str(row.get(key) or "").casefold()
                                   for key in ("title", "description", "destination_url")))
        ]

    def duplicate_pin(self, pin_id: int) -> int:
        """Copy metadata into a DRAFT; never copy published status or schedule."""
        original = self.get("pins", pin_id)
        if original is None:
            raise ValueError("Pin not found")
        return self.create(
            "pins", title=original["title"] + " (copy)",
            description=original["description"],
            destination_url=original["destination_url"],
            product_id=original["product_id"], board_id=original["board_id"],
            status="DRAFT")

    def delete_pin(self, pin_id: int) -> bool:
        """Delete one pin and its linked design/calendar rows via foreign keys."""
        with self.conn:
            result = self.conn.execute("DELETE FROM pins WHERE id=?", (pin_id,))
        return result.rowcount > 0

    def product_pin_count(self, product_id: int) -> int:
        return int(self.conn.execute(
            "SELECT COUNT(*) FROM pins WHERE product_id=?", (product_id,)
        ).fetchone()[0])

    def delete_product(self, product_id: int) -> bool:
        """Remove product only; linked pins survive with NULL product_id."""
        with self.conn:
            result = self.conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        return result.rowcount > 0

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


    def _validate_schedule(self, pin_id: int, scheduled_at: str, status: str) -> None:
        from datetime import datetime
        if status not in {"PLANNED", "READY", "PUBLISHED", "CANCELLED"}:
            raise ValueError("Invalid schedule status")
        try:
            datetime.strptime(scheduled_at, "%Y-%m-%dT%H:%M")
        except ValueError as exc:
            raise ValueError("Date/time must use YYYY-MM-DDTHH:MM") from exc
        if not self.get("pins", pin_id):
            raise ValueError("Pin does not exist")

    def schedule_conflicts(self, scheduled_at: str, board_id: int | None,
                           exclude_entry_id: int | None = None) -> list[dict]:
        """Same board and minute; advisory only, including unassigned pins."""
        self.conn.row_factory = sqlite3.Row
        try:
            rows = self.conn.execute(
                """SELECT s.id, s.pin_id, p.title, s.status
                   FROM pin_schedule AS s JOIN pins AS p ON p.id=s.pin_id
                   WHERE s.scheduled_at=? AND p.board_id IS ?
                     AND s.status!='CANCELLED' AND s.id!=?
                   ORDER BY s.id""",
                (scheduled_at, board_id, exclude_entry_id if exclude_entry_id is not None else -1)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            self.conn.row_factory = None

    def calendar_summary(self, start: str, end: str, board_id: int | None = None) -> dict[str, int]:
        rows = self.schedules_between(start, end, board_id)
        summary = {state: 0 for state in ("PLANNED", "READY", "PUBLISHED", "CANCELLED")}
        for row in rows:
            summary[row["status"]] += 1
        return summary

    def create_schedule(self, pin_id: int, scheduled_at: str, status: str = "PLANNED") -> int:
        self._validate_schedule(pin_id, scheduled_at, status)
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO pin_schedule(pin_id,scheduled_at,status,created_at) VALUES(?,?,?,?)",
                (pin_id, scheduled_at, status, utc_now()),
            )
        return int(cursor.lastrowid)

    def update_schedule(self, entry_id: int, pin_id: int, scheduled_at: str, status: str) -> bool:
        self._validate_schedule(pin_id, scheduled_at, status)
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE pin_schedule SET pin_id=?,scheduled_at=?,status=? WHERE id=?",
                (pin_id, scheduled_at, status, entry_id),
            )
        return cursor.rowcount > 0

    def create_carousel(self, title: str) -> int:
        if not title.strip():
            raise ValueError("Carousel title is required")
        with self.conn:
            row = self.conn.execute("INSERT INTO carousels(title,created_at) VALUES(?,?)",
                                    (title.strip(), utc_now()))
        return int(row.lastrowid)

    def list_carousels(self) -> list[dict]:
        self.conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in self.conn.execute(
                "SELECT * FROM carousels ORDER BY id DESC")]
        finally:
            self.conn.row_factory = None

    def carousel_slides(self, carousel_id: int) -> list[dict]:
        self.conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in self.conn.execute(
                """SELECT cs.pin_id, cs.position, p.title, d.png_path
                   FROM carousel_slides cs JOIN pins p ON p.id=cs.pin_id
                   LEFT JOIN pin_designs d ON d.pin_id=p.id
                   WHERE cs.carousel_id=? ORDER BY cs.position""", (carousel_id,))]
        finally:
            self.conn.row_factory = None

    def set_carousel_slides(self, carousel_id: int, pin_ids: list[int]) -> None:
        if len(pin_ids) != len(set(pin_ids)):
            raise ValueError("Duplicate pin in carousel")
        if len(pin_ids) > 10:
            raise ValueError("Carousel limit is 10 slides")
        with self.conn:
            if not self.conn.execute("SELECT 1 FROM carousels WHERE id=?", (carousel_id,)).fetchone():
                raise ValueError("Carousel does not exist")
            for pin_id in pin_ids:
                if not self.conn.execute("SELECT 1 FROM pins WHERE id=?", (pin_id,)).fetchone():
                    raise ValueError(f"Pin {pin_id} does not exist")
            self.conn.execute("DELETE FROM carousel_slides WHERE carousel_id=?", (carousel_id,))
            self.conn.executemany(
                "INSERT INTO carousel_slides(carousel_id,pin_id,position) VALUES(?,?,?)",
                [(carousel_id, pin_id, i) for i, pin_id in enumerate(pin_ids, 1)])

    def confirm_manual_publication(self, entry_id: int) -> None:
        """Atomically mark a schedule and pin published, refusing repeated confirmation."""
        with self.conn:
            row = self.conn.execute(
                """SELECT s.pin_id, s.status, p.status
                   FROM pin_schedule s JOIN pins p ON p.id=s.pin_id
                   WHERE s.id=?""", (entry_id,)).fetchone()
            if row is None:
                raise ValueError("Calendar entry no longer exists")
            pin_id, schedule_status, pin_status = row
            if schedule_status not in ("PLANNED", "READY"):
                raise ValueError("Schedule already completed or cancelled")
            if pin_status == "PUBLISHED":
                raise ValueError("Pin already marked as published")
            result = self.conn.execute(
                """UPDATE pin_schedule SET status='PUBLISHED'
                   WHERE id=? AND status IN ('PLANNED','READY')""", (entry_id,))
            if result.rowcount != 1:
                raise ValueError("Schedule status changed")
            result = self.conn.execute(
                """UPDATE pins SET status='PUBLISHED'
                   WHERE id=? AND status!='PUBLISHED'""", (pin_id,))
            if result.rowcount != 1:
                raise ValueError("Pin status changed")
            # Any other pending schedule for this same pin must not remain in the queue.
            self.conn.execute(
                """UPDATE pin_schedule SET status='CANCELLED'
                   WHERE pin_id=? AND id!=? AND status IN ('PLANNED','READY')""",
                (pin_id, entry_id))

    def get_schedule(self, entry_id: int) -> dict | None:
        self.conn.row_factory = sqlite3.Row
        try:
            row = self.conn.execute("SELECT * FROM pin_schedule WHERE id=?", (entry_id,)).fetchone()
            return dict(row) if row else None
        finally:
            self.conn.row_factory = None

    def schedules_for_day(self, day: str) -> list[dict]:
        from datetime import date
        date.fromisoformat(day)
        self.conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in self.conn.execute(
                """SELECT s.*,p.title FROM pin_schedule s JOIN pins p ON p.id=s.pin_id
                   WHERE s.scheduled_at >= ? AND s.scheduled_at < ?
                   ORDER BY s.scheduled_at,s.id""",
                (day, day + "T99:99"),
            )]
        finally:
            self.conn.row_factory = None


    def schedules_between(self, start: str, end: str, board_id: int | None = None) -> list[dict]:
        """Inclusive ISO calendar-day range; board filter uses linked pin's board."""
        from datetime import date
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("Start date must not exceed end date")
        params = [start, end + "T23:59"]
        where = "s.scheduled_at BETWEEN ? AND ?"
        if board_id is not None:
            where += " AND p.board_id=?"
            params.append(board_id)
        self.conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in self.conn.execute(
                f"""SELECT s.*, p.title, p.board_id, b.name AS board_name
                    FROM pin_schedule s
                    JOIN pins p ON p.id=s.pin_id
                    LEFT JOIN boards b ON b.id=p.board_id
                    WHERE {where}
                    ORDER BY s.scheduled_at, s.id""", params
            )]
        finally:
            self.conn.row_factory = None

    def delete_schedule(self, entry_id: int) -> bool:
        with self.conn:
            cursor = self.conn.execute("DELETE FROM pin_schedule WHERE id=?", (entry_id,))
        return cursor.rowcount > 0

    def save_pin_design(self, pin_id: int, project_json: str, png_path: str | None = None) -> None:
        if not self.get("pins", pin_id):
            raise ValueError("Pin does not exist")
        import json
        data = json.loads(project_json)
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("Unsupported design project")
        with self.conn:
            self.conn.execute(
                """INSERT INTO pin_designs(pin_id,project_json,png_path,updated_at)
                   VALUES(?,?,COALESCE(?,''),?)
                   ON CONFLICT(pin_id) DO UPDATE SET
                   project_json=excluded.project_json,
                   png_path=COALESCE(?,pin_designs.png_path),
                   updated_at=excluded.updated_at""",
                (pin_id, project_json, png_path, utc_now(), png_path),
            )

    def get_pin_design(self, pin_id: int) -> dict | None:
        self.conn.row_factory = sqlite3.Row
        try:
            row = self.conn.execute("SELECT * FROM pin_designs WHERE pin_id=?", (pin_id,)).fetchone()
            return dict(row) if row else None
        finally:
            self.conn.row_factory = None

    def close(self) -> None:
        self.conn.close()
