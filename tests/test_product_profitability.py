"""Product contribution is explicit, currency-separated, and guarded."""
from pinterest_os.storage import Storage
from pinterest_os.profit_costs import add_cost, set_hourly_rate
from pinterest_os.product_profitability import product_profitability


def test_product_contribution_and_roi(tmp_path):
    db = Storage(tmp_path / "db.sqlite3")
    try:
        product = db.create("products", name="Digital toolkit")
        pin = db.create("pins", title="Pin", product_id=product)
        with db.conn:
            db.conn.execute(
                "INSERT INTO business_metrics(date,pin_id,currency,site_visits,conversions,revenue_cents,reported_cost_cents) VALUES(?,?,?,?,?,?,?)",
                ("2026-11-01", pin, "USD", 100, 4, 10000, 1000))
            session = db.conn.execute(
                "INSERT INTO work_sessions(started_at) VALUES(?)", ("2026-11-01",)).lastrowid
            db.conn.execute(
                "INSERT INTO time_entries(session_id,task,pin_id,seconds,created_at) VALUES(?,?,?,?,?)",
                (session, "Design", pin, 3600, "2026-11-01"))
        add_cost(db, "2026-11-01", "USD", "DIRECT", "Design assets", "20.00", pin)
        first = product_profitability(db, "USD")[0]
        assert first["estimated_contribution_cents"] is None
        assert first["roi_percent"] is None
        set_hourly_rate(db, "USD", "10.00")
        result = product_profitability(db, "USD")[0]
        assert result["known_cost_cents"] == 3000
        assert result["labor_cents"] == 1000
        assert result["estimated_contribution_cents"] == 6000
        assert result["roi_percent"] == 150.0
        assert product_profitability(db, "EUR") == []
    finally:
        db.close()


def test_unassigned_cost_not_hidden(tmp_path):
    db = Storage(tmp_path / "db.sqlite3")
    try:
        set_hourly_rate(db, "USD", "0")
        add_cost(db, "2026-11-01", "USD", "ALLOCATED", "Unassigned hosting", "3.00")
        rows = product_profitability(db, "USD")
        assert len(rows) == 1
        assert rows[0]["product_name"] == "Unassigned"
        assert rows[0]["estimated_contribution_cents"] == -300
        assert rows[0]["roi_percent"] == -100.0
    finally:
        db.close()
