"""Manual-only publishing queue and explicit local confirmation."""
from __future__ import annotations

import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .publishing_logic import mark_published, pending_queue, publishing_issues


class PublishingPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Manual publishing queue — no Pinterest API or automatic posting"))
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Scheduled", "Pin", "Board", "Status", "Checklist"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        for title, handler in (
            ("Refresh", self.refresh),
            ("Review selected", self.review_selected),
            ("Copy pin details", self.copy_selected_details),
            ("Open Pinterest", lambda: webbrowser.open("https://www.pinterest.com/")),
            ("Confirm manually published", self.confirm_published),
        ):
            button = QPushButton(title)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        rows = pending_queue(self.storage)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            pin = self.storage.get("pins", row["pin_id"])
            issues = publishing_issues(pin, self.storage.get_pin_design(row["pin_id"]))
            values = [row["scheduled_at"], row["title"], row["board_name"] or "Unassigned",
                      row["status"], "READY" if not issues else f"{len(issues)} missing"]
            for j, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.table.setItem(i, j, cell)
        self.table.resizeColumnsToContents()

    def selected_id(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(self, "Select a pin", "Select a queue row first.")
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def review_selected(self):
        entry_id = self.selected_id()
        if entry_id is None:
            return
        entry = self.storage.get_schedule(entry_id)
        pin = self.storage.get("pins", entry["pin_id"])
        if not pin:
            QMessageBox.warning(self, "Missing pin", "Pin no longer exists.")
            self.refresh()
            return
        issues = publishing_issues(pin, self.storage.get_pin_design(pin["id"]))
        text = ("Missing:\n• " + "\n• ".join(issues)) if issues else (
            "Local metadata and image file checks passed.\n"
            "Review the image, destination and board in Pinterest before publishing.")
        QMessageBox.information(self, "Publishing review", text)

    def copy_selected_details(self):
        """Copy local pin metadata for manual pasting; never sends it to Pinterest."""
        entry_id = self.selected_id()
        if entry_id is None:
            return
        entry = self.storage.get_schedule(entry_id)
        if not entry:
            QMessageBox.warning(self, "Missing entry", "Calendar entry no longer exists.")
            self.refresh()
            return
        pin = self.storage.get("pins", entry["pin_id"])
        if not pin:
            QMessageBox.warning(self, "Missing pin", "Pin no longer exists.")
            self.refresh()
            return
        board = self.storage.get("boards", pin["board_id"]) if pin["board_id"] else None
        details = ("Title: " + pin["title"] + "\\n"
                   + "Description: " + pin["description"] + "\\n"
                   + "Destination: " + pin["destination_url"] + "\\n"
                   + "Board: " + (board["name"] if board else "Unassigned"))
        QApplication.clipboard().setText(details)
        QMessageBox.information(self, "Copied", "Pin details copied for manual pasting.")

    def confirm_published(self):
        entry_id = self.selected_id()
        if entry_id is None:
            return
        entry = self.storage.get_schedule(entry_id)
        pin = self.storage.get("pins", entry["pin_id"])
        issues = publishing_issues(pin, self.storage.get_pin_design(pin["id"]))
        if issues:
            QMessageBox.warning(self, "Not ready", "\n".join(issues))
            return
        answer = QMessageBox.question(
            self, "Confirm manual publication",
            "Only confirm after YOU have published this pin on Pinterest.\n"
            "This updates local records; it cannot verify the remote publication. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            mark_published(self.storage, entry_id)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Cannot update status", str(exc))
            return
        self.refresh()
        window = self.window()
        if hasattr(window, "calendar_page"):
            window.calendar_page.refresh()
        if hasattr(window, "refresh") and hasattr(window, "tables"):
            window.refresh("pins")
