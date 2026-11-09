"""TIME 4 descriptive efficiency checks; never imply verified net profit."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from pinterest_os.storage import Storage
from pinterest_os.profit_costs import set_hourly_rate
from pinterest_os.time_productivity import productivity_rows
from pinterest_os.time_page import TimePage


def test_time_per_worked_pin_and_unassigned(tmp_path):
    db = Storage(tmp_path / "efficiency.sqlite3")
    try:
        product = db.create("products", name="Guide")
        first = db.create("pins", title="First", product_id=product)
        second = db.create("pins", title="Second", product_id=product)
        session = db.start_session()
        db.save_elapsed(session, 1800, "Design", first)
        db.save_elapsed(session, 1800, "Review", first)
        db.save_elapsed(session, 3600, "Design", second)
        db.save_elapsed(session, 600, "General")
        set_hourly_rate(db, "USD", "12.00")
        rows = productivity_rows(db, "USD")
        guide = next(row for row in rows if row["product_id"] == product)
        assert guide["worked_pins"] == 2
        assert guide["seconds"] == 7200
        assert guide["seconds_per_worked_pin"] == 3600
        assert guide["labor_cents"] == 2400
        assert guide["labor_cents_per_worked_pin"] == 1200
        unknown = next(row for row in rows if row["product_id"] is None)
        assert unknown["worked_pins"] == 0
        assert unknown["seconds_per_worked_pin"] is None
    finally:
        db.close()


def test_time_productivity_gui(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Storage(tmp_path / "ui.sqlite3")
    try:
        pin = db.create("pins", title="Unassigned")
        session = db.start_session()
        db.save_elapsed(session, 60, "Draft", pin)
        page = TimePage(db)
        assert page.products_table.columnCount() == 6
        assert page.products_table.item(0, 4).text() == "00:01:00"
        assert page.products_table.item(0, 5).text() == "N/A"
        page.close()
    finally:
        db.close()
