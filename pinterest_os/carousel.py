"""Offline carousel composer from existing exported pin PNG assets."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QMessageBox, QPushButton, QVBoxLayout, QWidget, QListView, QListWidgetItem,
)

from .carousel_logic import export_carousel, validate_slides


class CarouselPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Create an ordered multi-image carousel from existing pin PNGs. Manual upload only."))
        header = QHBoxLayout()
        self.carousel = QComboBox()
        self.carousel.currentIndexChanged.connect(self.reload_slides)
        header.addWidget(self.carousel)
        new = QPushButton("+ New carousel")
        new.clicked.connect(self.create_carousel)
        header.addWidget(new)
        layout.addLayout(header)
        self.slides = QListWidget()
        self.slides.currentRowChanged.connect(self.update_preview)
        layout.addWidget(self.slides)
        layout.addWidget(QLabel("Carousel storyboard — select a thumbnail to preview"))
        self.storyboard = QListWidget()
        self.storyboard.setViewMode(QListView.ViewMode.IconMode)
        self.storyboard.setFlow(QListView.Flow.LeftToRight)
        self.storyboard.setWrapping(False)
        self.storyboard.setIconSize(QSize(92, 116))
        self.storyboard.setGridSize(QSize(120, 150))
        self.storyboard.setFixedHeight(165)
        self.storyboard.currentRowChanged.connect(self.slides.setCurrentRow)
        self.slides.currentRowChanged.connect(self.storyboard.setCurrentRow)
        layout.addWidget(self.storyboard)
        self.preview_label = QLabel("Select a slide to preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(300)
        layout.addWidget(self.preview_label)
        self.slide_info = QLabel("No slides")
        layout.addWidget(self.slide_info)
        navigation = QHBoxLayout()
        previous = QPushButton("Previous slide")
        previous.clicked.connect(lambda: self.navigate(-1))
        following = QPushButton("Next slide")
        following.clicked.connect(lambda: self.navigate(1))
        navigation.addWidget(previous)
        navigation.addWidget(following)
        layout.addLayout(navigation)
        buttons = QHBoxLayout()
        for name, callback in (
            ("Add pin", self.add_pin), ("Remove", self.remove_pin),
            ("Move up", lambda: self.move_slide(-1)),
            ("Move down", lambda: self.move_slide(1)),
            ("Export ordered ZIP", self.export_zip),
        ):
            button = QPushButton(name)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.reload_carousels()

    def reload_carousels(self):
        current = self.carousel.currentData()
        self.carousel.blockSignals(True)
        self.carousel.clear()
        for row in self.storage.list_carousels():
            self.carousel.addItem(row["title"], row["id"])
        index = self.carousel.findData(current)
        self.carousel.setCurrentIndex(index if index >= 0 else 0)
        self.carousel.blockSignals(False)
        self.reload_slides()

    def reload_slides(self):
        self.slides.clear()
        self.storyboard.clear()
        carousel_id = self.carousel.currentData()
        if carousel_id is None:
            return
        for row in self.storage.carousel_slides(carousel_id):
            label = f'{row["position"]:02d} — {row["title"]}'
            if not row.get("png_path") or not Path(row["png_path"]).is_file():
                label += "  [PNG missing]"
            self.slides.addItem(label)
            thumbnail = QListWidgetItem(label)
            path = row.get("png_path") or ""
            if path and Path(path).is_file():
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    thumbnail.setIcon(QIcon(pixmap.scaled(
                        QSize(92, 116), Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)))
            self.storyboard.addItem(thumbnail)
        if self.slides.count():
            self.slides.setCurrentRow(0)
        else:
            self.update_preview(-1)

    def navigate(self, delta: int):
        if self.slides.count():
            row = max(0, min(self.slides.count() - 1, self.slides.currentRow() + delta))
            self.slides.setCurrentRow(row)

    def update_preview(self, row: int):
        carousel_id = self.carousel.currentData()
        slides = self.storage.carousel_slides(carousel_id) if carousel_id is not None else []
        if row < 0 or row >= len(slides):
            self.preview_label.clear()
            self.preview_label.setText("Select a slide to preview")
            self.slide_info.setText(f"{len(slides)} slides")
            return
        slide = slides[row]
        self.slide_info.setText(f"Slide {row + 1} of {len(slides)} — {slide['title']}")
        path = slide.get("png_path") or ""
        pixmap = QPixmap(path) if path and Path(path).is_file() else QPixmap()
        if pixmap.isNull():
            self.preview_label.clear()
            self.preview_label.setText("PNG missing or unreadable. Export this pin again.")
            return
        self.preview_label.setPixmap(pixmap.scaled(
            QSize(260, 300), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def create_carousel(self):
        title, ok = QInputDialog.getText(self, "New carousel", "Carousel title:")
        if ok and title.strip():
            carousel_id = self.storage.create_carousel(title)
            self.reload_carousels()
            self.carousel.setCurrentIndex(self.carousel.findData(carousel_id))

    def _ids(self):
        return [row["pin_id"] for row in self.storage.carousel_slides(self.carousel.currentData())]

    def add_pin(self):
        carousel_id = self.carousel.currentData()
        if carousel_id is None:
            QMessageBox.information(self, "Create carousel", "Create a carousel first.")
            return
        existing = self._ids()
        options = [(f'#{p["id"]} — {p["title"]}', p["id"])
                   for p in self.storage.all("pins") if p["id"] not in existing]
        if not options:
            QMessageBox.information(self, "No pins", "No additional pins available.")
            return
        choice, ok = QInputDialog.getItem(self, "Add pin", "Choose pin:",
                                          [name for name, _ in options], 0, False)
        if ok:
            selected = dict(options)[choice]
            try:
                self.storage.set_carousel_slides(carousel_id, existing + [selected])
            except ValueError as exc:
                QMessageBox.warning(self, "Cannot add pin", str(exc))
                return
            self.reload_slides()

    def remove_pin(self):
        row = self.slides.currentRow()
        if row < 0:
            return
        ids = self._ids()
        ids.pop(row)
        self.storage.set_carousel_slides(self.carousel.currentData(), ids)
        self.reload_slides()

    def move_slide(self, offset):
        row = self.slides.currentRow()
        ids = self._ids()
        target = row + offset
        if row < 0 or target < 0 or target >= len(ids):
            return
        ids[row], ids[target] = ids[target], ids[row]
        self.storage.set_carousel_slides(self.carousel.currentData(), ids)
        self.reload_slides()
        self.slides.setCurrentRow(target)

    def export_zip(self):
        carousel_id = self.carousel.currentData()
        if carousel_id is None:
            QMessageBox.information(self, "Create carousel", "Create a carousel first.")
            return
        slides = self.storage.carousel_slides(carousel_id)
        errors = validate_slides(slides)
        if errors:
            QMessageBox.warning(self, "Carousel not ready", "\n".join(errors))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export carousel", "carousel.zip",
                                               "ZIP archive (*.zip)")
        if not path:
            return
        try:
            export_carousel(slides, Path(path), self.carousel.currentText())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Carousel exported",
                                "Ordered PNGs and manifest saved. Upload manually where supported.")
