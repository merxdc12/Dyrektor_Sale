"""Time accounting must reuse existing session records without double-counting."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from pinterest_os.storage import Storage
from pinterest_os.time_page import TimePage, time_summary, duration


def test_time_summary_existing_sessions(tmp_path):
    db = Storage(tmp_path / "time.sqlite3")
    try:
        session = db.start_session()
        db.save_elapsed(session, 90)
        db.save_elapsed(session, 30, "Design")
        db.end_session(session)
        result = time_summary(db)
        assert result["sessions"] == 1
        assert result["total_seconds"] == 120
        assert result["tracked_seconds"] == 120
        assert result["unattributed_seconds"] == 0
        assert dict((task, seconds) for task, seconds, _ in result["tasks"]) == {
            "General": 90, "Design": 30}
        assert duration(3661) == "01:01:01"
    finally:
        db.close()


def test_time_page_project_switch(tmp_path):
    app = QApplication.instance() or QApplication([])
    first = Storage(tmp_path / "first.sqlite3")
    second = Storage(tmp_path / "second.sqlite3")
    try:
        page = TimePage(first)
        assert "Sessions: 0" in page.summary.text()
        session = second.start_session()
        second.save_elapsed(session, 60)
        page.storage = second
        page.refresh()
        page.set_current(60)
        assert "Sessions: 1" in page.summary.text()
        assert "00:01:00" in page.current.text()
        assert page.table.rowCount() == 1
        page.close()
    finally:
        first.close()
        second.close()
