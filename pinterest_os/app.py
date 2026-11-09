"""PyQt6 UI foundation for ITHutir Pinterest OS."""
from __future__ import annotations

import sys
import time
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QStandardPaths, QTimer
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

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
        self.setWindowTitle("ITHutir Pinterest OS v1.0 — No API")
        self.resize(1100, 680)

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
            if name in {"PIN", "BOARD"}:
                add = QPushButton("New pin" if name == "PIN" else "New board")
                add.clicked.connect(self.new_pin if name == "PIN" else self.new_board)
                content.addWidget(add)
            if name == "PUBLISHING":
                open_browser = QPushButton("Open Pinterest in browser")
                open_browser.clicked.connect(lambda: webbrowser.open("https://www.pinterest.com/"))
                content.addWidget(open_browser)
            if name == "HELP":
                content.addWidget(QLabel("Offline-first. No API. Publishing is manual."))
            if name not in {"PIN", "BOARD", "PUBLISHING", "HELP"}:
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
        self.stop_button = QPushButton("Stop session")
        self.stop_button.clicked.connect(self.stop_session)
        bottom.addWidget(self.stop_button)
        self.statusBar().showMessage("SQLite: OK | Browser mode | No API")
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000)
        self.render_timer()

    def open_page(self, name: str) -> None:
        self.pages.setCurrentIndex(MENU.index(name))
        self.statusBar().showMessage(f"{name} | Local database | No API")

    def new_pin(self) -> None:
        title, ok = QInputDialog.getText(self, "New pin", "Pin title:")
        if ok and title.strip():
            self.storage.add_pin(title)
            QMessageBox.information(self, "Saved", "Pin draft saved to SQLite.")

    def new_board(self) -> None:
        name, ok = QInputDialog.getText(self, "New board", "Board name:")
        if ok and name.strip():
            self.storage.add_board(name)
            QMessageBox.information(self, "Saved", "Board saved to SQLite.")

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
    data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    if not data_dir:
        raise RuntimeError("Cannot locate platform application data directory")
    storage = Storage(Path(data_dir) / "pinterest_os.sqlite3")
    window = MainWindow(storage)
    window.show()
    return app.exec()
