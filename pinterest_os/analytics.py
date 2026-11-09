"""Offline operational analytics; never presents local status as Pinterest performance."""
from collections import Counter

from PyQt6.QtWidgets import QFileDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from .analytics_import import import_metrics, metric_history


def operational_summary(storage):
    pins = storage.all("pins")
    boards = storage.all("boards")
    statuses = Counter(pin["status"] for pin in pins)
    schedules = storage.conn.execute(
        "SELECT status, COUNT(*) FROM pin_schedule GROUP BY status").fetchall()
    schedule_counts = dict(schedules)
    carousels = storage.list_carousels()
    return {
        "pins": len(pins), "boards": len(boards),
        "drafts": statuses["DRAFT"], "ready": statuses["READY"],
        "published_local": statuses["PUBLISHED"],
        "scheduled_pending": schedule_counts.get("PLANNED", 0) + schedule_counts.get("READY", 0),
        "confirmed_schedules": schedule_counts.get("PUBLISHED", 0),
        "carousels": len(carousels),
    }


class AnalyticsPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "LOCAL OPERATIONS ONLY — not Pinterest impressions, clicks, saves, or revenue. "
            "Published means manually confirmed in this app, not verified remotely."))
        refresh = QPushButton("Refresh local metrics")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Metric", "Local count"])
        layout.addWidget(self.table)
        layout.addWidget(QLabel("CSV columns: date,pin_id,impressions,outbound_clicks,saves (local pin IDs)."))
        button = QPushButton("Import metrics CSV")
        button.clicked.connect(self.import_csv)
        layout.addWidget(button)
        self.history = QTableWidget(0, 4)
        self.history.setHorizontalHeaderLabels(["Date", "Impressions", "Outbound clicks", "Saves"])
        layout.addWidget(self.history)
        self.refresh()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import metrics", "", "CSV (*.csv)")
        if not path:
            return
        try:
            count = import_metrics(self.storage, path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self.refresh()
        QMessageBox.information(self, "Imported", f"Imported {count} records.")

    def refresh(self):
        values = operational_summary(self.storage)
        labels = [
            ("pins", "Pins in library"), ("boards", "Boards in library"),
            ("drafts", "Draft pins"), ("ready", "Ready pins"),
            ("published_local", "Pins marked published locally"),
            ("scheduled_pending", "Pending calendar entries"),
            ("confirmed_schedules", "Calendar entries confirmed locally"),
            ("carousels", "Saved carousels"),
        ]
        self.table.setRowCount(len(labels))
        for index, (key, title) in enumerate(labels):
            self.table.setItem(index, 0, QTableWidgetItem(title))
            self.table.setItem(index, 1, QTableWidgetItem(str(values[key])))
        self.table.resizeColumnsToContents()
        rows = metric_history(self.storage)
        self.history.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                self.history.setItem(i, j, QTableWidgetItem(str(value)))
        self.history.resizeColumnsToContents()
