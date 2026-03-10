"""
Data Value Panel

Displays typed values at the current cursor position.
"""

import math
import struct

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

MAX_VALUE_BYTES = 8
VALUE_SPECS = (
    ("char", 1),
    ("uint8", 1),
    ("int8", 1),
    ("uint16", 2),
    ("int16", 2),
    ("uint32", 4),
    ("int32", 4),
    ("uint64", 8),
    ("int64", 8),
    ("float", 4),
    ("double", 8),
)


def format_char(byte: int) -> str:
    """Format a single byte as a printable char or hex escape."""
    if 32 <= byte <= 126:
        char = chr(byte)
        if char == "\\":
            char = "\\\\"
        elif char == "'":
            char = "\\'"
        return f"'{char}'"
    return f"\\x{byte:02X}"


def format_float(value: float) -> str:
    """Format floating point values with readable special cases."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Inf" if value > 0 else "-Inf"
    return repr(value)


def format_typed_value(type_name: str, size: int, data: bytes, byteorder: str) -> str:
    """Format the leading bytes as the requested type."""
    if len(data) < size:
        return "N/A"

    chunk = data[:size]

    try:
        if type_name == "char":
            return format_char(chunk[0])

        if type_name.startswith("uint"):
            return str(int.from_bytes(chunk, byteorder=byteorder, signed=False))

        if type_name.startswith("int"):
            return str(int.from_bytes(chunk, byteorder=byteorder, signed=True))

        if type_name == "float":
            fmt = "<f" if byteorder == "little" else ">f"
            return format_float(struct.unpack(fmt, chunk)[0])

        if type_name == "double":
            fmt = "<d" if byteorder == "little" else ">d"
            return format_float(struct.unpack(fmt, chunk)[0])
    except (OverflowError, ValueError, struct.error):
        return "N/A"

    return "N/A"


def decode_data_values(data: bytes):
    """Decode the leading cursor bytes for all supported types."""
    data = bytes((data or b"")[:MAX_VALUE_BYTES])
    rows = []

    for type_name, size in VALUE_SPECS:
        little_value = format_typed_value(type_name, size, data, "little")
        if size == 1:
            big_value = little_value
        else:
            big_value = format_typed_value(type_name, size, data, "big")
        rows.append((type_name, size, little_value, big_value))

    return rows


def decode_display_values(data: bytes, byteorder: str):
    """Decode values for a single active byte order."""
    active_byteorder = "big" if byteorder == "big" else "little"
    rows = []

    for type_name, size, little_value, big_value in decode_data_values(data):
        value = big_value if active_byteorder == "big" else little_value
        rows.append((type_name, size, value))

    return rows


class DataValuePanel(QWidget):
    """
    Data value inspection panel.

    Shows multiple typed views of the bytes starting at the cursor.
    """

    MAX_BYTES = MAX_VALUE_BYTES
    VALUE_SPECS = VALUE_SPECS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = b""
        self._byteorder = "little"
        self._decoded_rows = []
        self._row_by_type = {
            type_name: row for row, (type_name, _size) in enumerate(self.VALUE_SPECS)
        }
        self._init_ui()
        self.clear_values()

    def _init_ui(self):
        """Initialize UI."""
        self.setObjectName("dataValuePanel")
        self.setStyleSheet(
            """
            QWidget#dataValuePanel {
                background-color: #252526;
                color: #cccccc;
            }
            QWidget#dataValuePanel QLabel {
                background-color: transparent;
                color: #cccccc;
                border: none;
            }
            QWidget#dataValuePanel QCheckBox {
                background-color: transparent;
                color: #cccccc;
                border: none;
                spacing: 6px;
            }
            QWidget#dataValuePanel QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #3c3c3c;
                background-color: #2d2d30;
            }
            QWidget#dataValuePanel QCheckBox::indicator:hover {
                border-color: #569cd6;
            }
            QWidget#dataValuePanel QCheckBox::indicator:checked {
                background-color: #0e639c;
                border-color: #0e639c;
            }
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("Data Inspector")
        title.setStyleSheet("font-weight: bold; color: #cccccc;")
        layout.addWidget(title)

        value_font = QFont("Monospace", 10)

        layout.addWidget(QLabel("Offset:"))
        self._offset_value = QLabel("0x00000000")
        self._offset_value.setFont(value_font)
        layout.addWidget(self._offset_value)

        layout.addWidget(QLabel("Bytes:"))
        self._raw_bytes_value = QLabel("N/A")
        self._raw_bytes_value.setFont(value_font)
        self._raw_bytes_value.setWordWrap(True)
        layout.addWidget(self._raw_bytes_value)

        endian_row = QHBoxLayout()
        endian_row.setContentsMargins(0, 0, 0, 0)
        endian_row.setSpacing(8)
        endian_label = QLabel("Byte Order:")
        self._big_endian_checkbox = QCheckBox("Big Endian")
        self._big_endian_checkbox.toggled.connect(self._on_endian_toggled)
        endian_row.addWidget(endian_label)
        endian_row.addWidget(self._big_endian_checkbox)
        endian_row.addStretch()
        layout.addLayout(endian_row)

        self._value_table = QTableWidget(len(self.VALUE_SPECS), 3, self)
        self._value_table.setHorizontalHeaderLabels(["Type", "Size", "Value (LE)"])
        self._value_table.verticalHeader().setVisible(False)
        self._value_table.setAlternatingRowColors(True)
        self._value_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._value_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._value_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._value_table.setShowGrid(False)
        self._value_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._value_table.setStyleSheet(
            """
            QTableWidget {
                background-color: #252526;
                color: #cccccc;
                alternate-background-color: #2d2d30;
                border: 1px solid #3c3c3c;
                gridline-color: #3c3c3c;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid #3c3c3c;
            }
            """
        )

        header = self._value_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for row, (type_name, size) in enumerate(self.VALUE_SPECS):
            self._set_table_item(row, 0, type_name, value_font)
            self._set_table_item(
                row,
                1,
                f"{size} B",
                value_font,
                Qt.AlignmentFlag.AlignCenter,
            )
            self._set_table_item(row, 2, "N/A", value_font)
            self._value_table.setRowHeight(row, 24)

        layout.addWidget(self._value_table)
        self.setLayout(layout)

    def _set_table_item(
        self,
        row: int,
        column: int,
        text: str,
        font: QFont,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft
        | Qt.AlignmentFlag.AlignVCenter,
    ):
        """Create and place a table item."""
        item = QTableWidgetItem(text)
        item.setFont(font)
        item.setTextAlignment(int(alignment))
        item.setToolTip(text)
        self._value_table.setItem(row, column, item)

    def _set_value_cell(self, row: int, value: str):
        """Update the active value cell for a row."""
        item = self._value_table.item(row, 2)
        item.setText(value)
        item.setToolTip(value)

    def _refresh_value_header(self):
        """Refresh the value column header for the active byte order."""
        header_item = self._value_table.horizontalHeaderItem(2)
        if header_item is None:
            return
        suffix = "BE" if self._byteorder == "big" else "LE"
        header_item.setText(f"Value ({suffix})")

    def _apply_display_values(self):
        """Push cached decoded rows into the table."""
        self._refresh_value_header()

        if not self._decoded_rows:
            for row in range(len(self.VALUE_SPECS)):
                self._set_value_cell(row, "N/A")
            return

        value_index = 3 if self._byteorder == "big" else 2
        for row, (_type_name, _size, little_value, big_value) in enumerate(self._decoded_rows):
            value = big_value if value_index == 3 else little_value
            self._set_value_cell(row, value)

    def _on_endian_toggled(self, checked: bool):
        """Switch the displayed byte order."""
        self._byteorder = "big" if checked else "little"
        self._apply_display_values()

    def clear_values(self):
        """Reset the panel to an empty state."""
        self._offset_value.setText("0x00000000")
        self._raw_bytes_value.setText("N/A")
        self._decoded_rows = []
        self._apply_display_values()

    def set_data(self, data: bytes):
        """Store data for compatibility with the older panel API."""
        self._data = bytes(data or b"")

    def update_at_offset(self, offset: int):
        """Update from internally stored data for compatibility."""
        if not self._data or offset < 0 or offset >= len(self._data):
            self.clear_values()
            return

        self.update_values(offset, self._data[offset:offset + self.MAX_BYTES])

    def update_values(self, offset: int, data: bytes):
        """Update display for bytes starting at the given offset."""
        data = bytes((data or b"")[:self.MAX_BYTES])
        if offset < 0 or not data:
            self.clear_values()
            return

        self._offset_value.setText(f"0x{offset:08X}")
        self._raw_bytes_value.setText(" ".join(f"{byte:02X}" for byte in data))
        self._decoded_rows = decode_data_values(data)
        self._apply_display_values()

    def get_row(self, type_name: str) -> int:
        """Return the row index for a type name."""
        return self._row_by_type[type_name]
