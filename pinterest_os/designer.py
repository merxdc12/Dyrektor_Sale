"""Simple offline pin composition tool, 1000x1500 PNG export."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

WIDTH, HEIGHT = 1000, 1500


def render_pin(title, subtitle, background, foreground, photo_path=""):
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(QColor(background))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if photo_path:
        photo = QPixmap(photo_path)
        if not photo.isNull():
            scaled = photo.scaled(WIDTH, HEIGHT, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
            x = (scaled.width() - WIDTH) // 2
            y = (scaled.height() - HEIGHT) // 2
            painter.drawPixmap(0, 0, scaled, x, y, WIDTH, HEIGHT)
            painter.fillRect(0, 0, WIDTH, HEIGHT, QColor(0, 0, 0, 125))
    painter.setPen(QColor(foreground))
    font = QFont("Sans Serif", 66, QFont.Weight.Bold)
    painter.setFont(font)
    title_box = painter.boundingRect(90, 250, 820, 720, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, title)
    painter.drawText(90, 250, 820, 720, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, title)
    painter.setFont(QFont("Sans Serif", 28))
    painter.drawText(90, 1020, 820, 260, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, subtitle)
    painter.setFont(QFont("Sans Serif", 23, QFont.Weight.Bold))
    painter.drawText(90, 1370, 820, 70, Qt.AlignmentFlag.AlignCenter, "ITHUTIR")
    painter.end()
    return image


class PinDesigner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.photo_path = ""
        self.background = "#0B1110"
        self.foreground = "#43E58A"
        layout = QHBoxLayout(self)
        left = QWidget()
        form = QFormLayout(left)
        self.title = QLineEdit("Build smarter with Linux")
        self.subtitle = QLineEdit("ITHutir • Engineering & DIY")
        form.addRow("Headline", self.title)
        form.addRow("Subtitle", self.subtitle)
        background = QPushButton("Background color")
        background.clicked.connect(self.pick_background)
        form.addRow(background)
        foreground = QPushButton("Text color")
        foreground.clicked.connect(self.pick_foreground)
        form.addRow(foreground)
        photo = QPushButton("Import background image")
        photo.clicked.connect(self.pick_photo)
        form.addRow(photo)
        clear = QPushButton("Remove background image")
        clear.clicked.connect(self.clear_photo)
        form.addRow(clear)
        preview = QPushButton("Refresh preview")
        preview.clicked.connect(self.refresh)
        form.addRow(preview)
        export = QPushButton("Export PNG (1000 × 1500)")
        export.setObjectName("Primary")
        export.clicked.connect(self.export_png)
        form.addRow(export)
        layout.addWidget(left, 1)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(240, 360)
        layout.addWidget(self.preview, 2)
        self.title.textChanged.connect(self.refresh)
        self.subtitle.textChanged.connect(self.refresh)
        self.refresh()

    def pick_background(self):
        color = QColorDialog.getColor(QColor(self.background), self)
        if color.isValid():
            self.background = color.name()
            self.refresh()

    def pick_foreground(self):
        color = QColorDialog.getColor(QColor(self.foreground), self)
        if color.isValid():
            self.foreground = color.name()
            self.refresh()

    def pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose image", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.photo_path = path
            self.refresh()

    def clear_photo(self):
        self.photo_path = ""
        self.refresh()

    def refresh(self):
        self.image = render_pin(self.title.text(), self.subtitle.text(),
                                self.background, self.foreground, self.photo_path)
        pixmap = QPixmap.fromImage(self.image)
        self.preview.setPixmap(pixmap.scaled(360, 540, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))

    def export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export pin", "ithutir-pin.png", "PNG (*.png)")
        if path:
            self.refresh()
            if not self.image.save(path, "PNG"):
                QMessageBox.warning(self, "Export failed", "Could not write PNG.")
            else:
                QMessageBox.information(self, "Export complete", f"Saved: {path}")
