"""Business analytics must preserve currency and avoid inferred profit."""
import pytest
from pinterest_os.business_metrics import import_business_metrics, business_summary
from pinterest_os.storage import Storage


def test_import_and_contribution(tmp_path):
    db = Storage(tmp_path / "db.sqlite3")
    try:
        pin = db.create("pins", title="Guide")
        path = tmp_path / "business.csv"
        path.write_text("date,pin_id,currency,site_visits,conversions,revenue,cost\n"
                        f"2026-11-01,{pin},USD,100,4,25.50,9.25\n"
                        f"2026-11-01,{pin},EUR,10,1,5.00,1.00\n")
        assert import_business_metrics(db, path) == 2
        assert import_business_metrics(db, path) == 2
        usd = business_summary(db, "USD")[0]
        assert usd["contribution_cents"] == 1625
        assert usd["conversion_rate"] == 4.0
        assert business_summary(db, "EUR")[0]["contribution_cents"] == 400
    finally:
        db.close()


def test_reject_invalid_and_preserve_existing_data(tmp_path):
    db = Storage(tmp_path / "db.sqlite3")
    try:
        pin = db.create("pins", title="Guide")
        path = tmp_path / "business.csv"
        path.write_text("date,pin_id,currency,site_visits,conversions,revenue,cost\n"
                        f"2026-11-01,{pin},USD,5,1,1.00,0.50\n"
                        f"2026-11-02,{pin},USD,5,1,1.001,0.50\n")
        with pytest.raises(ValueError, match="invalid value"):
            import_business_metrics(db, path)
        assert business_summary(db) == []
        path.write_text("date,pin_id,currency,site_visits,conversions,revenue,cost\n"
                        "2026-11-01,999,USD,5,1,1.00,0.50\n")
        with pytest.raises(ValueError, match="Unknown local pin"):
            import_business_metrics(db, path)
    finally:
        db.close()
