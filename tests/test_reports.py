"""Reports export is explicit, local and conservatively labeled."""
import csv
import pytest
from pinterest_os.storage import Storage
from pinterest_os.profit_costs import set_hourly_rate
from pinterest_os.reports import report_rows, export_report, FIELDS


def test_report_export_and_no_overwrite(tmp_path):
    db = Storage(tmp_path / "reports.sqlite3")
    try:
        product = db.create("products", name="Digital guide")
        pin = db.create("pins", title="Guide", product_id=product)
        with db.conn:
            db.conn.execute(
                """INSERT INTO business_metrics
                   (date,pin_id,currency,site_visits,conversions,revenue_cents,reported_cost_cents)
                   VALUES(?,?,?,?,?,?,?)""",
                ("2026-11-01", pin, "USD", 150, 6, 10000, 2500))
        rows = report_rows(db, "USD")
        assert len(rows) == 1
        assert rows[0]["estimated_contribution"] == ""
        assert rows[0]["decision"] == "TEST"
        set_hourly_rate(db, "USD", "10.00")
        assert report_rows(db, "USD")[0]["estimated_contribution"] == "75.00"
        target = tmp_path / "report.csv"
        assert export_report(db, target, "USD") == 1
        with target.open(encoding="utf-8-sig", newline="") as handle:
            parsed = list(csv.DictReader(handle))
        assert tuple(parsed[0]) == FIELDS
        assert parsed[0]["estimated_contribution"] == "75.00"
        with pytest.raises(FileExistsError):
            export_report(db, target, "USD")
    finally:
        db.close()


def test_empty_report(tmp_path):
    db = Storage(tmp_path / "empty.sqlite3")
    try:
        assert report_rows(db, "USD") == []
        assert export_report(db, tmp_path / "empty.csv") == 0
    finally:
        db.close()
