"""ITHutir Pinterest OS — responsive desktop shell and local workspace."""
from __future__ import annotations

import sys
import time
import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt, QStandardPaths, QTimer
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .editor import RecordEditor
from .storage import Storage
from .theme import ThemeManager

MENU = ("FILE", "PIN", "BOARD", "CALENDAR", "PUBLISHING",
        "ANALYTICS", "REPORTS", "TIME", "SETTINGS", "HELP")
TITLES = {
    "FILE": ("Workspace", "Products and content destinations"),
    "PIN": ("Pin library", "Create, edit and organize organic pin drafts"),
    "BOARD": ("Boards", "Manage board names, links and descriptions"),
    "CALENDAR": ("Publishing calendar", "Plan publishing dates — coming next"),
    "PUBLISHING": ("Publishing", "Manual browser-based workflow"),
    "ANALYTICS": ("Analytics", "Performance tracking — coming next"),
    "REPORTS": ("Reports", "Costs and export — coming next"),
    "TIME": ("Time tracking", "Track work sessions and production effort"),
    "SETTINGS": ("Settings", "Appearance and local preferences"),
    "HELP": ("Help", "Offline-first workflow and usage notes"),
}


def format_duration(seconds: int) -> str:
    h, rest = divmod(max(0, seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h:02}:{m:02}:{s:02}"


def label(text: str, object_name: str | None = None) -> QLabel:
    item = QLabel(text)
    if object_name:
        item.setObjectName(object_name)
    item.setWordWrap(True)
    return item


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    body = QVBoxLayout(frame)
    body.setContentsMargins(18, 16, 18, 16)
    body.setSpacing(12)
    return frame, body


class MainWindow(QMainWindow):
    def __init__(self, storage: Storage, theme: ThemeManager):
        super().__init__()
        self.storage, self.theme = storage, theme
        self.session_id = storage.start_session()
        self.active_seconds = 0
        self.paused = False
        self.last_tick = time.monotonic()
        self.tables = {}
        self.nav_buttons = {}
        self.setWindowTitle("ITHutir Pinterest OS — Organic Studio")
        self.resize(1360, 820)
        self.setMinimumSize(850, 580)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 8)
        outer.setSpacing(12)

        header, head = card()
        header.setObjectName("Header")
        row = QHBoxLayout()
        row.addWidget(label("ITHUTIR  /  PINTEREST OS", "Brand"))
        row.addStretch()
        row.addWidget(label("●  OFFLINE FIRST   •   ORGANIC ONLY", "Muted"))
        head.addLayout(row)
        outer.addWidget(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)
        sidebar = QFrame()
        sidebar.setObjectName("Navigation")
        sidebar.setMinimumWidth(160)
        sidebar.setMaximumWidth(230)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(10, 16, 10, 12)
        nav.addWidget(label("WORKSPACE", "Muted"))
        for name in MENU:
            button = QPushButton(name)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, item=name: self.open_page(item))
            nav.addWidget(button)
            self.nav_buttons[name] = button
        nav.addStretch()
        split.addWidget(sidebar)

        self.pages = QStackedWidget()
        split.addWidget(self.pages)
        split.setStretchFactor(1, 1)
        for name in MENU:
            page = QWidget()
            content = QVBoxLayout(page)
            content.setContentsMargins(18, 6, 12, 12)
            content.setSpacing(16)
            title, subtitle = TITLES[name]
            content.addWidget(label(title, "Heading"))
            content.addWidget(label(subtitle, "Muted"))
            if name in {"FILE", "PIN", "BOARD"}:
                table = {"FILE": "products", "PIN": "pins", "BOARD": "boards"}[name]
                self.build_catalog(content, table)
            elif name == "SETTINGS":
                panel, body = card()
                body.addWidget(label("Appearance", "Heading"))
                body.addWidget(label("Theme follows the operating system when System is selected.", "Muted"))
                selector = QComboBox()
                selector.setAccessibleName("Application color theme")
                for title, value in (("System", "system"), ("Dark", "dark"), ("Light", "light")):
                    selector.addItem(title, value)
                selector.setCurrentIndex(selector.findData(self.theme.preference))
                selector.currentIndexChanged.connect(
                    lambda idx: self.theme.set_theme(selector.itemData(idx))
                )
                body.addWidget(selector)
                content.addWidget(panel)
            elif name == "TIME":
                panel, body = card()
                body.addWidget(label("Current work session", "Heading"))
                self.time_metric = label("00:00:00", "Metric")
                body.addWidget(self.time_metric)
                content.addWidget(panel)
            elif name == "PUBLISHING":
                panel, body = card()
                body.addWidget(label("Manual publishing", "Heading"))
                body.addWidget(label("Prepare pins locally, then publish in your browser. No API or auto-posting.", "Muted"))
                browser = QPushButton("Open Pinterest ↗")
                browser.setObjectName("Primary")
                browser.clicked.connect(lambda: webbrowser.open("https://www.pinterest.com/"))
                body.addWidget(browser)
                content.addWidget(panel)
            elif name == "HELP":
                panel, body = card()
                body.addWidget(label("Getting started", "Heading"))
                body.addWidget(label(
                    "1. Add a product in FILE.\n2. Create a board in BOARD.\n"
                    "3. Create a pin draft in PIN and link both records.\n"
                    "4. Open Pinterest in PUBLISHING and publish manually.\n"
                    "5. TIME records active work. SETTINGS controls appearance."
                ))
                content.addWidget(panel)
            else:
                panel, body = card()
                body.addWidget(label("Planned module", "Heading"))
                body.addWidget(label("This section is reserved for the next development phase.", "Muted"))
                content.addWidget(panel)
            content.addStretch()
            self.pages.addWidget(page)

        footer, foot = card()
        footer_row = QHBoxLayout()
        footer_row.addWidget(label("SESSION", "Muted"))
        self.timer_label = label("00:00:00", "Metric")
        footer_row.addWidget(self.timer_label)
        footer_row.addStretch()
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        footer_row.addWidget(self.pause_button)
        self.stop_button = QPushButton("Stop session")
        self.stop_button.clicked.connect(self.stop_session)
        footer_row.addWidget(self.stop_button)
        foot.addLayout(footer_row)
        outer.addWidget(footer)
        self.statusBar().showMessage("SQLite connected  •  No API  •  Manual publishing")
        for table in self.tables:
            self.refresh(table)
        self.open_page("PIN")
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000)
        self.render_timer()

    def build_catalog(self, content: QVBoxLayout, table: str) -> None:
        panel, body = card()
        actions = QHBoxLayout()
        actions.addWidget(label("LOCAL RECORDS", "Muted"))
        actions.addStretch()
        add = QPushButton("+ New")
        add.setObjectName("Primary")
        add.clicked.connect(lambda checked=False, t=table: self.edit_record(t))
        actions.addWidget(add)
        edit = QPushButton("Edit selected")
        edit.clicked.connect(lambda checked=False, t=table: self.edit_selected(t))
        actions.addWidget(edit)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(lambda checked=False, t=table: self.refresh(t))
        actions.addWidget(refresh)
        body.addLayout(actions)
        grid = QTableWidget()
        grid.setAlternatingRowColors(True)
        grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        grid.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        grid.verticalHeader().setVisible(False)
        grid.horizontalHeader().setStretchLastSection(True)
        grid.doubleClicked.connect(lambda index, t=table: self.edit_selected(t))
        grid.setMinimumHeight(300)
        body.addWidget(grid)
        content.addWidget(panel, 1)
        self.tables[table] = grid

    def refresh(self, table: str) -> None:
        grid = self.tables[table]
        rows = self.storage.all(table)
        fields = {
            "products": ("id", "name", "category", "target_url"),
            "boards": ("id", "name", "url", "description"),
            "pins": ("id", "title", "status", "board_id", "product_id", "destination_url"),
        }[table]
        grid.setColumnCount(len(fields))
        grid.setHorizontalHeaderLabels([x.replace("_", " ").title() for x in fields])
        grid.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, field in enumerate(fields):
                grid.setItem(i, j, QTableWidgetItem(str(row.get(field) if row.get(field) is not None else "")))
        grid.resizeColumnsToContents()

    def edit_record(self, table: str, record: dict | None = None) -> None:
        if RecordEditor(self.storage, table, record, self).exec():
            self.refresh(table)
            if table in {"boards", "products"}:
                self.refresh("pins")

    def edit_selected(self, table: str) -> None:
        grid = self.tables[table]
        row = grid.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select a record", "Select a row first.")
            return
        record = self.storage.get(table, int(grid.item(row, 0).text()))
        if record:
            self.edit_record(table, record)

    def open_page(self, name: str) -> None:
        self.pages.setCurrentIndex(MENU.index(name))
        for key, button in self.nav_buttons.items():
            button.setChecked(key == name)
        self.statusBar().showMessage(f"{name}  •  SQLite connected  •  No API")

    def record_elapsed(self) -> None:
        if self.session_id is None:
            return
        now = time.monotonic()
        if not self.paused:
            elapsed = max(0, int(now - self.last_tick))
            if elapsed:
                self.active_seconds += elapsed
                self.storage.save_elapsed(self.session_id, elapsed)
                self.last_tick += elapsed
        else:
            self.last_tick = now

    def tick(self) -> None:
        self.record_elapsed()
        self.render_timer()

    def render_timer(self) -> None:
        value = format_duration(self.active_seconds)
        self.timer_label.setText(value)
        if hasattr(self, "time_metric"):
            self.time_metric.setText(value)

    def toggle_pause(self) -> None:
        if self.session_id is None:
            return
        self.record_elapsed()
        self.paused = not self.paused
        self.last_tick = time.monotonic()
        self.pause_button.setText("Resume" if self.paused else "Pause")

    def stop_session(self) -> None:
        if self.session_id is None:
            return
        self.record_elapsed()
        self.storage.end_session(self.session_id)
        self.session_id = None
        self.tick_timer.stop()
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.statusBar().showMessage("Session stopped. Data saved.")

    def closeEvent(self, event) -> None:
        self.stop_session()
        self.storage.close()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("ITHutir")
    app.setApplicationName("PinterestOS")
    theme = ThemeManager(app)
    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    if not data_dir:
        raise RuntimeError("Cannot locate platform application data directory")
    storage = Storage(Path(data_dir) / "pinterest_os.sqlite3")
    window = MainWindow(storage, theme)
    window.show()
    return app.exec()
