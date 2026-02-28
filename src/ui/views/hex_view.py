"""
Hex View

Main hex view widget with virtual scrolling for efficient large file display.
"""

from PyQt6.QtWidgets import QAbstractItemDelegate, QTableView, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QStyle
from PyQt6.QtCore import Qt, QModelIndex, QRect, pyqtSignal, QSize, QAbstractTableModel, QVariant, QEvent

# Custom role for search highlight range
UserRole_HighlightRange = Qt.ItemDataRole.UserRole
# Custom role for selection highlight range
UserRole_SelectionRange = Qt.ItemDataRole.UserRole + 1
from PyQt6.QtGui import QPainter, QColor, QFont, QTextFormat, QPalette

import math


class OffsetRulerWidget(QWidget):
    """
    Horizontal offset ruler widget that shows position markers.
    Shows tick marks every 10 bytes with position labels.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._font = QFont("Menlo", 9)
        self._font.setStyleHint(QFont.StyleHint.Monospace)
        self._bytes_per_row = 16
        self._header_length = 0
        self._scroll_offset = 0
        self._column0_width = 300  # Default, will be updated
        self.setFixedHeight(20)
        self.setStyleSheet("background-color: #2d2d2d;")

    def set_bytes_per_row(self, bytes_per_row: int):
        """Set bytes per row."""
        self._bytes_per_row = bytes_per_row
        self.update()

    def set_header_length(self, header_length: int):
        """Set header length."""
        self._header_length = header_length
        self.update()

    def set_column_width(self, width: int):
        """Set column 0 width for accurate positioning."""
        self._column0_width = width
        self.update()

    def set_scroll_offset(self, offset: int):
        """Set horizontal scroll offset."""
        self._scroll_offset = offset
        self.update()

    def paintEvent(self, event):
        """Paint the ruler."""
        painter = QPainter(self)
        painter.setFont(self._font)

        # Colors
        bg_color = QColor("#2d2d2d")
        text_color = QColor("#888888")
        tick_color = QColor("#555555")

        painter.fillRect(self.rect(), bg_color)

        fm = painter.fontMetrics()

        bytes_per_row = max(1, self._bytes_per_row)

        # Get actual column positions from hex view
        parent = self.parent()
        if parent and hasattr(parent, '_hex_view'):
            hex_view = parent._hex_view
            # Calculate: byte_width = column_width / bytes_per_row
            # Then adjust to match actual data spacing
            # Reduce to match data interval
            byte_width = hex_view.columnWidth(0) / bytes_per_row * 0.70
            # Offset to first data byte
            offset_width = byte_width * 0.8
        else:
            # Fallback calculation
            total_chars = 10 + bytes_per_row * 3
            byte_width = (self._column0_width / total_chars) * 3
            offset_width = (8 / total_chars) * self._column0_width

        # Debug info removed

        # Draw only major ticks every 10 bytes
        tick_interval = 10

        # For now, draw ticks at fixed positions based on percentage
        # Just show labels at positions 0, 10, 20, 30...
        for i in range(0, bytes_per_row + 1, tick_interval):
            # Position as percentage of data area
            pos_ratio = i / bytes_per_row if bytes_per_row > 0 else 0
            x_pos = pos_ratio * hex_view.columnWidth(0) - self._scroll_offset

            if -50 < x_pos < self.width() + 50:
                # Draw tick mark
                painter.setPen(tick_color)
                painter.drawLine(int(x_pos), 15, int(x_pos), 20)

                # Draw label
                painter.setPen(text_color)
                label = f"{i}"
                label_width = fm.horizontalAdvance(label)
                painter.drawText(int(x_pos - label_width / 2), 10, label)


class HexTableModel(QAbstractTableModel):
    """
    Table model for hex view.

    Provides virtual scrolling for large files.
    """

    # Display modes
    MODE_HEX = "hex"
    MODE_BINARY = "binary"
    MODE_OCTAL = "octal"
    MODE_ASCII = "ascii"

    # Highlight color for search results
    HIGHLIGHT_COLOR = QColor("#515c6a")
    HIGHLIGHT_CURRENT_COLOR = QColor("#614d00")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = bytearray()
        self._file_size = 0
        self._bytes_per_row = 32
        self._header_length = 0
        self._start_offset = 0
        self._display_mode = self.MODE_HEX

        # Arrangement mode: "equal_frame" or "header_length"
        self._arrangement_mode = "equal_frame"

        # Search highlight
        self._search_results = []  # List of (offset, length)
        self._current_result_index = -1

        # Selection highlight - stores list of (start, end) byte ranges
        self._selection_ranges = []  # List of (start_offset, end_offset) tuples

        # Cached values
        self._row_count = 0

    def set_data(self, data: bytes):
        """Set data to display."""
        self.beginResetModel()
        self._data = bytearray(data)
        self._file_size = len(data)
        self._update_row_count()
        self.endResetModel()

    def set_bytes_per_row(self, value: int):
        """Set bytes per row for equal frame mode."""
        if value != self._bytes_per_row:
            self.beginResetModel()
            self._bytes_per_row = value
            self._update_row_count()
            self.endResetModel()

    def set_arrangement_mode(self, mode: str, param: int = 32):
        """Set arrangement mode.

        Args:
            mode: "equal_frame" or "header_length"
            param: For equal_frame, this is bytes per row (1-65535).
                   For header_length, this is header length in bytes (1-8).
        """
        self.beginResetModel()
        self._arrangement_mode = mode

        if mode == "header_length":
            # In header length mode, the parameter is header length
            self._header_length = param
            # For header length mode, we calculate row count dynamically
            self._update_row_count()
        elif mode == "equal_frame":
            # In equal frame mode, the parameter is bytes per row
            self._header_length = 0
            self._bytes_per_row = param
            self._update_row_count()

        self.endResetModel()

    def set_start_offset(self, offset: int):
        """Set starting offset for display."""
        self._start_offset = offset

    def _update_row_count(self):
        """Update row count based on arrangement mode."""
        if self._file_size == 0:
            self._row_count = 0
        elif self._arrangement_mode == "equal_frame":
            # 等长帧模式：每行固定字节数
            self._row_count = (self._file_size + self._bytes_per_row - 1) // self._bytes_per_row
        elif self._arrangement_mode == "header_length":
            # 头长度模式：需要逐行计算
            count = 0
            offset = 0
            header_len = self._header_length
            max_rows = 100000  # 防止无限循环
            while offset < self._file_size and count < max_rows:
                if offset + header_len > self._file_size:
                    break
                # 读取头部的长度值
                header_bytes = self._data[offset:offset + header_len]
                try:
                    data_len = int.from_bytes(header_bytes, byteorder='big')
                except:
                    data_len = 0
                # 如果 data_len 为 0，跳到下一行（添加一个默认长度）
                if data_len == 0:
                    data_len = 1
                offset += header_len + data_len
                count += 1
            self._row_count = count

    def _get_row_offset(self, row: int) -> int:
        """Get the file offset for a specific row in header length mode."""
        if row < 0:
            return 0

        offset = 0
        header_len = self._header_length
        max_rows = 100000  # 防止无限循环

        for i in range(min(row, max_rows)):
            if offset >= self._file_size:
                return self._file_size
            if offset + header_len > self._file_size:
                return offset
            header_bytes = self._data[offset:offset + header_len]
            try:
                data_len = int.from_bytes(header_bytes, byteorder='big')
            except:
                data_len = 0
            # 如果 data_len 为 0，跳到下一行（添加一个默认长度）
            if data_len == 0:
                data_len = 1
            offset += header_len + data_len

        return offset

    def rowCount(self, parent=QModelIndex()):
        """Return number of rows."""
        return self._row_count

    def columnCount(self, parent=QModelIndex()):
        """Return number of columns."""
        # Offset column + bytes per row + ASCII column
        return 2

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Return data for index and role."""
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # Calculate offset for this row based on arrangement mode
        if self._arrangement_mode == "equal_frame":
            # 等长帧模式：每行固定字节数
            total_per_row = self._bytes_per_row
            row_offset = row * total_per_row + self._start_offset
            row_end_offset = min(row_offset + total_per_row, self._file_size)
        else:
            # 头长度模式：逐行计算偏移
            row_offset = self._get_row_offset(row) + self._start_offset
            if row_offset >= self._file_size:
                return None
            # 获取该行的数据长度
            header_len = self._header_length
            if row_offset + header_len > self._file_size:
                row_end_offset = self._file_size
            else:
                header_bytes = self._data[row_offset:row_offset + header_len]
                try:
                    data_len = int.from_bytes(header_bytes, byteorder='big')
                except:
                    data_len = 0
                # 如果 data_len 为 0，使用默认最小值
                if data_len == 0:
                    data_len = 1
                row_end_offset = min(row_offset + header_len + data_len, self._file_size)

        if row_offset >= self._file_size:
            return None

        # For highlighting, calculate data position in the row
        if self._arrangement_mode == "header_length":
            data_row_offset = row_offset + self._header_length
        else:
            data_row_offset = row_offset

        # Check for selection highlight - handle multiple selection ranges
        selection_range = None  # (start_byte_pos, end_byte_pos) in this row

        # Calculate the data byte range for this row
        row_data_start = data_row_offset
        row_data_end = row_end_offset

        # Check each selection range
        for sel_start, sel_end in self._selection_ranges:
            # Check if this row overlaps with selection
            if row_data_end > sel_start and row_data_start < sel_end + 1:
                # Calculate the byte range in this row that needs highlighting
                sel_byte_start = sel_start - row_data_start
                sel_byte_end = sel_end - row_data_start + 1

                # Make sure we don't go negative or beyond row
                if sel_byte_start < 0:
                    sel_byte_start = 0

                # Calculate row data length
                row_data_length = row_data_end - row_data_start
                if sel_byte_end > row_data_length:
                    sel_byte_end = row_data_length

                if sel_byte_end > sel_byte_start:
                    # For now, just take the first overlapping range
                    # Could be enhanced to handle multiple ranges
                    selection_range = (sel_byte_start, sel_byte_end)
                    break

        # Check for search highlight - only highlight current result bytes
        highlight_range = None  # (start_byte_pos, end_byte_pos) in this row
        # Only show search highlight if there's no selection
        if not selection_range and self._search_results and self._current_result_index >= 0:
            result_offset, result_length = self._search_results[self._current_result_index]
            result_end = result_offset + result_length
            # Check if this row overlaps with the current result
            if row_offset < result_end and row_end_offset > result_offset:
                # Calculate the byte range in this row that needs highlighting
                highlight_start = result_offset - data_row_offset
                highlight_end = highlight_start + result_length

                # Make sure we don't go negative or beyond row
                if highlight_start < 0:
                    highlight_start = 0

                # Calculate row data length
                row_data_length = row_end_offset - data_row_offset
                if highlight_end > row_data_length:
                    highlight_end = row_data_length

                if highlight_end > highlight_start:
                    highlight_range = (highlight_start, highlight_end)

        # Column 0: Offset + Hex bytes
        if col == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._get_hex_row(row_offset, row_end_offset)
            elif role == Qt.ItemDataRole.BackgroundRole:
                return QColor("#1e1e1e")
            elif role == Qt.ItemDataRole.ForegroundRole:
                return QColor("#d4d4d4")
            elif role == UserRole_HighlightRange:
                return QVariant(highlight_range)
            elif role == UserRole_SelectionRange:
                return QVariant(selection_range)

        # Column 1: ASCII representation
        elif col == 1:
            if role == Qt.ItemDataRole.DisplayRole:
                return self._get_ascii_row(row_offset, row_end_offset)
            elif role == Qt.ItemDataRole.BackgroundRole:
                return QColor("#1e1e1e")
            elif role == Qt.ItemDataRole.ForegroundRole:
                return QColor("#a9b7c6")
            elif role == UserRole_HighlightRange:
                return QVariant(highlight_range)
            elif role == UserRole_SelectionRange:
                return QVariant(selection_range)

        return None

    def set_display_mode(self, mode: str):
        """Set display mode (hex, binary, octal, ascii)."""
        if mode != self._display_mode:
            self._display_mode = mode
            self.beginResetModel()
            self.endResetModel()

    def set_search_results(self, results, current_index=-1):
        """Set search results for highlighting."""
        # Convert SearchResult objects to (offset, length) tuples
        self._search_results = [(r.offset, r.length) for r in results] if results else []
        self._current_result_index = current_index
        self.dataChanged.emit(self.index(0, 0), self.index(self._row_count - 1, 1))

    def clear_search_results(self):
        """Clear search highlights."""
        self._search_results = []
        self._current_result_index = -1
        self.dataChanged.emit(self.index(0, 0), self.index(self._row_count - 1, 1))

    def set_selection_ranges(self, ranges: list):
        """Set selection ranges for highlighting.

        Args:
            ranges: List of (start_offset, end_offset) tuples
        """
        self._selection_ranges = ranges
        self.dataChanged.emit(self.index(0, 0), self.index(self._row_count - 1, 1))

    def set_selection(self, start: int, end: int):
        """Set single selection for highlighting (backward compatible)."""
        self._selection_ranges = [(start, end)]
        self.dataChanged.emit(self.index(0, 0), self.index(self._row_count - 1, 1))

    def clear_selection_highlight(self):
        """Clear selection highlight."""
        self._selection_ranges = []
        self.dataChanged.emit(self.index(0, 0), self.index(self._row_count - 1, 1))

    def _get_hex_row(self, row_offset: int, row_end_offset: int = None) -> str:
        """Get hex string for row."""
        if row_end_offset is None:
            total_per_row = self._bytes_per_row + self._header_length
            row_end_offset = min(row_offset + total_per_row, self._file_size)

        parts = []

        # Offset (always in hex)
        parts.append(f"{row_offset:08X}  ")

        # Header bytes (if any) - always hex for now
        if self._header_length > 0:
            header_end = min(row_offset + self._header_length, self._file_size)
            header_len = header_end - row_offset
            if header_len > 0:
                header_bytes = self._data[row_offset:header_end]
                hex_str = ' '.join(f"{b:02X}" for b in header_bytes)
                # Calculate padding width safely
                padding_width = max(0, self._header_length * 3 - 1)
                hex_str = hex_str.ljust(padding_width)
                parts.append(hex_str)
                parts.append(" ")

        # Data bytes - use actual data length for this row
        data_start = row_offset + self._header_length
        data_end = row_end_offset
        data_bytes_len = max(0, data_end - data_start)

        if data_start < self._file_size and data_bytes_len > 0:
            data_bytes = self._data[data_start:data_end]
            data_bytes_len = len(data_bytes)

            if self._display_mode == self.MODE_HEX:
                hex_str = ' '.join(f"{b:02X}" for b in data_bytes)
                # Pad to bytes_per_row width (safe calculation)
                padding_width = max(0, self._bytes_per_row * 3 - 1)
                hex_str = hex_str.ljust(padding_width)
                parts.append(hex_str)
            elif self._display_mode == self.MODE_BINARY:
                # Binary: 8 bits per byte, grouped
                bin_str = ' '.join(f"{b:08b}" for b in data_bytes)
                parts.append(bin_str)
            elif self._display_mode == self.MODE_OCTAL:
                # Octal: 3 digits per byte
                oct_str = ' '.join(f"{b:03o}" for b in data_bytes)
                padding_width = max(0, self._bytes_per_row * 4 - 1)
                oct_str = oct_str.ljust(padding_width)
                parts.append(oct_str)
            elif self._display_mode == self.MODE_ASCII:
                # Just show spaces for ASCII mode in hex column
                padding_width = max(0, self._bytes_per_row * 3 - 1)
                parts.append(' ' * padding_width)

        return ''.join(parts)

    def _get_ascii_row(self, row_offset: int, row_end_offset: int = None) -> str:
        """Get ASCII string for row."""
        if row_end_offset is None:
            total_per_row = self._bytes_per_row + self._header_length
            row_end_offset = min(row_offset + total_per_row, self._file_size)

        data_start = row_offset + self._header_length
        data_end = row_end_offset

        if data_start >= self._file_size:
            return ""

        data_bytes = self._data[data_start:data_end]

        if self._display_mode == self.MODE_ASCII:
            # Full ASCII display
            return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data_bytes)
        else:
            # Standard ASCII representation
            return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data_bytes)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        """Return header data."""
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == 0:
                    return "Offset + Hex Data"
                elif section == 1:
                    return "ASCII"
        return None


