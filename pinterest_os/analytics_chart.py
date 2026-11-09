"""Dependency-free Qt chart for imported daily Pinterest metrics."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class MetricsChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.metric_index = 1
        self.setMinimumHeight(190)

    def set_data(self, rows, metric_index=1):
        self.rows = list(rows)
        self.metric_index = metric_index
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(self.foregroundRole())
        painter.setPen(color)
        bounds = self.rect().adjusted(55, 15, -20, -35)
        if bounds.width() < 10 or bounds.height() < 10:
            return
        if not self.rows:
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, "No imported data")
            return
        values = [int(row[self.metric_index]) for row in self.rows]
        maximum = max(values) or 1
        painter.drawText(4, 24, str(maximum))
        painter.drawText(4, bounds.bottom(), "0")
        painter.drawText(bounds.left(), self.height() - 8, str(self.rows[0][0]))
        painter.drawText(bounds.right() - 95, self.height() - 8, str(self.rows[-1][0]))
        painter.drawLine(bounds.bottomLeft(), bounds.bottomRight())
        painter.drawLine(bounds.topLeft(), bounds.bottomLeft())
        painter.setPen(QPen(QColor("#168a70"), 2))
        points = []
        for i, value in enumerate(values):
            x = bounds.left() + round(i * bounds.width() / max(1, len(values) - 1))
            y = bounds.bottom() - round(value * bounds.height() / maximum)
            points.append((x, y))
        if len(points) == 1:
            painter.drawEllipse(points[0][0] - 3, points[0][1] - 3, 6, 6)
        else:
            for previous, current in zip(points, points[1:]):
                painter.drawLine(*previous, *current)
        painter.end()
