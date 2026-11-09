"""Product time is grouped once, with unassigned work kept visible."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from pinterest_os.storage import Storage
from pinterest_os.profit_costs import set_hourly_rate
from pinterest_os.time_page import TimePage, product_time_summary


def test_product_time_and_rate(tmp_path):
    db = Storage(tmp_path / "product_time.sqlite3")
    try:
        product = db.create("products", name="Guide")
        pin = db.create("pins", title="Pin A", product_id=product)
        session = db.start_session()
        db.save_elapsed(session, 3600, "Design", pin)
        db.save_elapsed(session, 1800, "Research")
        rows = product_time_summary(db)
        assert sum(row["seconds"] for row in rows) == 5400
        assigned = next(row for row in rows if row["product_id"] == product)
        unassigned = next(row for row in rows if row["product_id"] is None)
        assert assigned["seconds"] == 3600
        assert assigned["pins"] == 1
        assert unassigned["seconds"] == 1800
        assert assigned["labor_cents"] is None
        set_hourly_rate(db, "USD", "12.00")
        rows = product_time_summary(db, "USD")
        assert next(row for row in rows if row["product_id"] == product)["labor_cents"] == 1200
        assert next(row for row in rows if row["product_id"] is None)["labor_cents"] == 600
        assert product_time_summary(db, "EUR")[0]["labor_cents"] is None
    finally:
        db.close()


def test_product_time_page_refresh(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Storage(tmp_path / "ui.sqlite3")
    try:
        pin = db.create("pins", title="Unassigned pin")
        session = db.start_session()
        db.save_elapsed(session, 60, "Draft", pin)
        page = TimePage(db)
        assert page.products_table.rowCount() == 1
        assert page.products_table.item(0, 0).text() == "Unassigned"
        assert page.products_table.item(0, 3).text() == "Unknown"
        set_hourly_rate(db, "USD", "60.00")
        page.refresh()
        page.currency.setCurrentIndex(page.currency.findData("USD"))
        assert page.products_table.item(0, 3).text() == "1.00 USD"
        page.close()
    finally:
        db.close()
