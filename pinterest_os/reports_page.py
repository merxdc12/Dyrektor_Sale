"""Reports tab: read-only preview and manual CSV export."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox,
                             QPushButton, QFileDialog, QMessageBox,
                             QTableWidget, QTableWidgetItem)
from .reports import FIELDS, report_rows, export_report, report_warnings


class ReportsPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("PRODUCT REPORTS — attributed estimates, NOT verified net profit. "
                                "Current product assignments; no currency conversion."))
        self.currency = QComboBox()
        self.currency.currentIndexChanged.connect(self.refresh_table)
        layout.addWidget(self.currency)
        refresh = QPushButton("Refresh report")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        self.table = QTableWidget(0, len(FIELDS))
        self.table.setHorizontalHeaderLabels(FIELDS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        export = QPushButton("Export product report CSV")
        export.clicked.connect(self.save_csv)
        layout.addWidget(export)
        layout.addWidget(QLabel("Blank estimates mean unknown or unresolved. "
                                "CSV exports are local; no automatic publication."))
        self.refresh()

    def refresh(self):
        previous = self.currency.currentData()
        currencies = [row[0] for row in self.storage.conn.execute(
            """SELECT currency FROM business_metrics UNION SELECT currency FROM cost_entries
               UNION SELECT currency FROM labor_rates ORDER BY currency""")]
        self.currency.blockSignals(True)
        self.currency.clear()
        for code in currencies:
            self.currency.addItem(code, code)
        self.currency.setCurrentIndex(self.currency.findData(previous) if previous in currencies else
                                      (0 if currencies else -1))
        self.currency.blockSignals(False)
        self.refresh_table()

    def refresh_table(self):
        currency = self.currency.currentData()
        if not currency:
            self.table.setRowCount(0)
            self.warning.setText("No financial data or configured labor rate.")
            return
        rows = report_rows(self.storage, currency)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, field in enumerate(FIELDS):
                self.table.setItem(i, j, QTableWidgetItem(str(row[field])))
        self.table.resizeColumnsToContents()
        status = report_warnings(self.storage, currency)
        self.warning.setText(
            "{} product rows | {} cost overlaps | {} unresolved. "
            "Review attribution, all expenses and labor before decisions.".format(
                len(rows), status["overlaps"], status["unresolved"]))

    def save_csv(self):
        currency = self.currency.currentData()
        if not currency:
            QMessageBox.warning(self, "Export unavailable", "No report currency available.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export report", "ithutir_product_report_{}.csv".format(currency),
            "CSV files (*.csv)")
        if not path:
            return
        try:
            count = export_report(self.storage, path, currency)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Report exported", "{} rows exported.".format(count))
