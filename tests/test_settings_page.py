"""SETTINGS: local preferences, diagnostics, and project switching."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from pinterest_os.storage import Storage
from pinterest_os.settings_page import SettingsPage


class FakeTheme:
    preference = "system"
    def set_theme(self, name):
        self.preference = name


def test_settings_theme_and_database_diagnostics(tmp_path):
    app = QApplication.instance() or QApplication([])
    first = Storage(tmp_path / "first.sqlite3")
    second = Storage(tmp_path / "second.sqlite3")
    try:
        theme = FakeTheme()
        page = SettingsPage(first, theme)
        assert "first.sqlite3" in page.diagnostics.text()
        assert "SQLite quick_check: ok" in page.diagnostics.text()
        page.theme_selector.setCurrentIndex(page.theme_selector.findData("dark"))
        assert theme.preference == "dark"
        page.set_storage(second)
        assert "second.sqlite3" in page.diagnostics.text()
        assert "first.sqlite3" not in page.diagnostics.text()
        page.close()
    finally:
        first.close()
        second.close()
