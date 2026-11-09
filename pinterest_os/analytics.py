"""Offline operational analytics; never presents local status as Pinterest performance."""
from collections import Counter

from PyQt6.QtWidgets import QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


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
        self.refresh()

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
