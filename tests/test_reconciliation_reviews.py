"""Explicit reviews change cost treatment; source edits invalidate approval."""
from pinterest_os.storage import Storage
from pinterest_os.profit_costs import add_cost, set_hourly_rate
from pinterest_os.financial_integrity import reconciliation_flags, record_review
from pinterest_os.product_profitability import product_profitability
from pinterest_os.product_decisions import decision_report


def setup_db(tmp_path):
    db = Storage(tmp_path / "reconcile.sqlite3")
    product = db.create("products", name="Guide")
    pin = db.create("pins", title="Guide pin", product_id=product)
    with db.conn:
        db.conn.execute(
            """INSERT INTO business_metrics
               (date,pin_id,currency,site_visits,conversions,revenue_cents,reported_cost_cents)
               VALUES(?,?,?,?,?,?,?)""",
            ("2026-11-01", pin, "USD", 200, 10, 10000, 1500))
    set_hourly_rate(db, "USD", "0")
    add_cost(db, "2026-11-01", "USD", "DIRECT", "Invoice", "15.00", pin)
    return db, pin


def test_duplicate_review_and_invalidation(tmp_path):
    db, pin = setup_db(tmp_path)
    try:
        assert product_profitability(db, "USD")[0]["roi_percent"] is None
        record_review(db, "USD", "2026-11-01", pin, "DUPLICATE", "Same invoice verified")
        row = product_profitability(db, "USD")[0]
        assert row["reconciled_duplicate_cents"] == 1500
        assert row["known_cost_cents"] == 1500
        assert row["estimated_contribution_cents"] == 8500
        assert decision_report(db)[0]["decision"] == "SCALE"
        add_cost(db, "2026-11-01", "USD", "DIRECT", "New expense", "1.00", pin)
        assert reconciliation_flags(db, "USD")[0]["decision"] is None
        assert decision_report(db)[0]["decision"] == "TEST"
    finally:
        db.close()


def test_distinct_review_counts_both(tmp_path):
    db, pin = setup_db(tmp_path)
    try:
        record_review(db, "USD", "2026-11-01", pin, "DISTINCT", "Two independent invoices")
        row = product_profitability(db, "USD")[0]
        assert row["reconciled_duplicate_cents"] == 0
        assert row["known_cost_cents"] == 3000
        assert row["estimated_contribution_cents"] == 7000
    finally:
        db.close()
