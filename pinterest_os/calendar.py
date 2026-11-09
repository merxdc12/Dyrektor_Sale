"""Local publishing calendar. Planning is not automatic Pinterest posting."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCalendarWidget, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

STATUS = ("PLANNED", "READY", "PUBLISHED", "CANCELLED")


class ScheduleDialog(QDialog):
    def __init__(self, storage, selected: QDate, entry=None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.entry = entry
        self.setWindowTitle("Edit scheduled pin" if entry else "Schedule pin")
        self.resize(460, 270)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.pin = QComboBox()
        for row in storage.all("pins"):
            self.pin.addItem(row["title"], row["id"])
        if self.pin.count() == 0:
            self.pin.addItem("Create a pin in PIN first", None)
        form.addRow("Pin", self.pin)
        self.when = QDateTimeEdit()
        self.when.setCalendarPopup(True)
        self.when.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.when.setDate(selected)
        self.when.setTime(QDate.currentDate().startOfDay().addSecs(12 * 3600).time())
        form.addRow("Local date / time", self.when)
        self.state = QComboBox()
        for status in STATUS:
            self.state.addItem(status)
        form.addRow("Planning status", self.state)
        form.addRow("Note", QLabel("Publishing remains manual. No automatic Pinterest posting."))
        if entry:
            self.pin.setCurrentIndex(self.pin.findData(entry["pin_id"]))
            self.when.setDateTime(QDate.fromString(entry["scheduled_at"][:10], "yyyy-MM-dd").startOfDay())
            from PyQt6.QtCore import QTime
            self.when.setTime(QTime.fromString(entry["scheduled_at"][11:16], "HH:mm"))
            self.state.setCurrentText(entry["status"])
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        pin_id = self.pin.currentData()
        if pin_id is None:
            QMessageBox.warning(self, "No pin", "Create a pin in the PIN tab first.")
            return
        scheduled = self.when.dateTime().toString("yyyy-MM-ddTHH:mm")
        try:
            if self.entry:
                self.storage.update_schedule(self.entry["id"], pin_id, scheduled, self.state.currentText())
            else:
                self.storage.create_schedule(pin_id, scheduled, self.state.currentText())
        except (ValueError, Exception) as exc:
            QMessageBox.warning(self, "Cannot save schedule", str(exc))
            return
        self.accept()


class CalendarPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.entries = []
        outer = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.prev = QPushButton("◀ Previous")
        self.prev.clicked.connect(lambda: self.move_month(-1))
        controls.addWidget(self.prev)
        self.today = QPushButton("Today")
        self.today.clicked.connect(self.go_today)
        controls.addWidget(self.today)
        self.next = QPushButton("Next ▶")
        self.next.clicked.connect(lambda: self.move_month(1))
        controls.addWidget(self.next)
        controls.addStretch()
        add = QPushButton("+ Schedule pin")
        add.setObjectName("Primary")
        add.clicked.connect(self.add_schedule)
        controls.addWidget(add)
        outer.addLayout(controls)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.refresh)
        self.calendar.currentPageChanged.connect(lambda year, month: self.refresh())
        outer.addWidget(self.calendar, 2)
        self.heading = QLabel()
        outer.addWidget(self.heading)
        self.grid = QTableWidget()
        self.grid.setColumnCount(4)
        self.grid.setHorizontalHeaderLabels(["Time", "Pin", "Status", "ID"])
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.grid.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.verticalHeader().setVisible(False)
        self.grid.setColumnHidden(3, True)
        self.grid.horizontalHeader().setStretchLastSection(True)
        self.grid.doubleClicked.connect(lambda index: self.edit_selected())
        outer.addWidget(self.grid, 1)
        actions = QHBoxLayout()
        edit = QPushButton("Edit selected")
        edit.clicked.connect(self.edit_selected)
        actions.addWidget(edit)
        remove = QPushButton("Remove from calendar")
        remove.clicked.connect(self.remove_selected)
        actions.addWidget(remove)
        actions.addStretch()
        outer.addLayout(actions)
        self.refresh()

    def move_month(self, delta: int):
        selected = self.calendar.selectedDate()
        self.calendar.setSelectedDate(selected.addMonths(delta))

    def go_today(self):
        self.calendar.setSelectedDate(QDate.currentDate())
        self.calendar.showToday()

    def selected_entry(self):
        row = self.grid.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select entry", "Select a scheduled pin first.")
            return None
        item = self.grid.item(row, 3)
        return self.storage.get_schedule(int(item.text())) if item else None

    def add_schedule(self):
        if ScheduleDialog(self.storage, self.calendar.selectedDate(), parent=self).exec():
            self.refresh()

    def edit_selected(self):
        entry = self.selected_entry()
        if entry and ScheduleDialog(self.storage, self.calendar.selectedDate(), entry, self).exec():
            self.refresh()

    def remove_selected(self):
        entry = self.selected_entry()
        if not entry:
            return
        answer = QMessageBox.question(self, "Remove schedule", "Remove this calendar entry? The pin will remain.")
        if answer == QMessageBox.StandardButton.Yes:
            self.storage.delete_schedule(entry["id"])
            self.refresh()

    def refresh(self):
        selected = self.calendar.selectedDate().toString("yyyy-MM-dd")
        entries = self.storage.schedules_for_day(selected)
        self.heading.setText(f"Scheduled pins — {selected}  |  {len(entries)} item(s)")
        self.grid.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            for j, value in enumerate((entry["scheduled_at"][11:16], entry["title"], entry["status"], entry["id"])):
                self.grid.setItem(i, j, QTableWidgetItem(str(value)))
        self.grid.resizeColumnsToContents()
