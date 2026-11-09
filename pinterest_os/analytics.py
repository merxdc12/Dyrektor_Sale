"""Offline operational analytics; never presents local status as Pinterest performance."""
from collections import Counter

from PyQt6.QtWidgets import QComboBox, QFileDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from .analytics_import import import_metrics, metric_history
from .analytics_metrics import daily_performance, pin_performance, group_performance
from .analytics_chart import MetricsChart
from .business_metrics import import_business_metrics, business_summary
from .profit_panel import ProfitCostsPanel


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
        self.pin_filter = QComboBox()
        self.pin_filter.currentIndexChanged.connect(self.refresh_chart)
        layout.addWidget(self.pin_filter)
        self.metric_filter = QComboBox()
        for title, index in (("Impressions", 1), ("Outbound clicks", 2), ("Saves", 3)):
            self.metric_filter.addItem(title, index)
        self.metric_filter.currentIndexChanged.connect(self.refresh_chart)
        layout.addWidget(self.metric_filter)
        self.chart = MetricsChart()
        layout.addWidget(self.chart)
        self.ranking = QTableWidget(0, 6)
        self.ranking.setHorizontalHeaderLabels(["Pin ID", "Title", "Impressions", "Clicks", "Saves", "Outbound CTR %"])
        layout.addWidget(self.ranking)
        layout.addWidget(QLabel("Board / category performance — imported data only."))
        layout.addWidget(QLabel("Attribution uses CURRENT pin-board assignments; changing boards reattributes past metrics."))
        self.group_selector = QComboBox()
        self.group_selector.addItem("Boards", "board")
        self.group_selector.addItem("Board categories", "category")
        self.group_selector.currentIndexChanged.connect(self.refresh_groups)
        layout.addWidget(self.group_selector)
        self.groups = QTableWidget(0, 6)
        self.groups.setHorizontalHeaderLabels(["Board / category", "Pins with data", "Impressions", "Outbound clicks", "Saves", "Outbound CTR %"])
        layout.addWidget(self.groups)
        layout.addWidget(QLabel("BUSINESS: explicitly attributed data only. Contribution = revenue minus REPORTED costs; not verified net profit."))
        layout.addWidget(QLabel("CSV: date,pin_id,currency,site_visits,conversions,revenue,cost. No inferred sales from Pinterest clicks."))
        business_button = QPushButton("Import business CSV")
        business_button.clicked.connect(self.import_business)
        layout.addWidget(business_button)
        self.business_currency = QComboBox()
        self.business_currency.currentIndexChanged.connect(self.refresh_business)
        layout.addWidget(self.business_currency)
        self.business_table = QTableWidget(0, 7)
        self.business_table.setHorizontalHeaderLabels(["Pin", "Site visits", "Conversions", "Conversion %", "Revenue", "Reported costs", "Contribution"])
        layout.addWidget(self.business_table)
        self.profit_costs = ProfitCostsPanel(storage)
        layout.addWidget(self.profit_costs)
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

    def import_business(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import attributed business data", "", "CSV (*.csv)")
        if not path:
            return
        try:
            count = import_business_metrics(self.storage, path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Business import failed", str(exc))
            return
        self.refresh()
        QMessageBox.information(self, "Imported", "Imported {} attributed records.".format(count))

    def refresh_business(self):
        if not hasattr(self, "business_table"):
            return
        currency = self.business_currency.currentData()
        self.business_table.setRowCount(0)
        if not currency:
            return
        rows = business_summary(self.storage, currency)
        self.business_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            rate = "N/A" if item["conversion_rate"] is None else format(item["conversion_rate"], ".2f")
            values = (item["title"], item["visits"], item["conversions"], rate,
                      format(item["revenue_cents"] / 100, ".2f"),
                      format(item["reported_cost_cents"] / 100, ".2f"),
                      format(item["contribution_cents"] / 100, ".2f"))
            for j, value in enumerate(values):
                self.business_table.setItem(i, j, QTableWidgetItem(str(value)))
        self.business_table.resizeColumnsToContents()

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
        ranking = pin_performance(self.storage)
        self.ranking.setRowCount(len(ranking))
        for i, item in enumerate(ranking):
            rate = "N/A" if item["ctr"] is None else format(item["ctr"], ".2f")
            values = (item["pin_id"], item["title"], item["impressions"], item["outbound_clicks"], item["saves"], rate)
            for j, value in enumerate(values):
                self.ranking.setItem(i, j, QTableWidgetItem(str(value)))
        self.ranking.resizeColumnsToContents()
        selected = self.pin_filter.currentData()
        self.pin_filter.blockSignals(True)
        self.pin_filter.clear()
        self.pin_filter.addItem("All imported pins", None)
        for item in ranking:
            self.pin_filter.addItem("#{} — {}".format(item["pin_id"], item["title"]), item["pin_id"])
        self.pin_filter.setCurrentIndex(max(0, self.pin_filter.findData(selected)))
        self.pin_filter.blockSignals(False)
        self.refresh_chart()
        self.refresh_groups()
        selected_currency = self.business_currency.currentData()
        currencies = [row[0] for row in self.storage.conn.execute(
            "SELECT DISTINCT currency FROM business_metrics ORDER BY currency")]
        self.business_currency.blockSignals(True)
        self.business_currency.clear()
        for currency in currencies:
            self.business_currency.addItem(currency, currency)
        self.business_currency.setCurrentIndex(max(0, self.business_currency.findData(selected_currency)))
        self.business_currency.blockSignals(False)
        self.refresh_business()
        self.profit_costs.storage = self.storage
        self.profit_costs.refresh()

    def refresh_groups(self):
        if not hasattr(self, "groups"):
            return
        rows = group_performance(self.storage, self.group_selector.currentData() or "board")
        self.groups.setRowCount(len(rows))
        for i, item in enumerate(rows):
            rate = "N/A" if item["ctr"] is None else format(item["ctr"], ".2f")
            values = (item["name"], item["pins"], item["impressions"], item["outbound_clicks"], item["saves"], rate)
            for j, value in enumerate(values):
                self.groups.setItem(i, j, QTableWidgetItem(str(value)))
        self.groups.resizeColumnsToContents()

    def refresh_chart(self):
        if not hasattr(self, "chart"):
            return
        self.chart.set_data(daily_performance(self.storage, self.pin_filter.currentData()),
                            self.metric_filter.currentData() or 1)
