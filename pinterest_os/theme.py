"""ITHutir design tokens and theme management for Qt widgets."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QEvent, QSettings
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

THEMES = ("system", "dark", "light")
PALETTES = {
    "dark": dict(bg="#0B1110", surface="#14201B", elevated="#1C2C24", text="#F3F8F4",
                 muted="#A7B9AE", border="#345344", accent="#43E58A", accent_text="#082011",
                 hover="#274D37", warning="#F5C84C", danger="#FF7373"),
    "light": dict(bg="#F3F8F4", surface="#FFFFFF", elevated="#E8F1EA", text="#17251C",
                  muted="#50685A", border="#C2D8C8", accent="#147D45", accent_text="#FFFFFF",
                  hover="#D7ECDD", warning="#A66D00", danger="#B42318"),
}


def system_theme(app: QApplication) -> str:
    # The platform's native palette is the source of truth, not a hardcoded OS guess.
    color = app.style().standardPalette().color(QPalette.ColorRole.Window)
    return "dark" if color.lightness() < 128 else "light"


def stylesheet(mode: str) -> str:
    p = PALETTES[mode]
    return """
    QWidget { background: %(bg)s; color: %(text)s; font-size: 14px; }
    QMainWindow, QDialog { background: %(bg)s; }
    QFrame#Card, QFrame#Navigation, QFrame#Header { background: %(surface)s;
        border: 1px solid %(border)s; border-radius: 12px; }
    QLabel#Brand { color: %(accent)s; font-size: 18px; font-weight: 800; }\n    QLabel#HeaderStatus { color: %(muted)s; font-size: 10px; font-weight: 500; }
    QLabel#Heading { font-size: 21px; font-weight: 700; }
    QLabel#WorkspaceHeading { font-size: 18px; font-weight: 700; }
    QLabel#SectionHeading { color: %(text)s; font-size: 16px; font-weight: 700; }
    QLabel#Muted { color: %(muted)s; }
    QLabel#Metric { font-size: 25px; font-weight: 700; color: %(accent)s; }
    QPushButton { background: %(elevated)s; border: 1px solid %(border)s;
        border-radius: 8px; padding: 7px 12px; min-height: 26px; }
    QPushButton:hover { background: %(hover)s; }
    QPushButton:focus { border: 2px solid %(accent)s; }
    QPushButton:disabled { color: %(muted)s; }
    QPushButton#Primary { background: %(accent)s; color: %(accent_text)s;
        border: 1px solid %(accent)s; font-weight: 700; }
    QPushButton#NavButton { text-align: left; padding: 11px 13px; border: none;
        background: transparent; font-weight: 600; }
    QPushButton#NavButton:checked { background: %(accent)s; color: %(accent_text)s;
        border: 1px solid %(accent)s; border-radius: 6px; font-weight: 800; }
    QPushButton#NavButton:checked:hover { background: %(accent)s; color: %(accent_text)s; }
    QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: %(surface)s;
        color: %(text)s; border: 1px solid %(border)s; border-radius: 7px;
        padding: 8px; min-height: 22px; selection-background-color: %(accent)s; }
    QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 2px solid %(accent)s; }
    QTableWidget { background: %(surface)s; alternate-background-color: %(elevated)s;
        gridline-color: %(border)s; border: 1px solid %(border)s;
        selection-background-color: %(hover)s; selection-color: %(text)s; }
    QHeaderView::section { background: %(elevated)s; color: %(text)s;
        border: 0; border-bottom: 1px solid %(border)s; padding: 10px; font-weight: 700; }
    QStatusBar { background: %(surface)s; color: %(muted)s; }
    QScrollArea { border: none; }
    QToolTip { background: %(surface)s; color: %(text)s; border: 1px solid %(accent)s; }
    """ % p


class ThemeManager(QObject):
    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.settings = QSettings("ITHutir", "PinterestOS")
        value = self.settings.value("appearance/theme", "system", type=str)
        self.preference = value if value in THEMES else "system"
        self._resolved = ""
        self.apply()
        app.installEventFilter(self)

    def apply(self) -> None:
        resolved = system_theme(self.app) if self.preference == "system" else self.preference
        if resolved != self._resolved:
            self._resolved = resolved
            self.app.setStyleSheet(stylesheet(resolved))

    def set_theme(self, value: str) -> None:
        if value not in THEMES:
            raise ValueError("Unsupported theme")
        self.preference = value
        self.settings.setValue("appearance/theme", value)
        self.apply()

    def eventFilter(self, watched, event):
        if watched is self.app and event.type() in (
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        ):
            if self.preference == "system":
                # Defer until Qt finishes applying its new platform palette.
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self.apply)
        return False
