"""Local-only application preferences and workspace diagnostics."""
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton


class SettingsPage(QWidget):
    def __init__(self, storage, theme, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.theme = theme
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Appearance"))
        self.theme_selector = QComboBox()
        self.theme_selector.setAccessibleName("Application color theme")
        for name, key in (("System", "system"), ("Dark", "dark"), ("Light", "light")):
            self.theme_selector.addItem(name, key)
        self.theme_selector.setCurrentIndex(
            max(0, self.theme_selector.findData(theme.preference)))
        self.theme_selector.currentIndexChanged.connect(self.change_theme)
        layout.addWidget(self.theme_selector)
        layout.addWidget(QLabel("Workspace diagnostics (read-only)"))
        self.diagnostics = QLabel()
        self.diagnostics.setWordWrap(True)
        layout.addWidget(self.diagnostics)
        refresh = QPushButton("Refresh diagnostics")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        layout.addWidget(QLabel(
            "Data stays in the local SQLite workspace. No Pinterest API, "
            "automatic posting or paid advertising. Financial labor rates "
            "are configured in ANALYTICS; time is recorded in TIME."))
        layout.addStretch()
        self.refresh()

    def change_theme(self, index):
        preference = self.theme_selector.itemData(index)
        if preference in {"system", "dark", "light"}:
            self.theme.set_theme(preference)

    def set_storage(self, storage):
        self.storage = storage
        self.refresh()

    def refresh(self):
        path = Path(self.storage.path)
        check = self.storage.conn.execute("PRAGMA quick_check").fetchone()
        status = check[0] if check else "Unknown"
        self.diagnostics.setText(
            f"Database: {path}\n"
            f"SQLite quick_check: {status}\n"
            f"Database size: {path.stat().st_size if path.exists() else 0} bytes\n"
            "Read-only inspection; this does not replace a verified backup.")
