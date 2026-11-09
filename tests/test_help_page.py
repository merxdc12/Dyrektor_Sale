"""Help content and read-only diagnostic smoke tests."""
from pinterest_os.help_page import GUIDES, LESSONS, diagnostics
from pinterest_os.storage import Storage


def test_help_covers_every_main_tab():
    expected = {"FILE", "PIN", "BOARD", "CALENDAR", "PUBLISHING",
                "ANALYTICS", "REPORTS", "TIME", "SETTINGS", "HELP"}
    assert set(GUIDES) == expected
    assert len(LESSONS) >= 5


def test_diagnostics_read_only(tmp_path):
    db = Storage(tmp_path / "help.sqlite3")
    try:
        before = db.conn.total_changes
        result = diagnostics(db)
        assert "SQLite quick_check: ok" in result
        assert "Foreign key violations: 0" in result
        assert "pins:" in result
        assert db.conn.total_changes == before
    finally:
        db.close()
