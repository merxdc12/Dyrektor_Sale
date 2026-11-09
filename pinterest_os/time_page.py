"""Read-only time accounting over existing work_sessions/time_entries.

No second timer or duplicate writes: MainWindow owns the active session.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem


def time_summary(storage):
    sessions = storage.conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(active_seconds), 0) FROM work_sessions"
    ).fetchone()
    entries = storage.conn.execute(
        """SELECT task, COALESCE(SUM(seconds),0), COUNT(*)
           FROM time_entries GROUP BY task ORDER BY SUM(seconds) DESC, task"""
    ).fetchall()
    allocated = sum(row[1] for row in entries)
    return {"sessions": sessions[0], "total_seconds": sessions[1],
            "tracked_seconds": allocated,
            "unattributed_seconds": max(0, sessions[1] - allocated),
            "tasks": entries}


def duration(seconds):
    hours, rem = divmod(int(seconds), 3600)
    minutes, sec = divmod(rem, 60)
    return f"{hours:02}:{minutes:02}:{sec:02}"


class TimePage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "TIME — work sessions and task allocation. The main window controls "
            "Start/Pause/Stop; this page does not start a second timer."))
        self.current = QLabel("Current session: 00:00:00")
        layout.addWidget(self.current)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Task", "Tracked time", "Entries"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        button = QPushButton("Refresh time accounting")
        button.clicked.connect(self.refresh)
        layout.addWidget(button)
        layout.addWidget(QLabel(
            "Time is not revenue or verified profit. Labor valuation is calculated "
            "in ANALYTICS using the configured hourly rate."))
        self.refresh()

    def set_current(self, seconds):
        self.current.setText("Current session: " + duration(seconds))

    def refresh(self):
        data = time_summary(self.storage)
        self.summary.setText(
            f"Sessions: {data['sessions']} | Total: {duration(data['total_seconds'])} | "
            f"Attributed: {duration(data['tracked_seconds'])} | "
            f"Unattributed: {duration(data['unattributed_seconds'])}")
        self.table.setRowCount(len(data["tasks"]))
        for i, (task, seconds, count) in enumerate(data["tasks"]):
            for j, value in enumerate((task, duration(seconds), count)):
                self.table.setItem(i, j, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