class HexViewDelegate(QAbstractItemDelegate):
    """
    Delegate for rendering hex view cells.
    """

    # Highlight colors
    HIGHLIGHT_COLOR = QColor("#614d00")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._font = QFont("Menlo", 11)
        if hasattr(self._font, 'setStyleHint'):
            self._font.setStyleHint(QFont.StyleHint.Monospace)

    def paint(self, painter, option, index):
        """Paint cell."""
        painter.save()

        # Set font
        painter.setFont(self._font)

        # Get data
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text is None:
            painter.restore()
            return

        # Set colors
        bg_color = index.data(Qt.ItemDataRole.BackgroundRole)
        fg_color = index.data(Qt.ItemDataRole.ForegroundRole)
        highlight_range = index.data(UserRole_HighlightRange)
        selection_range = index.data(UserRole_SelectionRange)

        rect = option.rect

        # Check if this is continuous selection mode (byte-level selection)
        is_continuous_mode = hasattr(self, '_selection_mode') and getattr(self, '_selection_mode', None) == 'continuous'
        
        # In continuous mode, prefer byte-level highlight over cell selection
        if option.state & QStyle.StateFlag.State_Selected and (selection_range or is_continuous_mode):
            # For continuous mode, show byte-level highlight instead of cell highlight
            if selection_range and is_continuous_mode:
                # Draw background first
                if bg_color:
                    painter.fillRect(rect, bg_color)
                if fg_color:
                    painter.setPen(fg_color)
                
                # Draw byte-level highlight
                start_byte, end_byte = selection_range
                display_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
                fm = painter.fontMetrics()

                if index.column() == 0:
                    # Hex format
                    offset_chars = 10
                    hex_byte_start = offset_chars + start_byte * 3
                    if hex_byte_start <= len(display_text):
                        prefix = display_text[:hex_byte_start]
                        byte_x = fm.horizontalAdvance(prefix)
                    else:
                        byte_x = fm.horizontalAdvance(display_text)

                    hex_byte_end = offset_chars + end_byte * 3
                    if hex_byte_end <= len(display_text):
                        full = display_text[:hex_byte_end]
                        byte_width = fm.horizontalAdvance(full) - byte_x
                    else:
                        byte_width = fm.horizontalAdvance(display_text[hex_byte_start:]) if hex_byte_start < len(display_text) else 0

                    highlight_rect = QRect(int(byte_x), rect.y(), max(int(byte_width), 1), rect.height())
                    painter.fillRect(highlight_rect, QColor("#3a3d41"))
                else:
                    # ASCII column
                    prefix = display_text[:start_byte] if start_byte <= len(display_text) else display_text
                    byte_x = fm.horizontalAdvance(prefix)
                    full = display_text[:end_byte] if end_byte <= len(display_text) else display_text
                    byte_width = fm.horizontalAdvance(full) - byte_x
                    highlight_rect = QRect(int(byte_x), rect.y(), max(int(byte_width), 1), rect.height())
                    painter.fillRect(highlight_rect, QColor("#3a3d41"))
                
                # Set text color
                painter.setPen(QColor("#ffffff"))
                painter.restore()
                return
            else:
                # Non-continuous mode: use default cell selection
                painter.fillRect(rect, QColor("#264f78"))
                painter.setPen(QColor("#ffffff"))
        elif option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor("#264f78"))
            painter.setPen(QColor("#ffffff"))
        else:
            # Draw background first
            if bg_color:
                painter.fillRect(rect, bg_color)
            if fg_color:
                painter.setPen(fg_color)

            # Draw highlight for selected bytes BEFORE drawing text
            # Priority: selection highlight > search highlight
            active_range = selection_range if selection_range else highlight_range
            active_color = QColor("#3a3d41") if selection_range else self.HIGHLIGHT_COLOR

            if active_range:
                start_byte, end_byte = active_range
                display_text = index.data(Qt.ItemDataRole.DisplayRole) or ""
                fm = painter.fontMetrics()

                if index.column() == 0:
                    # Hex format: "00000000  XX XX XX..."
                    # Offset: 8 chars + 2 spaces = 10 chars
                    # Each byte: 3 chars (2 hex + 1 space)
                    offset_chars = 10
                    hex_byte_start = offset_chars + start_byte * 3

                    # Measure width up to the start position
                    if hex_byte_start <= len(display_text):
                        prefix = display_text[:hex_byte_start]
                        byte_x = fm.horizontalAdvance(prefix)
                    else:
                        byte_x = fm.horizontalAdvance(display_text)

                    # Measure width of the highlighted portion
                    hex_byte_end = offset_chars + end_byte * 3
                    if hex_byte_end <= len(display_text):
                        full = display_text[:hex_byte_end]
                        byte_width = fm.horizontalAdvance(full) - byte_x
                    else:
                        byte_width = fm.horizontalAdvance(display_text[hex_byte_start:]) if hex_byte_start < len(display_text) else 0

                    highlight_rect = QRect(int(byte_x), rect.y(), max(int(byte_width), 1), rect.height())
                    painter.fillRect(highlight_rect, active_color)
                else:
                    # ASCII column
                    prefix = display_text[:start_byte] if start_byte <= len(display_text) else display_text
                    byte_x = fm.horizontalAdvance(prefix)

                    full = display_text[:end_byte] if end_byte <= len(display_text) else display_text
                    byte_width = fm.horizontalAdvance(full) - byte_x

                    highlight_rect = QRect(int(byte_x), rect.y(), max(int(byte_width), 1), rect.height())
                    painter.fillRect(highlight_rect, active_color)

        # Draw text (always draw, on top of background and highlight)
        text_rect = rect.adjusted(5, 0, -5, 0)
        painter.drawText(text_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        text)

        painter.restore()

    def sizeHint(self, option, index):
        """Return cell size hint."""
        # Column 0: Offset + Hex (dynamic width)
        # Column 1: ASCII (will stretch)
        if index.column() == 0:
            # Return a reasonable minimum width for offset + hex column
            return QSize(400, 18)
        else:
            # ASCII column will stretch
            return QSize(100, 18)


