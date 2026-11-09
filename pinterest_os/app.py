"""Desktop shell: FILE, PIN, BOARD, and future modules."""
from __future__ import annotations

import sys
import time
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QStandardPaths, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from .editor import RecordEditor
from .storage import Storage

MENU = ("FILE", "PIN", "BOARD", "CALENDAR", "PUBLISHING",
        "ANALYTICS", "REPORTS", "TIME", "SETTINGS", "HELP")


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


class MainWindow(QMainWindow):
    def __init__(self, storage: Storage):
        super().__init__()
        self.storage = storage
        self.session_id = storage.start_session()
        self.active_seconds = 0
        self.paused = False
        self.last_tick = time.monotonic()
        self.tables = {}
        self.setWindowTitle("ITHutir Pinterest OS v1.0 — No API")
        self.resize(1280, 720)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        nav = QHBoxLayout()
        layout.addLayout(nav)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        for name in MENU:
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, item=name: self.open_page(item))
            nav.addWidget(button)
            page = QWidget()
            content = QVBoxLayout(page)
            content.addWidget(QLabel(name))
            if name in {"FILE", "PIN", "BOARD"}:
                if name == "FILE":
                    content.addWidget(QLabel("Local workspace: products catalog"))
                table = {"FILE": "products", "PIN": "pins", "BOARD": "boards"}[name]
                actions = QHBoxLayout()
                add = QPushButton("New")
                add.clicked.connect(lambda checked=False, t=table: self.edit_record(t))
                actions.addWidget(add)
                edit = QPushButton("Edit selected")
                edit.clicked.connect(lambda checked=False, t=table: self.edit_selected(t))
                actions.addWidget(edit)
                refresh = QPushButton("Refresh")
                refresh.clicked.connect(lambda checked=False, t=table: self.refresh(t))
                actions.addWidget(refresh)
                content.addLayout(actions)
                grid = QTableWidget()
                grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
                grid.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
                grid.doubleClicked.connect(lambda index, t=table: self.edit_selected(t))
                content.addWidget(grid)
                self.tables[table] = grid
            elif name == "PUBLISHING":
                open_browser = QPushButton("Open Pinterest in browser (manual publishing)")
                open_browser.clicked.connect(lambda: webbrowser.open("https://www.pinterest.com/"))
                content.addWidget(open_browser)
            elif name == "HELP":
                content.addWidget(QLabel("Offline-first. No API. Pinterest publishing is manual."))
            else:
                content.addWidget(QLabel("Module planned for a future phase."))
            content.addStretch()
            self.pages.addWidget(page)
        bottom = QHBoxLayout()
        layout.addLayout(bottom)
        self.timer_label = QLabel()
        bottom.addWidget(self.timer_label)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        bottom.addWidget(self.pause_button)
        stop = QPushButton("Stop session")
        stop.clicked.connect(self.stop_session)
        bottom.addWidget(stop)
        self.stop_button = stop
        self.statusBar().showMessage("SQLite: OK | Manual browser publishing | No API")
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000)
        for table in self.tables:
            self.refresh(table)
        self.render_timer()

    def refresh(self, table: str) -> None:
        grid = self.tables[table]
        rows = self.storage.all(table)
        fields = {
            "products": ("id", "name", "category", "target_url"),
            "boards": ("id", "name", "url", "description"),
            "pins": ("id", "title", "status", "board_id", "product_id", "destination_url"),
        }[table]
        grid.setColumnCount(len(fields))
        grid.setHorizontalHeaderLabels(fields)
        grid.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, field in enumerate(fields):
                grid.setItem(i, j, QTableWidgetItem(str(row.get(field) or "")))
        grid.resizeColumnsToContents()

    def edit_record(self, table: str, record: dict | None = None) -> None:
        editor = RecordEditor(self.storage, table, record, self)
        if editor.exec():
            self.refresh(table)
            if table in {"boards", "products"}:
                self.refresh("pins")

    def edit_selected(self, table: str) -> None:
        grid = self.tables[table]
        row = grid.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select a record", "Select a row first.")
            return
        record_id = int(grid.item(row, 0).text())
        record = self.storage.get(table, record_id)
        if record:
            self.edit_record(table, record)

    def open_page(self, name: str) -> None:
        self.pages.setCurrentIndex(MENU.index(name))
        table = {"FILE": "products", "PIN": "pins", "BOARD": "boards"}.get(name)
        if table:
            self.refresh(table)
        self.statusBar().showMessage(f"{name} | Local SQLite | No API")

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
        self.timer_label.setText(f"ACTIVE: {format_duration(self.active_seconds)}")

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
    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    if not data_dir:
        raise RuntimeError("Cannot locate platform application data directory")
    storage = Storage(Path(data_dir) / "pinterest_os.sqlite3")
    window = MainWindow(storage)
    window.show()
    return app.exec()
