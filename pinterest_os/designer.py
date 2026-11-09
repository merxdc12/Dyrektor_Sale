"""ITHutir layered pin editor: editable Qt scene, templates and linked exports."""
from __future__ import annotations

import json
from pathlib import Path
import webbrowser
from .canva_bridge import project_to_svg, validate_canva_design_id

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QPen
from PyQt6.QtWidgets import (
    QComboBox, QColorDialog, QFileDialog, QFontComboBox, QFormLayout,
    QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsTextItem, QGraphicsView, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget, QListWidget,
)

WIDTH, HEIGHT = 1000, 1500
TEMPLATES = {
    "ITHutir Dark": {"background": "#0B1110", "foreground": "#43E58A"},
    "ITHutir Light": {"background": "#F3F8F4", "foreground": "#147D45"},
    "Minimal Black": {"background": "#000000", "foreground": "#FFFFFF"},
}


class LayerText(QGraphicsTextItem):
    def __init__(self, text, x, y, size, color, width=820, font="DejaVu Sans", align="center"):
        super().__init__(text)
        self.setTextWidth(width)
        self.setPos(x, y)
        self.setFont(QFont(font, size, QFont.Weight.Bold))
        self.setDefaultTextColor(QColor(color))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.set_alignment(align)

    def set_alignment(self, value):
        option = self.document().defaultTextOption()
        option.setAlignment({"left": Qt.AlignmentFlag.AlignLeft,
                             "center": Qt.AlignmentFlag.AlignCenter,
                             "right": Qt.AlignmentFlag.AlignRight}[value])
        self.document().setDefaultTextOption(option)
        self.align_value = value

    def to_dict(self):
        return {"kind": "text", "text": self.toPlainText(), "x": self.x(), "y": self.y(),
                "size": self.font().pointSize(), "font": self.font().family(),
                "color": self.defaultTextColor().name(), "width": self.textWidth(),
                "align": self.align_value, "z": self.zValue()}


class LayerImage(QGraphicsPixmapItem):
    def __init__(self, path, x=0, y=0, width=1000, height=1500):
        pix = QPixmap(path)
        if pix.isNull():
            raise ValueError(f"Cannot load image: {path}")
        super().__init__(pix.scaled(int(width), int(height),
                                    Qt.AspectRatioMode.IgnoreAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation))
        self.source_path = str(Path(path).resolve())
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

    def to_dict(self):
        return {"kind": "image", "path": self.source_path, "x": self.x(), "y": self.y(),
                "width": self.pixmap().width(), "height": self.pixmap().height(),
                "z": self.zValue()}