class HexView(QTableView):
    """
    Hex view widget.

    Displays binary data in hex and ASCII format with virtual scrolling.
    """

    # Selection modes
    SELECTION_ROW = "row"           # Select entire rows
    SELECTION_COLUMN = "column"      # Select entire columns
    SELECTION_CONTINUOUS = "continuous"  # Continuous selection (default)
    SELECTION_BLOCK = "block"        # Block/rectangular selection

    # Signals
    cursor_moved = pyqtSignal(int)  # Current offset
    selection_changed = pyqtSignal(int, int)  # Start, end of selection

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_handle = None

        # Selection mode
        self._selection_mode = self.SELECTION_CONTINUOUS

        # Block selection state
        self._block_start_offset = -1
        self._block_start_row = -1
        self._block_start_col = -1

        # Column selection state
        self._column_byte_pos = -1
        self._block_start_byte_pos = -1  # Store start byte position for block/continuous selection
        self._continuous_end_byte_pos = -1  # Store end byte position for continuous selection

        # Setup model and delegate
        self._model = HexTableModel(self)
        self.setModel(self._model)

        self._delegate = HexViewDelegate(self)
        self.setItemDelegate(self._delegate)

        # Setup appearance
        self.setShowGrid(False)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)
        # Hide horizontal header (we use custom ruler instead)
        self.horizontalHeader().setVisible(False)

        # Optimize for performance
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)

        # Set row height
        self.verticalHeader().setDefaultSectionSize(18)

        # Style
        self.setStyleSheet("""
            QTableView {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
            QTableView::item {
                padding: 0 5px;
            }
            QTableView::item:selected {
                background-color: #264f78;
                color: #ffffff;
            }
        """)

        # Calculate font width for column sizing
        self._font_width = 8.5  # Approximate width for Menlo 11pt

        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Connect selection changed to update highlight
        # Use selectionModel().selectionChanged for PyQt6
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def set_selection_mode(self, mode: str):
        """Set selection mode."""
        self._selection_mode = mode
        self._column_byte_pos = -1
        self.selectionModel().clearSelection()
        self._model.clear_selection_highlight()

        # Update selection behavior based on mode
        if mode == self.SELECTION_ROW:
            # Row selection - select entire rows
            self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
            self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        elif mode == self.SELECTION_COLUMN:
            # Column selection - select same column across rows (handled in mouse)
            self.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
            self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        elif mode == self.SELECTION_CONTINUOUS:
            # Continuous selection - standard selection behavior
            self.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
            self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        elif mode == self.SELECTION_BLOCK:
            # Block selection - custom implementation
            self.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
            self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)

    def get_selection_mode(self) -> str:
        """Get current selection mode."""
        return self._selection_mode

    def _show_context_menu(self, pos):
        """Show context menu at position."""
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)

        # Selection mode submenu
        selection_menu = QMenu("选择模式", menu)

        # Current mode check
        row_action = selection_menu.addAction("按行选择")
        row_action.setCheckable(True)
        row_action.setChecked(self._selection_mode == self.SELECTION_ROW)
        row_action.triggered.connect(lambda: self.set_selection_mode(self.SELECTION_ROW))

        col_action = selection_menu.addAction("按列选择")
        col_action.setCheckable(True)
        col_action.setChecked(self._selection_mode == self.SELECTION_COLUMN)
        col_action.triggered.connect(lambda: self.set_selection_mode(self.SELECTION_COLUMN))

        continuous_action = selection_menu.addAction("连续选择")
        continuous_action.setCheckable(True)
        continuous_action.setChecked(self._selection_mode == self.SELECTION_CONTINUOUS)
        continuous_action.triggered.connect(lambda: self.set_selection_mode(self.SELECTION_CONTINUOUS))

        block_action = selection_menu.addAction("块选择")
        block_action.setCheckable(True)
        block_action.setChecked(self._selection_mode == self.SELECTION_BLOCK)
        block_action.triggered.connect(lambda: self.set_selection_mode(self.SELECTION_BLOCK))

        menu.addMenu(selection_menu)

        menu.exec(self.viewport().mapToGlobal(pos))

    def _calculate_byte_offset(self, row: int, column: int, x_pos: int = 0) -> int:
        """Calculate byte offset from table row/column and optional x position.
        
        Args:
            row: Table row index
            column: Table column index (0 = hex, 1 = ascii)
            x_pos: Optional x position within cell for more precise calculation
            
        Returns:
            Byte offset in file
        """
        bytes_per_row = self._model._bytes_per_row
        header_length = self._model._header_length
        
        if self._model._arrangement_mode == "header_length":
            # For header length mode, calculate offset using model
            row_offset = self._model._get_row_offset(row)
        else:
            row_offset = row * bytes_per_row
            
        # Add header length if present
        row_offset += header_length
        
        return row_offset

    def _calculate_column_byte_pos(self, x_pos: int, bytes_per_row: int) -> int:
        """Calculate byte position within a row from x position.
        
        Args:
            x_pos: X position in the hex column
            bytes_per_row: Number of bytes per row
            
        Returns:
            Byte position (0-based index within row)
        """
        col_width = self.columnWidth(0)
        if col_width <= 0:
            return 0
            
        # Calculate character width based on column layout
        # Format: "00000000  AA BB CC ..." 
        # Offset: 8 chars + 2 spaces = 10 chars
        # Each byte: 3 chars (2 hex + 1 space)
        offset_chars = 10
        hex_section_width = col_width - (offset_chars * self._font_width)
        
        if hex_section_width <= 0:
            # Fallback: use simple calculation
            char_width = col_width / (offset_chars + bytes_per_row * 3)
            byte_pos = int((x_pos / char_width - offset_chars) / 3)
        else:
            # More accurate calculation
            byte_char_width = hex_section_width / bytes_per_row
            x_in_hex = x_pos - (offset_chars * self._font_width)
            
            if x_in_hex < 0:
                byte_pos = 0
            else:
                byte_pos = int(x_in_hex / byte_char_width)
        
        # Clamp to valid range
        return max(0, min(byte_pos, bytes_per_row - 1))

    def _on_selection_changed(self, selected, deselected):
        """Handle selection changed to update highlight based on selection mode."""
        selection = self.selectionModel().selection()
        indexes = selection.indexes()

        if not indexes:
            self._model.clear_selection_highlight()
            self.selection_changed.emit(-1, -1)
            return

        bytes_per_row = self._model._bytes_per_row
        header_length = self._model._header_length
        file_size = self._model._file_size
        arrangement_mode = self._model._arrangement_mode

        if self._selection_mode == self.SELECTION_ROW:
            # Row selection: select all bytes in each selected row
            rows = sorted(set(idx.row() for idx in indexes))
            ranges = []
            for row in rows:
                if arrangement_mode == "header_length":
                    row_offset = self._model._get_row_offset(row)
                    # Get actual data length for this row
                    if row_offset >= file_size:
                        continue
                    header_len = min(header_length, file_size - row_offset)
                    if header_len > 0:
                        header_bytes = self._model._data[row_offset:row_offset + header_len]
                        try:
                            data_len = int.from_bytes(header_bytes, byteorder='big')
                        except:
                            data_len = 0
                        if data_len == 0:
                            data_len = 1
                        start = row_offset + header_length
                        end = min(start + data_len - 1, file_size - 1)
                    else:
                        continue
                else:
                    start = row * bytes_per_row
                    end = min(start + bytes_per_row - 1, file_size - 1)
                
                if end >= start:
                    ranges.append((start, end))
            
            self._model.set_selection_ranges(ranges)

            # Emit signal with first range
            if ranges:
                self.selection_changed.emit(ranges[0][0], ranges[0][1])
            else:
                self.selection_changed.emit(-1, -1)

        elif self._selection_mode == self.SELECTION_COLUMN:
            # Column selection: select same byte position across all rows
            # Use the stored byte position from mouse press
            byte_pos = self._column_byte_pos

            if byte_pos < 0:
                self._model.clear_selection_highlight()
                self.selection_changed.emit(-1, -1)
                return

            # Select this byte position across all rows
            ranges = []
            
            if arrangement_mode == "header_length":
                # For header length mode, iterate through rows
                for row in range(self._model.rowCount()):
                    row_offset = self._model._get_row_offset(row)
                    if row_offset >= file_size:
                        break
                    # Get data length for this row
                    header_len = min(header_length, file_size - row_offset)
                    if header_len > 0:
                        header_bytes = self._model._data[row_offset:row_offset + header_len]
                        try:
                            data_len = int.from_bytes(header_bytes, byteorder='big')
                        except:
                            data_len = 0
                        if data_len == 0:
                            data_len = 1
                        
                        # Check if byte_pos is within this row's data
                        if byte_pos < data_len:
                            start = row_offset + header_length + byte_pos
                            if start < file_size:
                                ranges.append((start, start))
            else:
                # Equal frame mode
                total_rows = (file_size + bytes_per_row - 1) // bytes_per_row
                for r in range(total_rows):
                    start = r * bytes_per_row + byte_pos
                    if start < file_size:
                        ranges.append((start, start))

            self._model.set_selection_ranges(ranges)

            if ranges:
                self.selection_changed.emit(ranges[0][0], ranges[-1][1])
            else:
                self.selection_changed.emit(-1, -1)

        elif self._selection_mode == self.SELECTION_BLOCK:
            # Block selection: calculate ranges for each row in the block
            if not indexes:
                self._model.clear_selection_highlight()
                self.selection_changed.emit(-1, -1)
                return
                
            rows = sorted(set(idx.row() for idx in indexes))
            cols = sorted(set(idx.column() for idx in indexes))
            
            if not rows or not cols:
                self._model.clear_selection_highlight()
                self.selection_changed.emit(-1, -1)
                return
            
            min_row, max_row = min(rows), max(rows)
            min_col, max_col = min(cols), max(cols)

            # Convert column indices to byte positions
            # Column 0 = hex area, Column 1 = ascii area
            # For block selection, we need to calculate byte positions within rows
            if self._block_start_byte_pos >= 0:
                # Use stored start byte position for more accurate block selection
                start_byte_pos = self._block_start_byte_pos
            else:
                # Fallback: estimate from column
                start_byte_pos = 0
            
            # Determine byte range based on columns selected
            if min_col == 0 and max_col == 0:
                # Only hex column selected - calculate byte range
                start_byte_pos = self._block_start_byte_pos if self._block_start_byte_pos >= 0 else 0
                end_byte_pos = start_byte_pos + (len(cols) - 1)
            elif min_col == 1 and max_col == 1:
                # Only ascii column selected - same as hex column 0
                start_byte_pos = self._block_start_byte_pos if self._block_start_byte_pos >= 0 else 0
                end_byte_pos = start_byte_pos
            else:
                # Both columns selected
                start_byte_pos = self._block_start_byte_pos if self._block_start_byte_pos >= 0 else 0
                end_byte_pos = start_byte_pos + bytes_per_row - 1

            # Clamp to valid range
            start_byte_pos = max(0, min(start_byte_pos, bytes_per_row - 1))
            end_byte_pos = max(0, min(end_byte_pos, bytes_per_row - 1))

            ranges = []
            for row in range(min_row, max_row + 1):
                if arrangement_mode == "header_length":
                    row_offset = self._model._get_row_offset(row)
                    if row_offset >= file_size:
                        continue
                    # Get data length for this row
                    header_len = min(header_length, file_size - row_offset)
                    if header_len > 0:
                        header_bytes = self._model._data[row_offset:row_offset + header_len]
                        try:
                            data_len = int.from_bytes(header_bytes, byteorder='big')
                        except:
                            data_len = 0
                        if data_len == 0:
                            data_len = 1
                        
                        # Calculate start and end within this row's data
                        actual_start = row_offset + header_length + start_byte_pos
                        actual_end = row_offset + header_length + end_byte_pos
                        
                        # Clamp to file size and data length
                        if actual_start < file_size and actual_start < row_offset + header_length + data_len:
                            start = max(actual_start, row_offset + header_length)
                            end = min(actual_end, row_offset + header_length + data_len - 1, file_size - 1)
                            if end >= start:
                                ranges.append((start, end))
                else:
                    start = row * bytes_per_row + start_byte_pos
                    end = row * bytes_per_row + end_byte_pos
                    if start < file_size:
                        ranges.append((start, min(end, file_size - 1)))

            self._model.set_selection_ranges(ranges)

            if ranges:
                self.selection_changed.emit(ranges[0][0], ranges[-1][1])
            else:
                self.selection_changed.emit(-1, -1)

        else:
            # Continuous selection: standard behavior - select continuous byte range
            if not indexes:
                self._model.clear_selection_highlight()
                self.selection_changed.emit(-1, -1)
                return
                
            # Get all selected rows and columns
            rows = sorted(set(idx.row() for idx in indexes))
            cols = sorted(set(idx.column() for idx in indexes))
            
            if arrangement_mode == "header_length":
                # For header length mode, calculate based on actual row offsets
                min_row = min(rows)
                max_row = max(rows)
                
                start_offset = self._model._get_row_offset(min_row) + header_length
                
                # Get end offset from max row
                max_row_offset = self._model._get_row_offset(max_row)
                if max_row_offset < file_size:
                    header_len = min(header_length, file_size - max_row_offset)
                    if header_len > 0:
                        header_bytes = self._model._data[max_row_offset:max_row_offset + header_len]
                        try:
                            data_len = int.from_bytes(header_bytes, byteorder='big')
                        except:
                            data_len = 0
                        if data_len == 0:
                            data_len = 1
                        end_offset = max_row_offset + header_length + data_len - 1
                    else:
                        end_offset = max_row_offset
                else:
                    end_offset = file_size - 1
                
                end_offset = min(end_offset, file_size - 1)
            else:
                # Equal frame mode - calculate from rows
                min_row = min(rows)
                max_row = max(rows)
                
                # Determine byte range within rows
                if 0 in cols and 1 in cols:
                    # Both columns selected - select full rows
                    start_offset = min_row * bytes_per_row
                    end_offset = min((max_row + 1) * bytes_per_row - 1, file_size - 1)
                elif 0 in cols:
                    # Only hex column - calculate precise byte range
                    # Use tracked start/end byte positions
                    if self._block_start_byte_pos >= 0:
                        start_byte = self._block_start_byte_pos
                    else:
                        start_byte = 0
                    start_offset = min_row * bytes_per_row + start_byte
                    
                    # Use actual end byte position if tracking, otherwise use row end
                    if self._continuous_end_byte_pos >= 0:
                        end_byte = self._continuous_end_byte_pos
                    else:
                        end_byte = bytes_per_row - 1
                    end_offset = max_row * bytes_per_row + end_byte
                else:
                    # Only ascii column
                    start_offset = min_row * bytes_per_row
                    end_offset = (max_row + 1) * bytes_per_row - 1
                
                end_offset = min(end_offset, file_size - 1)

            if start_offset <= end_offset:
                self._model.set_selection(start_offset, end_offset)
                self.selection_changed.emit(start_offset, end_offset)
            else:
                self._model.clear_selection_highlight()
                self.selection_changed.emit(-1, -1)

    def mousePressEvent(self, event):
        """Handle mouse press for block/column selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if index.isValid():
                bytes_per_row = self._model._bytes_per_row
                
                if self._selection_mode == self.SELECTION_BLOCK:
                    # Start block selection - store start position with byte offset
                    self._block_start_row = index.row()
                    self._block_start_col = index.column()
                    # Calculate the byte position within the row from x position
                    self._block_start_byte_pos = self._calculate_column_byte_pos(event.pos().x(), bytes_per_row)
                elif self._selection_mode == self.SELECTION_COLUMN:
                    # Column selection - calculate byte position and apply highlight directly
                    self._do_column_selection(event.pos())
                    return  # Don't call super, we handled it
                elif self._selection_mode == self.SELECTION_CONTINUOUS:
                    # Track start byte position for continuous selection
                    self._block_start_byte_pos = self._calculate_column_byte_pos(event.pos().x(), bytes_per_row)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for block/continuous selection."""
        if event.buttons() & Qt.MouseButton.LeftButton:
            bytes_per_row = self._model._bytes_per_row
            current_byte_pos = self._calculate_column_byte_pos(event.pos().x(), bytes_per_row)
            
            if self._selection_mode == self.SELECTION_BLOCK and self._block_start_row >= 0:
                index = self.indexAt(event.pos())
                if index.isValid():
                    current_row = index.row()
                    current_col = index.column()

                    # Calculate block selection
                    start_row = min(self._block_start_row, current_row)
                    end_row = max(self._block_start_row, current_row)
                    start_col = min(self._block_start_col, current_col)
                    end_col = max(self._block_start_col, current_col)

                    # Update selection in table
                    self.selectionModel().clearSelection()
                    from PyQt6.QtCore import QItemSelection
                    selection = QItemSelection()
                    top_left = self.model().index(start_row, 0)
                    bottom_right = self.model().index(end_row, 1)
                    selection.select(top_left, bottom_right)
                    self.selectionModel().select(selection, self.selectionCommand(top_left, None))
            elif self._selection_mode == self.SELECTION_CONTINUOUS and self._block_start_byte_pos >= 0:
                # Update continuous selection as user drags
                index = self.indexAt(event.pos())
                if index.isValid():
                    current_row = index.row()
                    current_byte_pos = self._calculate_column_byte_pos(event.pos().x(), bytes_per_row)
                    self._continuous_end_byte_pos = current_byte_pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release for block/continuous selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._selection_mode == self.SELECTION_BLOCK:
                self._block_start_row = -1
                self._block_start_col = -1
            # Reset byte position tracking after selection is complete
            self._block_start_byte_pos = -1
            self._continuous_end_byte_pos = -1
        super().mouseReleaseEvent(event)

    def _do_column_selection(self, pos):
        """Select entire column (byte position) across all rows - directly update highlight."""
        bytes_per_row = self._model._bytes_per_row
        file_size = self._model._file_size
        header_length = self._model._header_length
        arrangement_mode = self._model._arrangement_mode

        # Calculate byte position from x position using improved method
        byte_pos = self._calculate_column_byte_pos(pos.x(), bytes_per_row)
        
        # Store byte position
        self._column_byte_pos = byte_pos

        # Create selection ranges for this byte position across all rows
        ranges = []
        
        if arrangement_mode == "header_length":
            # For header length mode, iterate through rows
            for row in range(self._model.rowCount()):
                row_offset = self._model._get_row_offset(row)
                if row_offset >= file_size:
                    break
                # Get data length for this row
                header_len = min(header_length, file_size - row_offset)
                if header_len > 0:
                    header_bytes = self._model._data[row_offset:row_offset + header_len]
                    try:
                        data_len = int.from_bytes(header_bytes, byteorder='big')
                    except:
                        data_len = 0
                    if data_len == 0:
                        data_len = 1
                    
                    # Check if byte_pos is within this row's data
                    if byte_pos < data_len:
                        start = row_offset + header_length + byte_pos
                        if start < file_size:
                            ranges.append((start, start))
        else:
            # Equal frame mode
            total_rows = (file_size + bytes_per_row - 1) // bytes_per_row
            for r in range(total_rows):
                start = r * bytes_per_row + byte_pos
                if start < file_size:
                    ranges.append((start, start))

        # Directly set selection ranges in model (don't use Qt selection)
        self._model.set_selection_ranges(ranges)

        # Emit signal
        if ranges:
            self.selection_changed.emit(ranges[0][0], ranges[-1][1])
        else:
            self.selection_changed.emit(-1, -1)

    def _get_offset_at(self, index: QModelIndex) -> int:
        """Get file offset at model index."""
        if not index.isValid():
            return 0

        row = index.row()
        total_per_row = self._model._bytes_per_row + self._model._header_length
        return row * total_per_row

    def set_file_handle(self, file_handle):
        """Set file handle to display."""
        self._file_handle = file_handle

        # Connect signals
        file_handle.data_changed.connect(self._on_data_changed)

        # Load data
        self._reload_data()

        # Resize columns based on bytes_per_row
        self._resize_columns()

    def _reload_data(self):
        """Reload data from file handle."""
        if self._file_handle:
            # Read all data (for now, optimization later)
            data = self._file_handle.read(0, self._file_handle.file_size)
            self._model.set_data(data)

    def _on_data_changed(self, start, end):
        """Handle data change."""
        self._reload_data()

    def set_bytes_per_row(self, value: int):
        """Set bytes per row for equal frame mode."""
        self._model.set_arrangement_mode("equal_frame", value)
        self._resize_columns()

    def set_arrangement_mode(self, mode: str, param: int = 32):
        """Set arrangement mode.

        Args:
            mode: "equal_frame" or "header_length"
            param: For equal_frame, this is bytes per row (1-65535).
                   For header_length, this is header length in bytes (1-8).
        """
        self._model.set_arrangement_mode(mode, param)
        self._resize_columns()

    def _resize_columns(self):
        """Resize columns based on bytes_per_row and font width."""
        # Calculate column 0 width (Offset + Hex)
        # Format: "00000000  AA BB CC ..." where each byte is 3 chars (2 hex + 1 space)
        offset_chars = 8  # 8 hex digits for offset
        space_between = 2  # space between offset and hex
        padding = 10  # padding for cell margins

        if self._model._arrangement_mode == "header_length":
            # 头长度模式：使用默认值 32 字节作为列宽
            bytes_per_row = 32
        else:
            bytes_per_row = self._model._bytes_per_row

        if bytes_per_row <= 0:
            return

        hex_chars = bytes_per_row * 3 - 1  # hex representation

        col0_chars = offset_chars + space_between + hex_chars
        col0_width = int(col0_chars * self._font_width) + padding

        # Set column 0 to calculated width
        self.setColumnWidth(0, col0_width)

        # Set column 1 to stretch (fills remaining space)
        self.horizontalHeader().setStretchLastSection(True)

    def get_offset_at_cursor(self) -> int:
        """Get file offset at current cursor position."""
        index = self.currentIndex()
        if not index.isValid():
            return 0

        row = index.row()
        total_per_row = self._model._bytes_per_row + self._model._header_length
        return row * total_per_row

    def scrollToOffset(self, offset: int):
        """Scroll to specific offset."""
        total_per_row = self._model._bytes_per_row + self._model._header_length
        row = offset // total_per_row
        self.scrollTo(self._model.index(row, 0))

    def set_search_results(self, results, current_index=-1):
        """Set search results for highlighting."""
        self._model.set_search_results(results, current_index)

    def clear_search_results(self):
        """Clear search highlights."""
        self._model.clear_search_results()

    def keyPressEvent(self, event):
        """Handle key press."""
        # Let parent handle most keys
        super().keyPressEvent(event)

        # Emit cursor moved signal
        offset = self.get_offset_at_cursor()
        self.cursor_moved.emit(offset)


