"""Offscreen GUI integration smoke test for REPORTS and project switching."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from pinterest_os.storage import Storage
from pinterest_os.reports_page import ReportsPage


def test_reports_page_empty_and_project_switch(tmp_path):
    app = QApplication.instance() or QApplication([])
    first = Storage(tmp_path / "one.sqlite3")
    second = Storage(tmp_path / "two.sqlite3")
    try:
        page = ReportsPage(first)
        assert page.table.rowCount() == 0
        product = second.create("products", name="Guide")
        pin = second.create("pins", title="Pin", product_id=product)
        with second.conn:
            second.conn.execute(
                """INSERT INTO business_metrics
                   (date,pin_id,currency,site_visits,conversions,revenue_cents,reported_cost_cents)
                   VALUES(?,?,?,?,?,?,?)""",
                ("2026-11-01", pin, "USD", 100, 5, 5000, 1000))
        page.storage = second
        page.refresh()
        assert page.currency.currentData() == "USD"
        assert page.table.rowCount() == 1
        assert page.table.item(0, 1).text() == "Guide"
        assert page.table.item(0, 12).text() == ""
        page.close()
    finally:
        first.close()
        second.close()
