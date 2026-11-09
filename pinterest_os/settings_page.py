"""Local-only application preferences and workspace diagnostics."""
from pathlib import Path
import webbrowser
from urllib.parse import urlparse
from PyQt6.QtCore import QSettings
from .google_sheets_link import parse_sheet_url, preview_public_sheet
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit, QFormLayout, QGroupBox, QPlainTextEdit


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
        self.preferences = QSettings("ITHutir", "PinterestOS")
        accounts = QGroupBox("Accounts — browser sign-in (no stored passwords)")
        form = QFormLayout(accounts)
        self.pinterest_email = QLineEdit()
        self.pinterest_email.setText(self.preferences.value("accounts/pinterest_email", "", str))
        self.pinterest_email.setPlaceholderText("Pinterest account email")
        form.addRow("Pinterest email", self.pinterest_email)
        self.pinterest_profile = QLineEdit()
        self.pinterest_profile.setText(self.preferences.value("accounts/pinterest_profile", "", str))
        self.pinterest_profile.setPlaceholderText("https://www.pinterest.com/yourprofile/")
        form.addRow("Pinterest profile URL", self.pinterest_profile)
        self.google_email = QLineEdit()
        self.google_email.setText(self.preferences.value("accounts/google_email", "", str))
        self.google_email.setPlaceholderText("Google Drive account email")
        form.addRow("Google email", self.google_email)
        self.account_status = QLabel(
            "Emails and profile URL are local identifiers only. No account connection "
            "or Drive synchronization is established. Passwords are never collected.")
        self.account_status.setWordWrap(True)
        form.addRow(self.account_status)
        save_accounts = QPushButton("Save account identifiers")
        save_accounts.clicked.connect(self.save_accounts)
        form.addRow(save_accounts)
        pinterest_login = QPushButton("Open Pinterest sign-in in browser")
        pinterest_login.clicked.connect(lambda: webbrowser.open("https://www.pinterest.com/login/"))
        form.addRow(pinterest_login)
        google_login = QPushButton("Open Google Drive in browser")
        google_login.clicked.connect(lambda: webbrowser.open("https://drive.google.com/"))
        form.addRow(google_login)
        layout.addWidget(accounts)
        sheets = QGroupBox("Google Sheets — selected spreadsheet")
        sheet_form = QFormLayout(sheets)
        self.sheet_url = QLineEdit()
        self.sheet_url.setPlaceholderText("https://docs.google.com/spreadsheets/d/.../edit#gid=0")
        self.sheet_url.setText(self.preferences.value("sheets/url", "", str))
        sheet_form.addRow("Spreadsheet URL", self.sheet_url)
        self.sheet_status = QLabel(
            "No Google authorization. Public CSV preview only; private sheets "
            "and writing require a separate authorized integration.")
        self.sheet_status.setWordWrap(True)
        sheet_form.addRow(self.sheet_status)
        save_sheet = QPushButton("Validate and save link")
        save_sheet.clicked.connect(self.save_sheet_link)
        sheet_form.addRow(save_sheet)
        preview_sheet = QPushButton("Preview public sheet (read-only)")
        preview_sheet.clicked.connect(self.preview_sheet)
        sheet_form.addRow(preview_sheet)
        self.sheet_preview = QPlainTextEdit()
        self.sheet_preview.setReadOnly(True)
        self.sheet_preview.setMaximumHeight(120)
        sheet_form.addRow(self.sheet_preview)
        layout.addWidget(sheets)
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

    def save_accounts(self):
        pinterest = self.pinterest_email.text().strip()
        google = self.google_email.text().strip()
        profile = self.pinterest_profile.text().strip()
        for address in (pinterest, google):
            if address and (address.count("@") != 1 or " " in address or "." not in address.split("@")[-1]):
                self.account_status.setText("Invalid email format. Nothing saved.")
                return
        if profile:
            parsed = urlparse(profile)
            if parsed.scheme != "https" or parsed.hostname not in (
                    "pinterest.com", "www.pinterest.com"):
                self.account_status.setText(
                    "Pinterest profile must use https://www.pinterest.com/ . Nothing saved.")
                return
        self.preferences.setValue("accounts/pinterest_email", pinterest)
        self.preferences.setValue("accounts/pinterest_profile", profile)
        self.preferences.setValue("accounts/google_email", google)
        self.preferences.sync()
        if self.preferences.status() != QSettings.Status.NoError:
            self.account_status.setText("Could not save local settings.")
            return
        self.account_status.setText(
            "Local account identifiers saved. Sign in separately in the browser; "
            "no passwords, OAuth tokens or automatic Drive access are stored.")

    def save_sheet_link(self):
        value = self.sheet_url.text().strip()
        if not value:
            self.sheet_status.setText("Enter a spreadsheet URL; existing link not changed.")
            return
        try:
            spreadsheet_id, gid = parse_sheet_url(value)
        except ValueError as exc:
            self.sheet_status.setText(str(exc))
            return
        self.preferences.setValue("sheets/url", value)
        self.preferences.sync()
        if self.preferences.status() != QSettings.Status.NoError:
            self.sheet_status.setText("Could not save spreadsheet URL.")
            return
        self.sheet_status.setText(
            f"Link saved locally (sheet gid={gid}). Access not yet tested. "
            "This does not grant permission to read or write.")

    def preview_sheet(self):
        value = self.sheet_url.text().strip()
        self.sheet_preview.clear()
        try:
            rows = preview_public_sheet(value)
        except Exception as exc:
            self.sheet_status.setText(
                f"Public preview unavailable: {type(exc).__name__}: {exc}. "
                "Private sheets require authorization.")
            return
        self.sheet_preview.setPlainText(
            "\\n".join(" | ".join(cell[:100] for cell in row[:12]) for row in rows))
        self.sheet_status.setText(
            f"Read-only public CSV preview: {len(rows)} rows shown (up to 10). "
            "No records imported or modified.")
