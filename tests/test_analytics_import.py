"""Offline metrics import regression tests."""
import pytest
from pinterest_os.analytics_import import import_metrics, metric_history
from pinterest_os.storage import Storage

def test_import_upsert_and_history(tmp_path):
    db = Storage(tmp_path / "data.sqlite3")
    try:
        pin = db.create("pins", title="Test")
        csv = tmp_path / "metrics.csv"
        csv.write_text(f"date,pin_id,impressions,outbound_clicks,saves\n2026-11-01,{pin},100,5,3\n")
        assert import_metrics(db, csv) == 1
        assert import_metrics(db, csv) == 1
        assert metric_history(db) == [("2026-11-01", 100, 5, 3)]
        csv.write_text(f"date,pin_id,impressions,outbound_clicks,saves\n2026-11-01,{pin},200,8,6\n")
        import_metrics(db, csv)
        assert metric_history(db) == [("2026-11-01", 200, 8, 6)]
    finally:
        db.close()

def test_reject_unknown_pin_and_negative_values(tmp_path):
    db = Storage(tmp_path / "data.sqlite3")
    try:
        csv = tmp_path / "metrics.csv"
        csv.write_text("date,pin_id,impressions,outbound_clicks,saves\n2026-11-01,999,10,2,1\n")
        with pytest.raises(ValueError, match="Unknown local pin"):
            import_metrics(db, csv)
        csv.write_text("date,pin_id,impressions,outbound_clicks,saves\n2026-11-01,999,-1,2,1\n")
        with pytest.raises(ValueError, match="invalid date"):
            import_metrics(db, csv)
        assert metric_history(db) == []
    finally:
        db.close()
