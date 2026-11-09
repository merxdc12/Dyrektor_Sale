"""Product attribution is frozen when time is recorded, not inferred later."""
import sqlite3
from pinterest_os.storage import Storage
from pinterest_os.time_page import product_time_summary


def test_product_transfer_preserves_historical_time(tmp_path):
    db = Storage(tmp_path / "history.sqlite3")
    try:
        first = db.create("products", name="Original")
        second = db.create("products", name="Replacement")
        pin = db.create("pins", title="Pin", product_id=first)
        session = db.start_session()
        db.save_elapsed(session, 120, "Draft", pin)
        db.update("pins", pin, product_id=second)
        db.save_elapsed(session, 60, "Revision", pin)
        rows = product_time_summary(db)
        assert {(row["product_id"], row["seconds"]) for row in rows} == {
            (first, 120), (second, 60)}
        assert {row["product_name"] for row in rows} == {"Original", "Replacement"}
    finally:
        db.close()


def test_legacy_entries_not_assigned_using_current_pin(tmp_path):
    db = Storage(tmp_path / "legacy.sqlite3")
    try:
        product = db.create("products", name="Current product")
        pin = db.create("pins", title="Pin", product_id=product)
        session = db.start_session()
        with db.conn:
            db.conn.execute(
                "INSERT INTO time_entries(session_id,task,pin_id,seconds,created_at) "
                "VALUES(?,?,?,?,?)", (session, "Old", pin, 90, "2026-01-01"))
        db.save_elapsed(session, 30, "New", pin)
        rows = product_time_summary(db)
        unknown = next(row for row in rows if not row["attribution_known"])
        assert unknown["seconds"] == 90
        assert "Unknown" in unknown["product_name"]
        known = next(row for row in rows if row["attribution_known"])
        assert known["product_id"] == product
        assert known["seconds"] == 30
    finally:
        db.close()


def test_snapshot_migration_preserves_existing_rows(tmp_path):
    path = tmp_path / "upgrade.sqlite3"
    db = Storage(path)
    try:
        session = db.start_session()
        with db.conn:
            db.conn.execute(
                "INSERT INTO time_entries(session_id,task,seconds,created_at) "
                "VALUES(?,?,?,?)", (session, "Legacy", 45, "2026-01-01"))
            # Simulate a database with the original time_entries schema.
            db.conn.execute("ALTER TABLE time_entries RENAME TO time_entries_new")
            db.conn.execute(
                "CREATE TABLE time_entries (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, "
                "task TEXT NOT NULL, pin_id INTEGER, seconds INTEGER NOT NULL, created_at TEXT NOT NULL)")
            db.conn.execute(
                "INSERT INTO time_entries(id,session_id,task,pin_id,seconds,created_at) "
                "SELECT id,session_id,task,pin_id,seconds,created_at FROM time_entries_new")
            db.conn.execute("DROP TABLE time_entries_new")
    finally:
        db.close()
    upgraded = Storage(path)
    try:
        rows = product_time_summary(upgraded)
        assert len(rows) == 1
        assert rows[0]["seconds"] == 45
        assert rows[0]["attribution_known"] is False
    finally:
        upgraded.close()
