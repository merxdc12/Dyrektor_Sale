"""Profit Intelligence phase 1: costs and labor."""
import pytest
from pinterest_os.profit_costs import (add_cost, cost_summary, labor_summary,
                                       money_cents, set_hourly_rate)
from pinterest_os.storage import Storage


def test_cost_ledger_and_labor(tmp_path):
    db = Storage(tmp_path / "costs.sqlite3")
    try:
        pin = db.create("pins", title="Pin")
        session = db.conn.execute(
            "INSERT INTO work_sessions(started_at) VALUES(?)", ("2026-11-01",)).lastrowid
        with db.conn:
            db.conn.execute(
                "INSERT INTO time_entries(session_id,task,pin_id,seconds,created_at) VALUES(?,?,?,?,?)",
                (session, "Design", pin, 5400, "2026-11-01"))
        assert labor_summary(db, "USD")["rate_configured"] is False
        set_hourly_rate(db, "USD", "10.00")
        assert labor_summary(db, "USD")["by_pin"][pin]["cost_cents"] == 1500
        add_cost(db, "2026-11-01", "USD", "DIRECT", "Printing", "3.25", pin)
        add_cost(db, "2026-11-01", "USD", "ALLOCATED", "Hosting", "2.00")
        costs = cost_summary(db, "USD")
        assert costs["direct_cents"] == 325
        assert costs["allocated_cents"] == 200
        assert costs["by_pin"][None]["ALLOCATED"] == 200
        assert cost_summary(db, "EUR")["direct_cents"] == 0
    finally:
        db.close()


def test_validation(tmp_path):
    db = Storage(tmp_path / "costs.sqlite3")
    try:
        for amount in ("-1", "1.001", "NaN", "Infinity"):
            with pytest.raises(ValueError):
                money_cents(amount)
        with pytest.raises(ValueError, match="Unknown pin"):
            add_cost(db, "2026-11-01", "USD", "DIRECT", "Cost", "2.00", 999)
        with pytest.raises(ValueError, match="description"):
            add_cost(db, "2026-11-01", "USD", "DIRECT", "", "2.00")
        assert cost_summary(db, "USD")["direct_cents"] == 0
    finally:
        db.close()
