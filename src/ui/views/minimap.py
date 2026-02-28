"""
Minimap

VSCode-style minimap for hex view navigation.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


class Minimap(QWidget):
    """
    Minimap widget.

    Displays a miniature overview of the entire file for quick navigation.
    """

    # Signals
    position_clicked = pyqtSignal(float)  # Normalized position (0.0 - 1.0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = bytearray()
        self._file_size = 0
        self._scroll_position = 0.0  # 0.0 - 1.0
        self._visible_ratio = 0.1  # Ratio of visible area
        self._selection_start = -1
        self._selection_end = -1

        # Colors
        self._background_color = QColor("#1e1e1e")
        self._data_color = QColor("#4ec9b0")
        self._selection_color = QColor("#264f78")
        self._cursor_color = QColor("#d4d4d4")

        # Size
        self.setFixedWidth(80)

    def set_data(self, data: bytes):
        """Set data to display."""
        self._data = bytearray(data)
        self._file_size = len(data)
        self.update()

    def set_scroll_position(self, position: float):
        """Set scroll position (0.0 - 1.0)."""
        self._scroll_position = max(0.0, min(1.0, position))
        self.update()

    def set_visible_ratio(self, ratio: float):
        """Set visible area ratio."""
        self._visible_ratio = max(0.01, min(1.0, ratio))
        self.update()

    def set_selection(self, start: int, end: int):
        """Set selection range."""
        self._selection_start = start
        self._selection_end = end
        self.update()

    def clear_selection(self):
        """Clear selection."""
        self._selection_start = -1
        self._selection_end = -1
        self.update()

    def _get_color_for_byte(self, byte: int) -> QColor:
        """Get color for a byte based on its value."""
        # Different colors for different byte ranges
        if byte == 0:
            return QColor("#2d2d2d")  # Null bytes - dark
        elif 32 <= byte < 127:
            return QColor("#a9b7c6")  # ASCII printable - light
        elif byte < 32:
            return QColor("#6a9955")  # Control chars - green
        else:
            return QColor("#ce9178")  # High bytes - orange

    def paintEvent(self, event):
        """Paint the minimap."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Background
        painter.fillRect(0, 0, width, height, self._background_color)

        if self._file_size == 0:
            return

        # Calculate scale
        scale = height / self._file_size
        pixel_per_byte = scale

        # Draw data
        if pixel_per_byte >= 1:
            # Each byte is at least 1 pixel - draw individual bytes
            for i in range(min(self._file_size, height)):
                byte = self._data[i] if i < len(self._data) else 0
                color = self._get_color_for_byte(byte)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawRect(0, i, width, 1)
        else:
            # Compression needed - sample and draw
            bytes_per_pixel = int(1 / pixel_per_byte)
            for y in range(height):
                start = y * bytes_per_pixel
                end = min(start + bytes_per_pixel, self._file_size)

                if start >= self._file_size:
                    break

                # Average color for this range
                sample = self._data[start:min(end, len(self._data))]
                if sample:
                    avg = sum(sample) / len(sample)
                    color = self._get_color_for_byte(int(avg))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(color))
                    painter.drawRect(0, y, width, 1)

        # Draw selection
        if self._selection_start >= 0 and self._selection_end >= 0:
            sel_start_y = int(self._selection_start * scale)
            sel_end_y = int(self._selection_end * scale)
            painter.fillRect(0, sel_start_y, width, sel_end_y - sel_start_y + 1,
                          self._selection_color)

        # Draw viewport indicator
        viewport_height = int(height * self._visible_ratio)
        viewport_y = int(height * self._scroll_position)

        # Draw viewport rectangle
        painter.setPen(QPen(QColor("#858585"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, viewport_y, width - 1, viewport_height - 1)

        # Draw cursor position
        cursor_y = viewport_y + viewport_height // 2
        painter.setPen(QPen(self._cursor_color, 2))
        painter.drawLine(width - 5, cursor_y, width - 1, cursor_y)

    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            position = event.position().y() / self.height()
            self.position_clicked.emit(max(0.0, min(1.0, position)))

    def mouseMoveEvent(self, event):
        """Handle mouse move."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            position = event.position().y() / self.height()
            self.position_clicked.emit(max(0.0, min(1.0, position)))

    def minimumSizeHint(self):
        """Return minimum size hint."""
        return QSize(50, 100)

    def sizeHint(self):
        """Return size hint."""
        return QSize(80, 300)
