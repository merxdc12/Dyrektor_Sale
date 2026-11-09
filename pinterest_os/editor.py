"""Reusable local record editor for products, pins and boards."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QMessageBox, QPlainTextEdit, QVBoxLayout,
)

FIELDS = {
    "products": (("name", "Name"), ("target_url", "Destination URL"), ("category", "Category")),
    "boards": (("name", "Board name"), ("url", "Board URL"), ("description", "SEO description")),
    "pins": (
        ("title", "Title"), ("description", "SEO description"),
        ("destination_url", "Destination URL"), ("product_id", "Product"),
        ("board_id", "Board"), ("status", "Status"),
    ),
}


class RecordEditor(QDialog):
    def __init__(self, storage, table: str, record: dict | None = None, parent=None):
        super().__init__(parent)
        self.storage, self.table = storage, table
        self.record = record
        self.inputs = {}
        self.setWindowTitle(f"{'Edit' if record else 'New'} {table[:-1]}")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        for field, label in FIELDS[table]:
            if field in {"description"}:
                widget = QPlainTextEdit()
                widget.setPlainText(str((record or {}).get(field) or ""))
            elif field in {"product_id", "board_id", "status", "category"}:
                widget = QComboBox()
                if field == "status":
                    options = [(x, x) for x in ("DRAFT", "IN_REVIEW", "READY", "PUBLISHED")]
                elif field == "category":
                    options = [(x, x) for x in ("POD", "KDP", "DIGITAL", "FREE_TOOL", "OTHER")]
                else:
                    related = "products" if field == "product_id" else "boards"
                    name = "name"
                    options = [("None", None)] + [
                        (row[name], row["id"]) for row in storage.all(related)
                    ]
                for title, value in options:
                    widget.addItem(title, value)
                index = widget.findData((record or {}).get(field))
                if index >= 0:
                    widget.setCurrentIndex(index)
            else:
                widget = QLineEdit(str((record or {}).get(field) or ""))
            self.inputs[field] = widget
            form.addRow(label, widget)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        values = {}
        for field, widget in self.inputs.items():
            if isinstance(widget, QPlainTextEdit):
                values[field] = widget.toPlainText()
            elif isinstance(widget, QComboBox):
                values[field] = widget.currentData()
            else:
                values[field] = widget.text()
        try:
            if self.record:
                self.storage.update(self.table, self.record["id"], **values)
            else:
                self.storage.create(self.table, **values)
        except (ValueError, Exception) as exc:
            QMessageBox.warning(self, "Cannot save", str(exc))
            return
        self.accept()
