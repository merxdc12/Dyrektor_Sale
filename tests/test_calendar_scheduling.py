"""Offline calendar scheduling regression checks."""
from pathlib import Path

from pinterest_os.storage import Storage


def test_schedule_conflicts_and_status_summary(tmp_path: Path):
    db = Storage(tmp_path / "calendar.sqlite3")
    try:
        board = db.create("boards", name="IoT")
        other = db.create("boards", name="Homelab")
        a = db.create("pins", title="A", board_id=board)
        b = db.create("pins", title="B", board_id=board)
        c = db.create("pins", title="C", board_id=other)
        when = "2026-11-12T10:30"
        first = db.create_schedule(a, when)
        assert db.schedule_conflicts(when, board)[0]["pin_id"] == a
        assert db.schedule_conflicts(when, board, exclude_entry_id=first) == []
        assert db.schedule_conflicts(when, other) == []
        db.create_schedule(b, when, "READY")
        db.create_schedule(c, when, "CANCELLED")
        assert len(db.schedule_conflicts(when, board)) == 2
        assert db.calendar_summary("2026-11-12", "2026-11-12", board) == {
            "PLANNED": 1, "READY": 1, "PUBLISHED": 0, "CANCELLED": 0}
        assert db.calendar_summary("2026-11-12", "2026-11-12") == {
            "PLANNED": 1, "READY": 1, "PUBLISHED": 0, "CANCELLED": 1}
    finally:
        db.close()


def test_invalid_schedule_does_not_create_entry(tmp_path: Path):
    db = Storage(tmp_path / "calendar.sqlite3")
    try:
        pin = db.create("pins", title="Draft")
        try:
            db.create_schedule(pin, "2026-99-99T25:80")
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid datetime was accepted")
        assert db.schedules_between("2026-01-01", "2026-12-31") == []
    finally:
        db.close()
