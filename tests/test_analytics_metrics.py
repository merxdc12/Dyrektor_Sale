"""Imported metrics, outbound CTR and pin filtering."""
from pinterest_os.analytics_metrics import ctr, daily_performance, pin_performance
from pinterest_os.storage import Storage

def test_ctr():
    assert ctr(5, 100) == 5.0
    assert ctr(0, 0) is None

def test_pin_performance_and_daily_filter(tmp_path):
    db = Storage(tmp_path / "metrics.sqlite3")
    try:
        first = db.create("pins", title="First")
        second = db.create("pins", title="Second")
        with db.conn:
            db.conn.executemany("INSERT INTO pinterest_metrics(date,pin_id,impressions,outbound_clicks,saves) VALUES(?,?,?,?,?)", [
                ("2026-11-01", first, 100, 5, 2),
                ("2026-11-02", first, 100, 10, 3),
                ("2026-11-01", second, 50, 2, 1),
            ])
        ranking = pin_performance(db)
        assert ranking[0]["pin_id"] == first
        assert ranking[0]["ctr"] == 7.5
        assert daily_performance(db, first) == [("2026-11-01", 100, 5, 2), ("2026-11-02", 100, 10, 3)]
        assert daily_performance(db)[0] == ("2026-11-01", 150, 7, 3)
    finally:
        db.close()
