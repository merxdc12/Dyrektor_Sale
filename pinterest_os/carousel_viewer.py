"""Full-screen offline carousel image viewer."""
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class CarouselViewer(QDialog):
    def __init__(self, slides, start=0, parent=None):
        super().__init__(parent)
        self.slides = slides
        self.index = max(0, min(start, len(slides) - 1))
        self.setWindowTitle("Перегляд каруселі")
        layout = QVBoxLayout(self)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(1, 1)
        self.caption = QLabel()
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image, 1)
        layout.addWidget(self.caption)
        controls = QHBoxLayout()
        for title, callback in (("← Попередній", lambda: self.navigate(-1)),
                                ("Наступний →", lambda: self.navigate(1)),
                                ("Закрити", self.accept)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            controls.addWidget(button)
        layout.addLayout(controls)
        for key, direction in (("Left", -1), ("Right", 1)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda step=direction: self.navigate(step))
        self.showFullScreen()
        QTimer.singleShot(100, self.render)

    def navigate(self, step):
        if self.slides:
            self.index = (self.index + step) % len(self.slides)
            self.render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.render)

    def render(self):
        if not self.slides:
            return
        slide = self.slides[self.index]
        self.caption.setText(f"{self.index + 1} / {len(self.slides)} — {slide['title']}")
        path = slide.get("png_path") or ""
        pixmap = QPixmap(path) if path and Path(path).is_file() else QPixmap()
        if pixmap.isNull():
            self.image.clear()
            self.image.setText("PNG відсутній або не читається")
        else:
            self.image.setPixmap(pixmap.scaled(
                max(1, self.image.width()), max(1, self.image.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
