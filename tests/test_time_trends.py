"""TIME 5 regression checks: aggregation and descriptive UI."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from pinterest_os.storage import Storage
from pinterest_os.time_trends import workload_trends
from pinterest_os.time_page import TimePage


def test_weekly_trends_and_bottlenecks(tmp_path):
    db = Storage(tmp_path / "trends.sqlite3")
    try:
        session = db.start_session()
        with db.conn:
            db.conn.executemany(
                "INSERT INTO time_entries(session_id,task,seconds,created_at) VALUES(?,?,?,?)",
                [(session, "Design", 3600, "2026-11-02T10:00:00+00:00"),
                 (session, "Research", 900, "2026-11-03T10:00:00+00:00"),
                 (session, "Design", 1800, "2026-11-09T10:00:00+00:00"),
                 (session, "Invalid", 60, "not-a-date")])
        result = workload_trends(db)
        assert [w["week"] for w in result["weeks"]] == ["2026-W45", "2026-W46"]
        assert [w["seconds"] for w in result["weeks"]] == [4500, 1800]
        assert result["tasks"][0]["task"] == "Design"
        assert result["tasks"][0]["seconds"] == 5400
        assert result["invalid_timestamps"] == 1
        assert result["tracked_seconds"] == 6300
    finally:
        db.close()


def test_time_trends_gui(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Storage(tmp_path / "ui.sqlite3")
    try:
        session = db.start_session()
        db.save_elapsed(session, 90, "Draft")
        page = TimePage(db)
        assert page.week_table.rowCount() == 1
        assert page.bottleneck_table.rowCount() == 1
        assert page.bottleneck_table.item(0, 0).text() == "Draft"
        assert "not proof" in page.trend_note.text()
        page.close()
    finally:
        db.close()
