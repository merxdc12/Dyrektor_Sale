"""No silent financial deduplication and no scale with unresolved overlap."""
import sqlite3
import pytest
from pinterest_os.storage import Storage
from pinterest_os.profit_costs import add_cost, set_hourly_rate
from pinterest_os.financial_integrity import reconciliation_flags
from pinterest_os.product_profitability import product_profitability
from pinterest_os.product_decisions import decision_report


def test_overlap_blocks_roi_and_scale(tmp_path):
    db = Storage(tmp_path / "financial.sqlite3")
    try:
        product = db.create("products", name="Guide")
        pin = db.create("pins", title="Guide pin", product_id=product)
        with db.conn:
            db.conn.execute(
                """INSERT INTO business_metrics
                   (date,pin_id,currency,site_visits,conversions,revenue_cents,reported_cost_cents)
                   VALUES(?,?,?,?,?,?,?)""",
                ("2026-11-01", pin, "USD", 200, 10, 10000, 1500))
        set_hourly_rate(db, "USD", "10.00")
        assert decision_report(db)[0]["decision"] == "SCALE"
        add_cost(db, "2026-11-01", "USD", "DIRECT", "Possibly same expense", "15.00", pin, "invoice-1")
        assert len(reconciliation_flags(db, "USD")) == 1
        row = product_profitability(db, "USD")[0]
        assert row["reconciliation_required"]
        assert row["estimated_contribution_cents"] is None
        assert row["roi_percent"] is None
        assert decision_report(db)[0]["decision"] == "TEST"
        with pytest.raises(sqlite3.IntegrityError):
            add_cost(db, "2026-11-02", "USD", "DIRECT", "Repeated invoice", "15.00", pin, "invoice-1")
        assert len(reconciliation_flags(db, "USD")) == 1
    finally:
        db.close()


def test_additive_schema_upgrade(tmp_path):
    path = tmp_path / "old.sqlite3"
    db = Storage(path)
    try:
        with db.conn:
            db.conn.execute("DROP INDEX IF EXISTS ux_cost_source_ref")
            db.conn.execute("ALTER TABLE cost_entries RENAME TO cost_entries_previous")
            db.conn.execute("""CREATE TABLE cost_entries (
                id INTEGER PRIMARY KEY, date TEXT NOT NULL, pin_id INTEGER,
                currency TEXT NOT NULL, category TEXT NOT NULL,
                description TEXT NOT NULL, amount_cents INTEGER NOT NULL,
                created_at TEXT NOT NULL)""")
            db.conn.execute("DROP TABLE cost_entries_previous")
    finally:
        db.close()
    upgraded = Storage(path)
    try:
        fields = [row[1] for row in upgraded.conn.execute("PRAGMA table_info(cost_entries)")]
        assert "source_ref" in fields
    finally:
        upgraded.close()
