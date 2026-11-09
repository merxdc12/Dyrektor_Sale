"""Offline user guide, practical lessons and safe diagnostics."""
from __future__ import annotations

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QPlainTextEdit,
    QPushButton, QComboBox, QHBoxLayout,
)

GUIDES = {
    "FILE": "Create a product and set its destination URL. Save a project and make a full ZIP backup before major imports.",
    "PIN": "Create a draft, select a product and board, then review its description and target URL. Designer and carousel tools are local.",
    "BOARD": "Create boards with accurate names and descriptions. Review SEO warnings; they are guidance, not ranking guarantees.",
    "CALENDAR": "Plan publishing slots. A planned slot does not mean a pin was posted.",
    "PUBLISHING": "Open Pinterest in your browser, publish manually, then confirm the outcome in the app. No Pinterest API or auto-posting.",
    "ANALYTICS": "Import measured Pinterest metrics with local pin IDs. Imported numbers are user-provided, not independently verified.",
    "REPORTS": "Inspect product estimates and reconciliation warnings. Estimated contribution is NOT verified net profit.",
    "TIME": "Start/pause/stop the session using the main window. Assign task and pin to future tracked time.",
    "SETTINGS": "Configure appearance and optionally authorize Google Sheets. Review imports before accepting. Google exports create NEW tabs.",
    "HELP": "Read the guide, complete the exercise, and run local diagnostics. Diagnostics never modify records.",
}

LESSONS = (
    ("1. Prepare", "In FILE create a product with a working destination URL. In BOARD create a relevant board. Verify both records."),
    ("2. Produce", "In PIN create a DRAFT linked to that product and board. Check image, title, description and destination."),
    ("3. Plan", "In CALENDAR schedule a slot. Confirm that it remains only a plan until you publish."),
    ("4. Publish manually", "In PUBLISHING open Pinterest, post manually, then record the result. Never mark an unverified post as published."),
    ("5. Measure", "Import actual metrics in ANALYTICS, review estimated contribution in REPORTS, and check time cost in TIME."),
    ("6. Protect", "Create a project backup in FILE. If using Google Sheets, export to a new worksheet and verify the row count."),
)


def diagnostics(storage):
    """Read-only SQLite checks; no external network requests."""
    conn = storage.conn
    result = []
    quick = conn.execute("PRAGMA quick_check").fetchone()
    result.append("SQLite quick_check: " + (str(quick[0]) if quick else "UNKNOWN"))
    foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
    result.append(f"Foreign key violations: {len(foreign_keys)}")
    for table in ("products", "boards", "pins", "pin_schedule",
                  "pinterest_metrics", "time_entries"):
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            result.append(f"{table}: {count}")
        except Exception as exc:
            result.append(f"{table}: unavailable ({type(exc).__name__})")
    path = Path(storage.path)
    result.append(f"Database file exists: {path.is_file()}")
    result.append("No backup created; no external Google or Pinterest connectivity tested.")
    return "\n".join(result)


class HelpPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Offline guidance for organic Pinterest workflows. "
            "No publishing automation, paid ads, or verified revenue claims."))
        tabs = QTabWidget()
        layout.addWidget(tabs)

        guide = QWidget()
        guide_layout = QVBoxLayout(guide)
        selector_row = QHBoxLayout()
        self.guide_selector = QComboBox()
        self.guide_selector.addItems(GUIDES)
        self.guide_selector.currentTextChanged.connect(self.show_guide)
        selector_row.addWidget(QLabel("Module"))
        selector_row.addWidget(self.guide_selector)
        guide_layout.addLayout(selector_row)
        self.guide_text = QPlainTextEdit()
        self.guide_text.setReadOnly(True)
        guide_layout.addWidget(self.guide_text)
        tabs.addTab(guide, "User Guide")

        lessons = QWidget()
        lessons_layout = QVBoxLayout(lessons)
        self.lesson_selector = QComboBox()
        for name, _ in LESSONS:
            self.lesson_selector.addItem(name)
        self.lesson_selector.currentIndexChanged.connect(self.show_lesson)
        lessons_layout.addWidget(self.lesson_selector)
        self.lesson_text = QPlainTextEdit()
        self.lesson_text.setReadOnly(True)
        lessons_layout.addWidget(self.lesson_text)
        tabs.addTab(lessons, "Practical Learning")

        checks = QWidget()
        checks_layout = QVBoxLayout(checks)
        checks_layout.addWidget(QLabel(
            "Read-only diagnostics. They do not validate external services or replace backups."))
        self.diagnostic_text = QPlainTextEdit()
        self.diagnostic_text.setReadOnly(True)
        checks_layout.addWidget(self.diagnostic_text)
        button = QPushButton("Run local diagnostics")
        button.clicked.connect(self.run_diagnostics)
        checks_layout.addWidget(button)
        tabs.addTab(checks, "Diagnostics")

        trouble = QPlainTextEdit()
        trouble.setReadOnly(True)
        trouble.setPlainText(
            "Google Sheets: OAuth requires a local desktop-client JSON and an unlocked OS keyring. "
            "Never commit credentials.\n\n"
            "Duplicate import: review the source and existing local records; do not bypass conflict checks.\n\n"
            "Missing metrics: verify local pin IDs, date format YYYY-MM-DD, and nonnegative counts.\n\n"
            "Database error: stop editing, preserve the project, create a backup, and inspect diagnostics.\n\n"
            "Publishing status: only confirm after verifying the actual Pinterest post in the browser.\n\n"
            "Revenue: use attributable evidence and reconcile all costs before treating an estimate as profit.")
        tabs.addTab(trouble, "Troubleshooting")
        self.show_guide()
        self.show_lesson()
        self.run_diagnostics()

    def show_guide(self, *_):
        name = self.guide_selector.currentText()
        self.guide_text.setPlainText(name + "\n\n" + GUIDES.get(name, ""))

    def show_lesson(self, *_):
        index = self.lesson_selector.currentIndex()
        if index >= 0:
            title, body = LESSONS[index]
            self.lesson_text.setPlainText(
                title + "\n\n" + body +
                "\n\nCheckpoint: perform the action in the app and verify the saved result.")

    def run_diagnostics(self):
        try:
            self.diagnostic_text.setPlainText(diagnostics(self.storage))
        except Exception as exc:
            self.diagnostic_text.setPlainText(
                f"Diagnostic failed: {type(exc).__name__}: {exc}")

    def set_storage(self, storage):
        self.storage = storage
        self.run_diagnostics()
