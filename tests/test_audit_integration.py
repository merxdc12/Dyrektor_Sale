"""Regression coverage for audit findings: cost-only currency and incomplete overhead."""
from pinterest_os.storage import Storage
from pinterest_os.profit_costs import add_cost, set_hourly_rate
from pinterest_os.product_decisions import decision_report


def test_unassigned_overhead_blocks_scale(tmp_path):
    db = Storage(tmp_path / "audit.sqlite3")
    try:
        product = db.create("products", name="Book")
        pin = db.create("pins", title="Pin", product_id=product)
        with db.conn:
            db.conn.execute(
                "INSERT INTO business_metrics(date,pin_id,currency,site_visits,conversions,revenue_cents,reported_cost_cents) VALUES(?,?,?,?,?,?,?)",
                ("2026-11-01", pin, "USD", 200, 10, 10000, 1000))
        set_hourly_rate(db, "USD", "10.00")
        assert decision_report(db)[0]["decision"] == "SCALE"
        add_cost(db, "2026-11-01", "USD", "ALLOCATED", "Unassigned hosting", "2.00")
        report = decision_report(db)
        product_row = next(row for row in report if row["product_id"] == product)
        assert product_row["decision"] == "TEST"
        assert product_row["evidence"] == "INCOMPLETE"
    finally:
        db.close()


def test_cost_only_currency_is_queryable(tmp_path):
    db = Storage(tmp_path / "audit.sqlite3")
    try:
        add_cost(db, "2026-11-01", "EUR", "DIRECT", "Supplies", "3.00")
        currencies = [row[0] for row in db.conn.execute(
            """SELECT currency FROM business_metrics UNION SELECT currency FROM cost_entries
               UNION SELECT currency FROM labor_rates ORDER BY currency""")]
        assert currencies == ["EUR"]
    finally:
        db.close()
