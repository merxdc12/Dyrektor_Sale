"""Accounts settings never collect passwords or claim external authentication."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
from pinterest_os.settings_page import SettingsPage
from pinterest_os.storage import Storage


class Theme:
    preference = "system"
    def set_theme(self, value):
        self.preference = value


def test_accounts_save_identifiers_without_password(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    db = Storage(tmp_path / "db.sqlite3")
    try:
        page = SettingsPage(db, Theme())
        page.pinterest_email.setText("maker@example.com")
        page.google_email.setText("drive@example.com")
        page.pinterest_profile.setText("https://www.pinterest.com/maker/")
        page.save_accounts()
        settings = QSettings("ITHutir", "PinterestOS")
        assert settings.value("accounts/pinterest_email") == "maker@example.com"
        assert settings.value("accounts/google_email") == "drive@example.com"
        assert settings.value("accounts/pinterest_profile") == "https://www.pinterest.com/maker/"
        assert not any("password" in key.lower() or "token" in key.lower()
                       for key in settings.allKeys())
        page.pinterest_profile.setText("https://evil.example/profile")
        page.save_accounts()
        assert settings.value("accounts/pinterest_profile") == "https://www.pinterest.com/maker/"
        page.close()
    finally:
        db.close()