class HexViewWidget(QWidget):
    """
    Hex view widget with hex view, ruler, and vertical scrollbar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_handle = None

        # Create layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create offset ruler (hidden for now)
        self._ruler = OffsetRulerWidget()
        self._ruler.setVisible(False)
        layout.addWidget(self._ruler)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
        """)

        # Create hex view
        self._hex_view = HexView()
        scroll.setWidget(self._hex_view)

        layout.addWidget(scroll)
        self.setLayout(layout)

        # Connect scroll signals
        self._hex_view.horizontalScrollBar().valueChanged.connect(self._on_scroll_changed)

    def _on_scroll_changed(self, value):
        """Handle horizontal scroll change."""
        self._ruler.set_scroll_offset(value)
        # Also update column width in case it changed
        self._ruler.set_column_width(self._hex_view.columnWidth(0))

    def set_file_handle(self, file_handle):
        """Set file handle to display."""
        self._file_handle = file_handle
        self._hex_view.set_file_handle(file_handle)
        # Update ruler settings
        self._ruler.set_bytes_per_row(self._hex_view._model._bytes_per_row)
        self._ruler.set_header_length(self._hex_view._model._header_length)
        self._ruler.set_column_width(self._hex_view.columnWidth(0))

    @property
    def hex_view(self):
        """Get hex view."""
        return self._hex_view
