"""Read-only time accounting over existing work_sessions/time_entries.

No second timer or duplicate writes: MainWindow owns the active session.
"""
from decimal import Decimal, ROUND_HALF_UP
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QLineEdit


def time_summary(storage):
    sessions = storage.conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(active_seconds), 0) FROM work_sessions"
    ).fetchone()
    entries = storage.conn.execute(
        """SELECT task, COALESCE(SUM(seconds),0), COUNT(*)
           FROM time_entries GROUP BY task ORDER BY SUM(seconds) DESC, task"""
    ).fetchall()
    allocated = sum(row[1] for row in entries)
    return {"sessions": sessions[0], "total_seconds": sessions[1],
            "tracked_seconds": allocated,
            "unattributed_seconds": max(0, sessions[1] - allocated),
            "tasks": entries}



def product_time_summary(storage, currency=None):
    """Historical time grouped by CURRENT pin-to-product assignment.

    Unassigned time is visible, not distributed. Current rate is an estimate,
    not a historical payroll cost.
    """
    rows = storage.conn.execute(
        """SELECT p.product_id, COALESCE(pr.name,'Unassigned'),
                  COUNT(DISTINCT t.pin_id), SUM(t.seconds)
           FROM time_entries t
           LEFT JOIN pins p ON p.id=t.pin_id
           LEFT JOIN products pr ON pr.id=p.product_id
           GROUP BY p.product_id ORDER BY pr.name, p.product_id"""
    ).fetchall()
    rate = None
    if currency:
        found = storage.conn.execute(
            "SELECT hourly_cents FROM labor_rates WHERE currency=?", (currency,)
        ).fetchone()
        if found:
            rate = found[0]
    result = []
    for product_id, name, pin_count, seconds in rows:
        cents = None if rate is None else int(
            (Decimal(seconds) * Decimal(rate) / Decimal(3600)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP))
        result.append({"product_id": product_id, "product_name": name,
                       "pins": pin_count, "seconds": seconds, "labor_cents": cents})
    return result


def duration(seconds):
    hours, rem = divmod(int(seconds), 3600)
    minutes, sec = divmod(rem, 60)
    return f"{hours:02}:{minutes:02}:{sec:02}"


class TimePage(QWidget):
    def __init__(self, storage, parent=None, on_change=None):
        super().__init__(parent)
        self.storage = storage
        self.on_change = on_change
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "TIME — work sessions and task allocation. The main window controls "
            "Start/Pause/Stop; this page does not start a second timer."))
        self.current = QLabel("Current session: 00:00:00")
        layout.addWidget(self.current)
        layout.addWidget(QLabel("Task attribution for future time:"))
        self.task = QLineEdit("General")
        layout.addWidget(self.task)
        self.pin = QComboBox()
        layout.addWidget(self.pin)
        apply_button = QPushButton("Apply task / pin")
        apply_button.clicked.connect(self.apply_attribution)
        layout.addWidget(apply_button)
        self.active_task = "General"
        self.active_pin_id = None
        self.selection = QLabel("Active: General / Unassigned")
        layout.addWidget(self.selection)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Task", "Tracked time", "Entries"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        layout.addWidget(QLabel("Product time and estimated labor (current pin assignments):"))
        self.currency = QComboBox()
        layout.addWidget(self.currency)
        self.products_table = QTableWidget(0, 4)
        self.products_table.setHorizontalHeaderLabels(
            ["Product", "Pins", "Time", "Labor estimate"])
        self.products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.products_table)
        button = QPushButton("Refresh time accounting")
        button.clicked.connect(self.refresh)
        layout.addWidget(button)
        layout.addWidget(QLabel(
            "Time is not revenue or verified profit. Labor valuation is calculated "
            "in ANALYTICS using the configured hourly rate."))
        self.currency.currentIndexChanged.connect(self.refresh_products)
        self.refresh()

    def apply_attribution(self):
        name = self.task.text().strip()
        if not name:
            self.selection.setText("Task name required; attribution unchanged.")
            return
        if self.on_change:
            self.on_change()
        self.active_task = name
        self.active_pin_id = self.pin.currentData()
        self.selection.setText("Active: {} / Pin {}".format(
            name, self.active_pin_id if self.active_pin_id is not None else "Unassigned"))

    def reset_attribution(self):
        self.active_task = "General"
        self.active_pin_id = None
        self.task.setText("General")
        self.refresh()
        self.pin.setCurrentIndex(0)
        self.selection.setText("Active: General / Unassigned")

    def set_current(self, seconds):
        self.current.setText("Current session: " + duration(seconds))

    def refresh(self):
        previous = self.pin.currentData()
        self.pin.clear()
        self.pin.addItem("Unassigned", None)
        for pin in self.storage.all("pins"):
            self.pin.addItem("#{} — {}".format(pin["id"], pin["title"]), pin["id"])
        self.pin.setCurrentIndex(max(0, self.pin.findData(previous)))
        data = time_summary(self.storage)
        self.summary.setText(
            f"Sessions: {data['sessions']} | Total: {duration(data['total_seconds'])} | "
            f"Attributed: {duration(data['tracked_seconds'])} | "
            f"Unattributed: {duration(data['unattributed_seconds'])}")
        self.table.setRowCount(len(data["tasks"]))
        for i, (task, seconds, count) in enumerate(data["tasks"]):
            for j, value in enumerate((task, duration(seconds), count)):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        previous_currency = self.currency.currentData()
        self.currency.blockSignals(True)
        self.currency.clear()
        self.currency.addItem("No labor valuation", None)
        for (code,) in self.storage.conn.execute(
                "SELECT currency FROM labor_rates ORDER BY currency"):
            self.currency.addItem(code, code)
        self.currency.setCurrentIndex(max(0, self.currency.findData(previous_currency)))
        self.currency.blockSignals(False)
        self.refresh_products()

    def refresh_products(self):
        currency = self.currency.currentData()
        rows = product_time_summary(self.storage, currency)
        self.products_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            amount = item["labor_cents"]
            values = (item["product_name"], item["pins"], duration(item["seconds"]),
                      "Unknown" if amount is None else
                      f"{Decimal(amount) / 100:.2f} {currency}")
            for j, value in enumerate(values):
                self.products_table.setItem(i, j, QTableWidgetItem(str(value)))
        self.products_table.resizeColumnsToContents()
