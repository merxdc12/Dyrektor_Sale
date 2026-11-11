"""Offline carousel composer from existing exported pin PNG assets."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QMessageBox, QPushButton, QVBoxLayout, QWidget, QListView, QListWidgetItem,
    QSizePolicy,
)

from .carousel_logic import export_carousel, validate_slides
from .carousel_viewer import CarouselViewer


class CarouselPage(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        title = QLabel("Конструктор каруселі")
        title.setObjectName("carouselTitle")
        subtitle = QLabel("Створюйте впорядковану Pinterest-карусель з уже підготовлених PNG-пінів. Публікація залишається ручною.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("carouselSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        header = QHBoxLayout()
        header.addWidget(QLabel("Карусель:"))
        self.carousel = QComboBox()
        self.carousel.currentIndexChanged.connect(self.reload_slides)
        header.addWidget(self.carousel, 1)
        self.new_carousel_button = QPushButton("+ Нова карусель")
        self.new_carousel_button.clicked.connect(self.create_carousel)
        header.addWidget(self.new_carousel_button)
        layout.addLayout(header)
        self.slides = QListWidget()
        self.slides.setVisible(False)  # internal selection model; storyboard is the visible selector
        self.slides.currentRowChanged.connect(self.update_preview)
        layout.addWidget(self.slides)
        workspace = QHBoxLayout()
        workspace.setSpacing(14)
        storyboard_column = QVBoxLayout()
        self.storyboard_title = QLabel("Порядок слайдів")
        self.storyboard_title.setObjectName("carouselSectionLabel")
        storyboard_column.addWidget(self.storyboard_title)
        self.storyboard = QListWidget()
        self.storyboard.setObjectName("storyboard")
        self.storyboard.setViewMode(QListView.ViewMode.IconMode)
        self.storyboard.setFlow(QListView.Flow.LeftToRight)
        self.storyboard.setWrapping(True)
        self.storyboard.setIconSize(QSize(92, 125))
        self.storyboard.setGridSize(QSize(122, 150))
        self.storyboard.setMinimumHeight(170)
        self.storyboard.setMaximumHeight(230)
        self.storyboard.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.storyboard.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.storyboard.currentRowChanged.connect(self.slides.setCurrentRow)
        self.slides.currentRowChanged.connect(self.storyboard.setCurrentRow)
        storyboard_column.addWidget(self.storyboard, 1)
        workspace.addLayout(storyboard_column, 1)

        preview_column = QVBoxLayout()
        preview_column.setSpacing(6)
        preview_heading = QLabel("Попередній перегляд")
        preview_heading.setObjectName("carouselSectionLabel")
        preview_column.addWidget(preview_heading)
        preview_row = QHBoxLayout()
        preview_row.addStretch(1)
        self.preview_label = QLabel()
        self.preview_label.setObjectName("carouselPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setFixedSize(170, 255)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        preview_row.addWidget(self.preview_label)
        preview_row.addStretch(1)
        preview_column.addLayout(preview_row)
        self.slide_info = QLabel("Слайдів: 0")
        self.slide_info.setObjectName("carouselSlideInfo")
        self.slide_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_column.addWidget(self.slide_info)
        self.validation_status = QLabel("PNG: —")
        self.validation_status.setObjectName("carouselValidation")
        self.validation_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.validation_status.setWordWrap(True)
        preview_column.addWidget(self.validation_status)
        navigation = QHBoxLayout()
        navigation.addStretch(1)
        self.previous_button = QPushButton("←")
        self.previous_button.setToolTip("Попередній слайд")
        self.previous_button.setMaximumWidth(48)
        self.previous_button.clicked.connect(lambda: self.navigate(-1))
        self.fullscreen_button = QPushButton("Повноекранний")
        self.fullscreen_button.clicked.connect(self.show_fullscreen)
        self.next_button = QPushButton("→")
        self.next_button.setToolTip("Наступний слайд")
        self.next_button.setMaximumWidth(48)
        self.next_button.clicked.connect(lambda: self.navigate(1))
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.fullscreen_button)
        navigation.addWidget(self.next_button)
        navigation.addStretch(1)
        preview_column.addLayout(navigation)
        workspace.addLayout(preview_column)
        layout.addLayout(workspace, 1)
        buttons = QHBoxLayout()
        self.add_button = QPushButton("Додати пін з бібліотеки")
        self.add_button.clicked.connect(self.add_pin)
        self.remove_button = QPushButton("Видалити")
        self.remove_button.clicked.connect(self.remove_pin)
        self.move_left_button = QPushButton("← Перемістити ліворуч")
        self.move_left_button.clicked.connect(lambda: self.move_slide(-1))
        self.move_right_button = QPushButton("Перемістити праворуч →")
        self.move_right_button.clicked.connect(lambda: self.move_slide(1))
        self.export_button = QPushButton("Експортувати ZIP")
        self.export_button.clicked.connect(self.export_zip)
        for button in (self.add_button, self.remove_button, self.move_left_button, self.move_right_button, self.export_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.setStyleSheet("""
            #carouselTitle { font-size: 18px; font-weight: 700; }
            #carouselSubtitle { color: #aebdb4; font-size: 12px; }
            #carouselSectionLabel { color: #d7e6dd; font-size: 13px; font-weight: 700; }
            #carouselSlideInfo { color: #c9d5ce; font-size: 12px; }
            #carouselValidation { color: #9db3a5; font-size: 11px; }
            #carouselPreview { border: 1px solid #315442; border-radius: 8px; background: #07100b; color: #c9d5ce; font-size: 13px; padding: 10px; }
            QListWidget#storyboard { background: #09120d; border: 1px solid #294436; border-radius: 8px; }
            QListWidget::item:selected { background: #173c28; color: #e7fff0; border: 1px solid #42e58d; }
            QPushButton:disabled { color: #64756b; border-color: #304138; background: #111a15; }
        """)
        self.reload_carousels()

    def update_controls(self):
        carousel_exists = self.carousel.currentData() is not None
        count = self.slides.count()
        row = self.slides.currentRow()
        has_slides = count > 0
        has_selection = has_slides and 0 <= row < count
        self.slides.setVisible(False)
        self.storyboard_title.setVisible(has_slides)
        self.storyboard.setVisible(has_slides)
        self.add_button.setEnabled(carousel_exists)
        self.add_button.setText("Додати перший пін" if carousel_exists and not has_slides else "Додати пін з бібліотеки")
        self.fullscreen_button.setEnabled(has_slides)
        carousel_id = self.carousel.currentData()
        export_ready = False
        if has_slides and carousel_id is not None:
            export_ready = not validate_slides(self.storage.carousel_slides(carousel_id))
        self.export_button.setEnabled(export_ready)
        self.export_button.setToolTip("" if export_ready else "Експорт стане доступним, коли всі слайди матимуть валідні PNG однакового розміру.")
        if not has_slides:
            self.validation_status.setText("PNG: —")
        elif export_ready:
            self.validation_status.setText("PNG: OK • готово до експорту")
            self.validation_status.setStyleSheet("color:#42e58d")
        else:
            errors = validate_slides(self.storage.carousel_slides(carousel_id)) if carousel_id is not None else []
            reason = errors[0] if errors else "потрібна перевірка"
            self.validation_status.setText(f"PNG: не готово • {reason}")
            self.validation_status.setStyleSheet("color:#f4c45e")
        self.remove_button.setEnabled(has_selection)
        self.previous_button.setEnabled(has_selection and row > 0)
        self.next_button.setEnabled(has_selection and row < count - 1)
        self.move_left_button.setEnabled(has_selection and row > 0)
        self.move_right_button.setEnabled(has_selection and row < count - 1)

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
            self.update_preview(-1)
            self.update_controls()
            return
        for row in self.storage.carousel_slides(carousel_id):
            label = f'{row["position"]:02d} — {row["title"]}'
            if not row.get("png_path") or not Path(row["png_path"]).is_file():
                label += "  [PNG відсутній]"
            self.slides.addItem(label)
            thumbnail = QListWidgetItem(f'{row["position"]:02d}  {row["title"]}')
            thumbnail.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            path = row.get("png_path") or ""
            if path and Path(path).is_file():
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    thumbnail.setIcon(QIcon(pixmap.scaled(
                        QSize(110, 150), Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)))
            self.storyboard.addItem(thumbnail)
        if self.slides.count():
            self.slides.setCurrentRow(0)
        else:
            self.update_preview(-1)
        self.update_controls()

    def navigate(self, delta: int):
        if self.slides.count():
            row = max(0, min(self.slides.count() - 1, self.slides.currentRow() + delta))
            self.slides.setCurrentRow(row)

    def update_preview(self, row: int):
        carousel_id = self.carousel.currentData()
        slides = self.storage.carousel_slides(carousel_id) if carousel_id is not None else []
        if row < 0 or row >= len(slides):
            self.preview_label.clear()
            if self.carousel.currentData() is None:
                self.preview_label.setText("Створіть першу карусель, щоб почати роботу.")
                self.slide_info.setText("Карусель не вибрана")
            elif not slides:
                self.preview_label.setText("Слайдів ще немає.\n\nДодайте перший пін з бібліотеки, щоб почати карусель.")
                self.slide_info.setText("Слайдів: 0")
            else:
                self.preview_label.setText("Виберіть слайд для перегляду")
                self.slide_info.setText(f"Слайдів: {len(slides)}")
            self.update_controls()
            return
        slide = slides[row]
        self.slide_info.setText(f"Слайд {row + 1} з {len(slides)} — {slide['title']}")
        self.update_controls()
        path = slide.get("png_path") or ""
        pixmap = QPixmap(path) if path and Path(path).is_file() else QPixmap()
        if pixmap.isNull():
            self.preview_label.clear()
            self.preview_label.setText("PNG відсутній або не читається. Експортуйте цей пін повторно.")
            return
        self.preview_label.setPixmap(pixmap.scaled(
            QSize(150, 225), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def show_fullscreen(self):
        carousel_id = self.carousel.currentData()
        if carousel_id is None:
            QMessageBox.information(self, "Немає каруселі", "Спочатку створіть карусель.")
            return
        slides = self.storage.carousel_slides(carousel_id)
        if not slides:
            QMessageBox.information(self, "Немає слайдів", "Спочатку додайте слайди.")
            return
        viewer = CarouselViewer(slides, max(0, self.slides.currentRow()), self)
        viewer.exec()
        self.slides.setCurrentRow(viewer.index)

    def create_carousel(self):
        title, ok = QInputDialog.getText(self, "Нова карусель", "Назва каруселі:")
        if ok and title.strip():
            carousel_id = self.storage.create_carousel(title)
            self.reload_carousels()
            self.carousel.setCurrentIndex(self.carousel.findData(carousel_id))

    def _ids(self):
        return [row["pin_id"] for row in self.storage.carousel_slides(self.carousel.currentData())]

    def add_pin(self):
        carousel_id = self.carousel.currentData()
        if carousel_id is None:
            QMessageBox.information(self, "Створіть карусель", "Спочатку створіть карусель.")
            return
        existing = self._ids()
        options = [(f'#{p["id"]} — {p["title"]}', p["id"])
                   for p in self.storage.all("pins") if p["id"] not in existing]
        if not options:
            QMessageBox.information(self, "Немає пінів", "Немає доступних пінів для додавання.")
            return
        choice, ok = QInputDialog.getItem(self, "Додати пін", "Виберіть пін:",
                                          [name for name, _ in options], 0, False)
        if ok:
            selected = dict(options)[choice]
            try:
                self.storage.set_carousel_slides(carousel_id, existing + [selected])
            except ValueError as exc:
                QMessageBox.warning(self, "Не вдалося додати пін", str(exc))
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
            QMessageBox.information(self, "Створіть карусель", "Спочатку створіть карусель.")
            return
        slides = self.storage.carousel_slides(carousel_id)
        errors = validate_slides(slides)
        if errors:
            QMessageBox.warning(self, "Карусель не готова", "\n".join(errors))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Експорт каруселі", "carousel.zip",
                                               "ZIP-архів (*.zip)")
        if not path:
            return
        try:
            export_carousel(slides, Path(path), self.carousel.currentText())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Помилка експорту", str(exc))
            return
        QMessageBox.information(self, "Карусель експортована",
                                "Впорядковані PNG та manifest збережено. Завантажте їх вручну там, де це підтримується.")
