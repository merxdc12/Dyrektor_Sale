"""Reports workspace: export-only UI, without duplicate Analytics tables."""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox,
                             QPushButton, QFileDialog, QMessageBox)
from .reports import report_rows, export_report, report_warnings


class ReportsPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "PRODUCT REPORTS — export of attributed estimates, NOT verified net profit. "
            "Financial detail and reconciliation remain in ANALYTICS."))
        self.currency = QComboBox()
        self.currency.currentIndexChanged.connect(self.refresh_summary)
        layout.addWidget(self.currency)
        refresh = QPushButton("Refresh export summary")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.warning = QLabel()
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        export = QPushButton("Export product report CSV")
        export.clicked.connect(self.save_csv)
        layout.addWidget(export)
        layout.addWidget(QLabel(
            "CSV includes per-product revenue, costs, labor estimates, ROI, decisions "
            "and data-integrity flags. Blank values mean unknown or unresolved. "
            "No automatic publication or currency conversion."))
        layout.addStretch()
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
        self.currency.setCurrentIndex(
            self.currency.findData(previous) if previous in currencies
            else (0 if currencies else -1))
        self.currency.blockSignals(False)
        self.refresh_summary()

    def refresh_summary(self):
        currency = self.currency.currentData()
        if not currency:
            self.summary.setText("No financial data or configured labor rate.")
            self.warning.clear()
            return
        rows = report_rows(self.storage, currency)
        self.summary.setText(
            f"Ready to export: {len(rows)} product rows | Currency: {currency}. "
            "Detailed records are available in the CSV export.")
        status = report_warnings(self.storage, currency)
        self.warning.setText(
            f"Cost overlaps: {status['overlaps']} | Unresolved: {status['unresolved']}. "
            "Verify attribution, completeness of costs and labor before decisions.")

    def save_csv(self):
        currency = self.currency.currentData()
        if not currency:
            QMessageBox.warning(self, "Export unavailable", "No report currency available.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export report", f"ithutir_product_report_{currency}.csv",
            "CSV files (*.csv)")
        if not path:
            return
        try:
            count = export_report(self.storage, path, currency)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Report exported", f"{count} rows exported.")
