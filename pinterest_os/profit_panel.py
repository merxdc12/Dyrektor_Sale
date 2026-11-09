"""Manual cost entry and transparent labor valuation UI."""
from datetime import date
from PyQt6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)
from .profit_costs import add_cost, set_hourly_rate, labor_summary, cost_summary


class ProfitCostsPanel(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "COST TRACKING — manual ledger. Labor uses current hourly rate on all logged time. "
            "Unassigned costs/time remain unallocated. No verified net profit."))
        form = QFormLayout()
        self.day = QLineEdit(date.today().isoformat())
        self.currency = QLineEdit("USD")
        self.pin_id = QLineEdit()
        self.category = QComboBox()
        self.category.addItems(["DIRECT", "ALLOCATED"])
        self.description = QLineEdit()
        self.amount = QLineEdit()
        for label, widget in (
            ("Date YYYY-MM-DD", self.day), ("Currency", self.currency),
            ("Local pin ID (optional)", self.pin_id), ("Cost category", self.category),
            ("Description", self.description), ("Amount", self.amount)):
            form.addRow(label, widget)
        layout.addLayout(form)
        controls = QHBoxLayout()
        add = QPushButton("Record cost")
        add.clicked.connect(self.record_cost)
        controls.addWidget(add)
        self.hourly = QLineEdit()
        self.hourly.setPlaceholderText("Hourly rate")
        controls.addWidget(self.hourly)
        rate = QPushButton("Save hourly rate")
        rate.clicked.connect(self.save_rate)
        controls.addWidget(rate)
        layout.addLayout(controls)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Pin ID", "Direct cost", "Allocated cost", "Labor estimate"])
        layout.addWidget(self.table)
        refresh = QPushButton("Refresh cost and labor")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.refresh()

    def record_cost(self):
        try:
            pin_id = int(self.pin_id.text()) if self.pin_id.text().strip() else None
            add_cost(self.storage, self.day.text().strip(), self.currency.text(),
                     self.category.currentText(), self.description.text(),
                     self.amount.text(), pin_id)
        except (ValueError, OverflowError) as exc:
            QMessageBox.warning(self, "Invalid cost", str(exc))
            return
        self.refresh()

    def save_rate(self):
        try:
            set_hourly_rate(self.storage, self.currency.text(), self.hourly.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid hourly rate", str(exc))
            return
        self.refresh()

    def refresh(self):
        try:
            currency = self.currency.text().strip().upper()
            costs = cost_summary(self.storage, currency)
            labor = labor_summary(self.storage, currency)
        except ValueError:
            self.summary.setText("Enter a valid three-letter currency.")
            self.table.setRowCount(0)
            return
        labor_label = ("Not configured" if not labor["rate_configured"]
                       else "{:.2f}".format(labor["cost_cents"] / 100))
        self.summary.setText(
            "{} | Direct: {:.2f} | Allocated: {:.2f} | Labor estimate: {} | "
            "Time logged: {:.2f} h".format(
                currency, costs["direct_cents"] / 100, costs["allocated_cents"] / 100,
                labor_label, labor["seconds"] / 3600))
        keys = sorted(set(costs["by_pin"]) | set(labor["by_pin"]),
                      key=lambda value: (value is None, value if value is not None else 0))
        self.table.setRowCount(len(keys))
        for i, pin_id in enumerate(keys):
            cost = costs["by_pin"].get(pin_id, {"DIRECT": 0, "ALLOCATED": 0})
            labor_entry = labor["by_pin"].get(pin_id)
            labor_value = ("N/A" if not labor["rate_configured"] else
                           "{:.2f}".format((labor_entry or {"cost_cents": 0})["cost_cents"] / 100))
            values = (pin_id if pin_id is not None else "Unassigned",
                      "{:.2f}".format(cost["DIRECT"] / 100),
                      "{:.2f}".format(cost["ALLOCATED"] / 100), labor_value)
            for j, value in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
