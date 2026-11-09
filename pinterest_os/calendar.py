"""Local publishing calendar. Planning is not automatic Pinterest posting."""
from __future__ import annotations


from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat
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
        pin_record = self.storage.get("pins", pin_id)
        if not pin_record:
            QMessageBox.warning(self, "Missing pin", "Selected pin no longer exists.")
            return
        collisions = self.storage.schedule_conflicts(
            scheduled, pin_record["board_id"],
            self.entry["id"] if self.entry else None)
        if collisions:
            names = ", ".join(f"#{item['pin_id']} {item['title']}" for item in collisions[:5])
            answer = QMessageBox.question(
                self, "Scheduling collision",
                f"Another pin is planned for the same board and minute:\\n{names}\\n"
                "Keep both entries anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            if self.entry:
                self.storage.update_schedule(self.entry["id"], pin_id, scheduled, self.state.currentText())
            else:
                self.storage.create_schedule(pin_id, scheduled, self.state.currentText())
        except (ValueError, Exception) as exc:
            QMessageBox.warning(self, "Cannot save schedule", str(exc))
            return
        self.accept()


class ScheduleGrid(QTableWidget):
    """Drag a schedule row onto a day column to reschedule its date."""
    def __init__(self, on_move, parent=None):
        super().__init__(parent)
        self.on_move = on_move
        self.day_columns = []
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTableWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        if not event.source() is self:
            event.ignore()
            return
        source_row = self.currentRow()
        source_item = self.item(source_row, 0) if source_row >= 0 else None
        target = self.indexAt(event.position().toPoint())
        if source_item is None or not target.isValid():
            event.ignore()
            return
        schedule_id = source_item.data(Qt.ItemDataRole.UserRole)
        if not schedule_id or target.column() >= len(self.day_columns):
            event.ignore()
            return
        day = self.day_columns[target.column()]
        if day and self.on_move(int(schedule_id), day):
            event.acceptProposedAction()
        else:
            event.ignore()


class CalendarPage(QWidget):
    COLORS = {
        "PLANNED": "#E5B64A",
        "READY": "#43E58A",
        "PUBLISHED": "#4C9BE8",
        "CANCELLED": "#E26B72",
    }

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self._marked = set()
        outer = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.prev = QPushButton("◀ Previous")
        self.prev.clicked.connect(lambda: self.move_period(-1))
        controls.addWidget(self.prev)
        self.today = QPushButton("Today")
        self.today.clicked.connect(self.go_today)
        controls.addWidget(self.today)
        self.next = QPushButton("Next ▶")
        self.next.clicked.connect(lambda: self.move_period(1))
        controls.addWidget(self.next)
        self.view = QComboBox()
        for name in ("Month", "Week", "Day"):
            self.view.addItem(name)
        self.view.currentTextChanged.connect(self.refresh)
        controls.addWidget(self.view)
        self.board = QComboBox()
        self.board.currentIndexChanged.connect(self.refresh)
        controls.addWidget(QLabel("Board:"))
        controls.addWidget(self.board)
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
        self.grid = ScheduleGrid(self.move_entry)
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.grid.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.verticalHeader().setVisible(False)
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

    def reload_boards(self):
        selected = self.board.currentData()
        self.board.blockSignals(True)
        self.board.clear()
        self.board.addItem("All boards", None)
        for board in self.storage.all("boards"):
            self.board.addItem(board["name"], board["id"])
        index = self.board.findData(selected)
        self.board.setCurrentIndex(max(index, 0))
        self.board.blockSignals(False)

    def move_period(self, delta: int):
        selected = self.calendar.selectedDate()
        mode = self.view.currentText()
        new_date = selected.addMonths(delta) if mode == "Month" else selected.addDays(delta * (7 if mode == "Week" else 1))
        self.calendar.setSelectedDate(new_date)

    def go_today(self):
        self.calendar.setSelectedDate(QDate.currentDate())
        self.calendar.showToday()

    def selected_entry(self):
        row = self.grid.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select entry", "Select a scheduled pin first.")
            return None
        item = self.grid.item(row, 0)
        entry_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return self.storage.get_schedule(int(entry_id)) if entry_id else None

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

    def move_entry(self, entry_id: int, day: str) -> bool:
        entry = self.storage.get_schedule(entry_id)
        if not entry:
            return False
        if entry["scheduled_at"][:10] == day:
            return False
        answer = QMessageBox.question(
            self, "Reschedule pin",
            f"Move this pin to {day}? The time will remain {entry['scheduled_at'][11:16]}."
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        proposed = day + entry["scheduled_at"][10:]
        pin = self.storage.get("pins", entry["pin_id"])
        if pin:
            conflicts = self.storage.schedule_conflicts(
                proposed, pin["board_id"], exclude_entry_id=entry_id)
            if conflicts and QMessageBox.question(
                self, "Scheduling collision",
                f"{len(conflicts)} existing entry/entries for this board and minute. Move anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return False
        try:
            self.storage.update_schedule(
                entry_id, entry["pin_id"], proposed, entry["status"])
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Reschedule failed", str(exc))
            return False
        self.refresh()
        return True

    def refresh(self, *_):
        self.reload_boards()
        selected = self.calendar.selectedDate()
        mode = self.view.currentText()
        if mode == "Month":
            start = QDate(selected.year(), selected.month(), 1)
            end = start.addMonths(1).addDays(-1)
            self.calendar.show()
        elif mode == "Week":
            start = selected.addDays(1 - selected.dayOfWeek())
            end = start.addDays(6)
            self.calendar.hide()
        else:
            start = selected
            end = selected
            self.calendar.hide()
        start_iso = start.toString("yyyy-MM-dd")
        end_iso = end.toString("yyyy-MM-dd")
        entries = self.storage.schedules_between(start_iso, end_iso, self.board.currentData())
        summary = self.storage.calendar_summary(start_iso, end_iso, self.board.currentData())
        counts = "  |  ".join(f"{key}: {value}" for key, value in summary.items())
        self.heading.setText(
            f"{mode}: {start_iso} — {end_iso}  |  {len(entries)} entries  |  {counts}")
        if mode == "Week":
            days = [start.addDays(i).toString("yyyy-MM-dd") for i in range(7)]
        elif mode == "Day":
            days = [start_iso]
        else:
            days = [start.addDays(i).toString("yyyy-MM-dd") for i in range(start.daysTo(end) + 1)]
        # A compact list in Month mode; Week/Day use date columns as drop targets.
        if mode == "Month":
            headers = ["Date", "Time", "Pin", "Board", "Status"]
            self.grid.day_columns = []
        else:
            headers = days
            self.grid.day_columns = days
        self.grid.clearContents()
        self.grid.setColumnCount(len(headers))
        self.grid.setHorizontalHeaderLabels(headers)
        self.grid.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            if mode == "Month":
                values = [entry["scheduled_at"][:10], entry["scheduled_at"][11:16],
                          entry["title"], entry["board_name"] or "Unassigned", entry["status"]]
                for j, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setData(Qt.ItemDataRole.UserRole, entry["id"])
                    if j == 4:
                        item.setForeground(QColor(self.COLORS[entry["status"]]))
                    self.grid.setItem(i, j, item)
            else:
                target = days.index(entry["scheduled_at"][:10])
                # Each row has a pin in its scheduled day and empty drop targets elsewhere.
                for j in range(len(days)):
                    item = QTableWidgetItem(
                        f"{entry['scheduled_at'][11:16]}  {entry['title']}  [{entry['status']}]"
                        if j == target else "Drop here"
                    )
                    item.setData(Qt.ItemDataRole.UserRole, entry["id"])
                    if j == target:
                        item.setForeground(QColor(self.COLORS[entry["status"]]))
                    self.grid.setItem(i, j, item)
        self.grid.resizeColumnsToContents()
        self.update_markers()

    def update_markers(self):
        # Highlight days with entries in the displayed month, respecting the board filter.
        shown = self.calendar.yearShown(), self.calendar.monthShown()
        first = QDate(shown[0], shown[1], 1)
        last = first.addMonths(1).addDays(-1)
        rows = self.storage.schedules_between(
            first.toString("yyyy-MM-dd"), last.toString("yyyy-MM-dd"), self.board.currentData()
        )
        by_day = {}
        for row in rows:
            by_day.setdefault(row["scheduled_at"][:10], []).append(row["status"])
        for old in self._marked:
            self.calendar.setDateTextFormat(old, QTextCharFormat())
        self._marked.clear()
        for day, statuses in by_day.items():
            qdate = QDate.fromString(day, "yyyy-MM-dd")
            fmt = QTextCharFormat()
            fmt.setFontWeight(QFont.Weight.Bold)
            fmt.setForeground(QColor(self.COLORS[statuses[0]]))
            self.calendar.setDateTextFormat(qdate, fmt)
            self._marked.add(qdate)
