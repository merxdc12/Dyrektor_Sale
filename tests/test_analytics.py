"""Local analytics must never invent Pinterest performance metrics."""
from pinterest_os.analytics import operational_summary
from pinterest_os.storage import Storage


def test_operational_counts(tmp_path):
    db = Storage(tmp_path / "analytics.sqlite3")
    try:
        board = db.create("boards", name="Electronics")
        first = db.create("pins", title="Draft")
        second = db.create("pins", title="Ready", board_id=board, status="READY")
        third = db.create("pins", title="Published", status="PUBLISHED")
        db.create_schedule(first, "2026-01-01T12:00", "PLANNED")
        db.create_schedule(third, "2026-01-01T12:00", "PUBLISHED")
        db.create_carousel("Guide")
        counts = operational_summary(db)
        assert counts["pins"] == 3
        assert counts["boards"] == 1
        assert counts["drafts"] == 1
        assert counts["ready"] == 1
        assert counts["published_local"] == 1
        assert counts["scheduled_pending"] == 1
        assert counts["confirmed_schedules"] == 1
        assert counts["carousels"] == 1
        assert "impressions" not in counts and "clicks" not in counts
    finally:
        db.close()