class PinDesigner(QWidget):
    def __init__(self, storage=None, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.background = "#0B1110"
        self.dirty = False
        self._loading = False
        self.scene = QGraphicsScene(0, 0, WIDTH, HEIGHT, self)
        self.scene.setSceneRect(0, 0, WIDTH, HEIGHT)
        self.scene.selectionChanged.connect(self.update_selection)
        self.scene.changed.connect(self.mark_dirty)
        layout = QHBoxLayout(self)
        left = QWidget()
        left.setMaximumWidth(290)
        form = QFormLayout(left)
        self.pin = QComboBox()
        form.addRow("Linked pin", self.pin)
        self.reload_pins()
        self.pin.currentIndexChanged.connect(self.on_pin_changed)
        load = QPushButton("Load pin project")
        load.clicked.connect(self.load_pin)
        form.addRow(load)
        self.template = QComboBox()
        self.template.addItems(TEMPLATES)
        form.addRow("Template", self.template)
        apply_template = QPushButton("Apply template")
        apply_template.clicked.connect(self.apply_template)
        form.addRow(apply_template)
        add_text = QPushButton("+ Text layer")
        add_text.clicked.connect(self.add_text)
        form.addRow(add_text)
        add_image = QPushButton("+ Image layer")
        add_image.clicked.connect(self.add_image)
        form.addRow(add_image)
        self.text = QLineEdit()
        self.text.editingFinished.connect(self.change_text)
        form.addRow("Selected text", self.text)
        self.font = QFontComboBox()
        self.font.currentFontChanged.connect(self.change_font)
        form.addRow("Font", self.font)
        self.size = QSpinBox()
        self.size.setRange(8, 240)
        self.size.setValue(48)
        self.size.valueChanged.connect(self.change_size)
        form.addRow("Font size", self.size)
        self.alignment = QComboBox()
        self.alignment.addItems(("left", "center", "right"))
        self.alignment.currentTextChanged.connect(self.change_alignment)
        form.addRow("Alignment", self.alignment)
        color = QPushButton("Text color")
        color.clicked.connect(self.change_color)
        form.addRow(color)
        raise_button = QPushButton("Bring forward")
        raise_button.clicked.connect(lambda: self.shift_layer(1))
        form.addRow(raise_button)
        lower_button = QPushButton("Send backward")
        lower_button.clicked.connect(lambda: self.shift_layer(-1))
        form.addRow(lower_button)
        remove = QPushButton("Delete selected layer")
        remove.clicked.connect(self.delete_selected)
        form.addRow(remove)
        self.layers_list = QListWidget()
        self.layers_list.setMaximumHeight(130)
        self.layers_list.currentRowChanged.connect(self.select_layer_row)
        form.addRow("Layers (top first)", self.layers_list)
        self.x_position = QSpinBox()
        self.x_position.setRange(-5000, 5000)
        self.x_position.valueChanged.connect(lambda value: self.set_position("x", value))
        form.addRow("X position", self.x_position)
        self.y_position = QSpinBox()
        self.y_position.setRange(-5000, 5000)
        self.y_position.valueChanged.connect(lambda value: self.set_position("y", value))
        form.addRow("Y position", self.y_position)
        self.zoom = QSpinBox()
        self.zoom.setRange(10, 300)
        self.zoom.setSuffix("%")
        self.zoom.setValue(100)
        self.zoom.valueChanged.connect(self.set_zoom)
        form.addRow("Zoom", self.zoom)
        preview = QPushButton("Preview at canvas size")
        preview.clicked.connect(self.preview)
        form.addRow(preview)
        self.dirty_label = QLabel("Saved / no pending changes")
        form.addRow(self.dirty_label)
        save = QPushButton("Save editable project")
        save.clicked.connect(self.save_project)
        form.addRow(save)
        export = QPushButton("Export PNG + link to pin")
        export.setObjectName("Primary")
        export.clicked.connect(self.export_png)
        form.addRow(export)
        canva_export = QPushButton("Export editable SVG for Canva")
        canva_export.clicked.connect(self.export_canva_svg)
        form.addRow(canva_export)
        open_canva = QPushButton("Open Canva")
        open_canva.clicked.connect(lambda: webbrowser.open("https://www.canva.com/"))
        form.addRow(open_canva)
        self.canva_id = QLineEdit()
        self.canva_id.setPlaceholderText("Canva design ID (D...)")
        form.addRow("Canva design ID", self.canva_id)
        link_canva = QPushButton("Link Canva design to pin")
        link_canva.clicked.connect(self.link_canva)
        form.addRow(link_canva)
        layout.addWidget(left)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        layout.addWidget(self.view, 1)
        self.reset_scene()
        self.apply_template()
        self.dirty = False
        self.dirty_label.setText("Saved / no pending changes")

    def mark_dirty(self, *_args):
        if not self._loading and hasattr(self, "dirty_label"):
            self.dirty = True
            self.dirty_label.setText("Unsaved changes")

    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        return QMessageBox.question(
            self, "Unsaved design", "Discard unsaved design changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def on_pin_changed(self, _index):
        # Selection alone does not load or discard the current canvas.
        if self.dirty:
            self.dirty_label.setText("Unsaved changes — save before loading another pin")

    def refresh_layers(self):
        if not hasattr(self, "layers_list"):
            return
        items = [x for x in self.scene.items() if isinstance(x, (LayerText, LayerImage))]
        self.layers_list.blockSignals(True)
        self.layers_list.clear()
        for item in items:
            name = item.toPlainText()[:35] if isinstance(item, LayerText) else Path(item.source_path).name
            self.layers_list.addItem(("Text: " if isinstance(item, LayerText) else "Image: ") + name)
            if item.isSelected():
                self.layers_list.setCurrentRow(len(items) - 1 if False else items.index(item))
        self.layers_list.blockSignals(False)

    def select_layer_row(self, row):
        items = [x for x in self.scene.items() if isinstance(x, (LayerText, LayerImage))]
        if 0 <= row < len(items):
            self.scene.clearSelection()
            items[row].setSelected(True)

    def set_position(self, axis, value):
        item = self.selected()
        if isinstance(item, (LayerText, LayerImage)):
            if axis == "x":
                item.setX(value)
            else:
                item.setY(value)
            self.mark_dirty()

    def set_zoom(self, _value):
        self.fit()

    def preview(self):
        image = self.render_image()
        from PyQt6.QtWidgets import QDialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Pin preview — {WIDTH} × {HEIGHT}")
        dialog.resize(540, 740)
        layout = QVBoxLayout(dialog)
        display = QLabel()
        display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        display.setPixmap(QPixmap.fromImage(image).scaled(
            480, 650, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(display)
        dialog.exec()

    def render_image(self):
        image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.scene.render(painter, QRectF(0, 0, WIDTH, HEIGHT), self.scene.sceneRect())
        painter.end()
        return image

    def reload_pins(self):
        old = self.pin.currentData()
        self.pin.clear()
        if self.storage:
            for row in self.storage.all("pins"):
                self.pin.addItem(f"#{row['id']} {row['title']}", row["id"])
        found = self.pin.findData(old)
        if found >= 0:
            self.pin.setCurrentIndex(found)

    def selected(self):
        return next(iter(self.scene.selectedItems()), None)

    def update_selection(self):
        item = self.selected()
        self.refresh_layers()
        for widget, value in ((self.x_position, round(item.x()) if item else 0),
                              (self.y_position, round(item.y()) if item else 0)):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        if not isinstance(item, LayerText):
            return
        self.text.blockSignals(True)
        self.font.blockSignals(True)
        self.size.blockSignals(True)
        self.alignment.blockSignals(True)
        self.text.setText(item.toPlainText())
        self.font.setCurrentFont(item.font())
        self.size.setValue(item.font().pointSize())
        self.alignment.setCurrentText(item.align_value)
        for widget in (self.text, self.font, self.size, self.alignment):
            widget.blockSignals(False)

    def reset_scene(self):
        self.scene.clear()
        self.background_item = QGraphicsRectItem(0, 0, WIDTH, HEIGHT)
        self.background_item.setPen(QPen(Qt.PenStyle.NoPen))
        self.background_item.setBrush(QColor(self.background))
        self.background_item.setZValue(-10000)
        self.scene.addItem(self.background_item)

    def apply_template(self):
        template = TEMPLATES[self.template.currentText()]
        if hasattr(self, "dirty_label") and not self.confirm_discard():
            return
        self.background = template["background"]
        self.reset_scene()
        self.scene.addItem(LayerText("BUILD SMARTER", 90, 350, 66, template["foreground"]))
        self.scene.addItem(LayerText("ITHutir • Engineering & DIY", 90, 1070, 30, template["foreground"]))
        self.scene.addItem(LayerText("ITHUTIR", 90, 1370, 25, template["foreground"]))
        self.fit()

    def fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.view.scale(self.zoom.value() / 100, self.zoom.value() / 100)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()

    def add_text(self):
        item = LayerText("New text", 100, 200, 45, "#43E58A")
        self.scene.addItem(item)
        self.scene.clearSelection()
        item.setSelected(True)

    def add_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Add image layer", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            try:
                self.scene.addItem(LayerImage(path, 100, 300, 800, 800))
            except ValueError as exc:
                QMessageBox.warning(self, "Image error", str(exc))

    def change_text(self):
        item = self.selected()
        if isinstance(item, LayerText):
            item.setPlainText(self.text.text())

    def change_font(self, font):
        item = self.selected()
        if isinstance(item, LayerText):
            old = item.font()
            old.setFamily(font.family())
            item.setFont(old)

    def change_size(self, size):
        item = self.selected()
        if isinstance(item, LayerText):
            font = item.font()
            font.setPointSize(size)
            item.setFont(font)

    def change_alignment(self, align):
        item = self.selected()
        if isinstance(item, LayerText):
            item.set_alignment(align)

    def change_color(self):
        item = self.selected()
        if isinstance(item, LayerText):
            color = QColorDialog.getColor(item.defaultTextColor(), self)
            if color.isValid():
                item.setDefaultTextColor(color)

    def shift_layer(self, amount):
        item = self.selected()
        if item:
            item.setZValue(item.zValue() + amount)

    def delete_selected(self):
        item = self.selected()
        if item and item is not self.background_item:
            self.scene.removeItem(item)

    def project(self):
        layers = []
        for item in self.scene.items(Qt.SortOrder.AscendingOrder):
            if isinstance(item, (LayerText, LayerImage)):
                layers.append(item.to_dict())
        return {"version": 1, "width": WIDTH, "height": HEIGHT,
                "background": self.background, "layers": layers}

    def restore(self, project):
        if project.get("version") != 1 or project.get("width") != WIDTH or project.get("height") != HEIGHT:
            raise ValueError("Unsupported project format")
        layers = project.get("layers")
        if not isinstance(layers, list) or len(layers) > 200:
            raise ValueError("Invalid project layers")
        self.background = project.get("background", "#0B1110")
        self.reset_scene()
        for layer in layers:
            if layer["kind"] == "text":
                item = LayerText(layer["text"], layer["x"], layer["y"],
                                 layer["size"], layer["color"], layer.get("width", 820),
                                 layer.get("font", "DejaVu Sans"), layer.get("align", "center"))
            elif layer["kind"] == "image":
                asset_path = Path(layer["path"])
                if not asset_path.is_absolute() and self.storage is not None:
                    asset_path = self.storage.path.parent / asset_path
                item = LayerImage(str(asset_path), layer["x"], layer["y"],
                                  layer["width"], layer["height"])
            else:
                raise ValueError("Unknown layer type")
            item.setZValue(layer.get("z", 0))
            self.scene.addItem(item)
        self.fit()

    def save_project(self):
        pin_id = self.pin.currentData()
        if not self.storage or pin_id is None:
            QMessageBox.warning(self, "Select pin", "Create and select a pin in Pin Library first.")
            return
        try:
            self.storage.save_pin_design(pin_id, json.dumps(self.project(), ensure_ascii=False))
            self.dirty = False
            self.dirty_label.setText("Saved / no pending changes")
            QMessageBox.information(self, "Saved", "Editable project saved to SQLite.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Save failed", str(exc))

    def load_pin(self):
        if not self.confirm_discard():
            return
        pin_id = self.pin.currentData()
        data = self.storage.get_pin_design(pin_id) if self.storage and pin_id else None
        if not data:
            QMessageBox.information(self, "No project", "No saved design for this pin.")
            return
        try:
            self._loading = True
            try:
                self.restore(json.loads(data["project_json"]))
            finally:
                self._loading = False
            self.dirty = False
            self.dirty_label.setText("Saved / no pending changes")
            self.canva_id.setText(data.get("canva_design_id", ""))
        except (ValueError, KeyError, TypeError) as exc:
            QMessageBox.warning(self, "Cannot load", str(exc))

    def export_canva_svg(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export SVG for Canva", "ithutir-canva.svg", "SVG (*.svg)")
        if not path:
            return
        try:
            project_to_svg(self.project(), path)
            QMessageBox.information(
                self, "SVG exported",
                "Import this SVG in Canva. Text is stored as SVG text and images as separate SVG elements. "
                "Canva may flatten or alter them; verify editability in Canva.")
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "SVG export failed", str(exc))

    def link_canva(self):
        pin_id = self.pin.currentData()
        if not self.storage or pin_id is None:
            QMessageBox.warning(self, "Select pin", "Select a pin first.")
            return
        try:
            self.storage.set_canva_design_id(pin_id, self.canva_id.text().strip())
            QMessageBox.information(self, "Linked", "Canva design ID linked to pin.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Canva ID", str(exc))

    def export_png(self):
        pin_id = self.pin.currentData()
        if not self.storage or pin_id is None:
            QMessageBox.warning(self, "Select pin", "Select a pin before exporting.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export pin", f"ithutir-pin-{pin_id}.png", "PNG (*.png)")
        if not path:
            return
        image = self.render_image()
        if image.width() != WIDTH or image.height() != HEIGHT or not image.save(path, "PNG"):
            QMessageBox.warning(self, "Export failed", "Cannot save PNG.")
            return
        try:
            self.storage.save_pin_design(pin_id, json.dumps(self.project(), ensure_ascii=False),
                                         str(Path(path).resolve()))
            self.dirty = False
            self.dirty_label.setText("Saved / no pending changes")
        except Exception as exc:
            QMessageBox.warning(self, "Link failed", f"PNG saved but SQLite link failed: {exc}")
            return
        QMessageBox.information(self, "Exported", "PNG exported and linked to the selected pin.")
