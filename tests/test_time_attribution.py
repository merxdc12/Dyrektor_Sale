"""Time attribution preserves accounting and avoids retroactive reassignment."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtWidgets import QApplication
from pinterest_os.storage import Storage
from pinterest_os.time_page import TimePage


def test_pin_attribution_and_validation(tmp_path):
    db = Storage(tmp_path / "time.sqlite3")
    try:
        pin = db.create("pins", title="Test pin")
        session = db.start_session()
        db.save_elapsed(session, 10)
        db.save_elapsed(session, 20, "Design", pin)
        with pytest.raises(ValueError):
            db.save_elapsed(session, 5, "Design", 999999)
        rows = db.conn.execute(
            "SELECT task,pin_id,seconds FROM time_entries ORDER BY id").fetchall()
        assert rows == [("General", None, 10), ("Design", pin, 20)]
        assert db.conn.execute(
            "SELECT active_seconds FROM work_sessions WHERE id=?", (session,)
        ).fetchone()[0] == 30
    finally:
        db.close()


def test_time_page_apply_flushes_before_switch(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Storage(tmp_path / "gui.sqlite3")
    try:
        pin = db.create("pins", title="Design pin")
        events = []
        page = TimePage(db, on_change=lambda: events.append(
            (page.active_task, page.active_pin_id)))
        page.task.setText("Design")
        page.pin.setCurrentIndex(page.pin.findData(pin))
        page.apply_attribution()
        assert events == [("General", None)]
        assert (page.active_task, page.active_pin_id) == ("Design", pin)
        page.reset_attribution()
        assert (page.active_task, page.active_pin_id) == ("General", None)
        page.close()
    finally:
        db.close()
