"""
Data Value Panel

Displays typed values at the current cursor position.
"""

import math
import struct
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..design_system import CHROME, build_mono_font, panel_surface_qss, table_surface_qss

MAX_VALUE_BYTES = 8
VALUE_SPECS = (
    ("char", 1),
    ("uint8", 1),
    ("int8", 1),
    ("uint16", 2),
    ("int16", 2),
    ("uint32", 4),
    ("int32", 4),
    ("time", 4),
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


def format_unix_time(seconds: int) -> str:
    """Format Unix timestamp seconds as a YYYY/MM/DD date."""
    return datetime.fromtimestamp(seconds).strftime("%Y/%m/%d")


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

        if type_name == "time":
            return format_unix_time(int.from_bytes(chunk, byteorder=byteorder, signed=False))

        if type_name == "float":
            fmt = "<f" if byteorder == "little" else ">f"
            return format_float(struct.unpack(fmt, chunk)[0])

        if type_name == "double":
            fmt = "<d" if byteorder == "little" else ">d"
            return format_float(struct.unpack(fmt, chunk)[0])
    except (OSError, OverflowError, ValueError, struct.error):
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
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            panel_surface_qss("QWidget#dataValuePanel")
            + table_surface_qss("QWidget#dataValuePanel")
            + f"""
            QWidget#dataValuePanel {{
                background: transparent;
                border: none;
            }}
            QLabel#dataValueSectionLabel {{
                color: {CHROME.text_muted};
                font-size: 9px;
                font-weight: 700;
            }}
            QFrame#dataValueSummaryCard {{
                background-color: {CHROME.surface_alt};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
            }}
            QFrame#dataValueMetricBlock {{
                background: transparent;
                border: none;
            }}
            QLabel#dataValueMetricValue {{
                color: {CHROME.text_primary};
                background: transparent;
                border: none;
                padding: 0;
            }}
            QWidget#dataValuePanel QRadioButton {{
                background-color: transparent;
                color: {CHROME.text_secondary};
                border: none;
                spacing: 6px;
                font-weight: 600;
            }}
            QWidget#dataValuePanel QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid {CHROME.border_strong};
                background-color: {CHROME.surface};
            }}
            QWidget#dataValuePanel QRadioButton:hover {{
                color: {CHROME.text_primary};
            }}
            QWidget#dataValuePanel QRadioButton::indicator:hover {{
                border-color: {CHROME.accent_hover};
            }}
            QWidget#dataValuePanel QRadioButton::indicator:checked {{
                background-color: {CHROME.accent};
                border-color: {CHROME.accent};
            }}
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        value_font = build_mono_font(10)

        summary_card = QFrame(self)
        summary_card.setObjectName("dataValueSummaryCard")
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(16)

        offset_block = QFrame(summary_card)
        offset_block.setObjectName("dataValueMetricBlock")
        offset_layout = QVBoxLayout(offset_block)
        offset_layout.setContentsMargins(0, 0, 0, 0)
        offset_layout.setSpacing(4)
        offset_label = QLabel("Offset")
        offset_label.setObjectName("dataValueSectionLabel")
        offset_layout.addWidget(offset_label)
        self._offset_value = QLabel("0x00000000")
        self._offset_value.setObjectName("dataValueMetricValue")
        self._offset_value.setFont(value_font)
        offset_layout.addWidget(self._offset_value)
        summary_layout.addWidget(offset_block, 0, Qt.AlignmentFlag.AlignTop)

        bytes_block = QFrame(summary_card)
        bytes_block.setObjectName("dataValueMetricBlock")
        bytes_layout = QVBoxLayout(bytes_block)
        bytes_layout.setContentsMargins(0, 0, 0, 0)
        bytes_layout.setSpacing(4)
        bytes_label = QLabel("Cursor Bytes")
        bytes_label.setObjectName("dataValueSectionLabel")
        bytes_layout.addWidget(bytes_label)
        self._raw_bytes_value = QLabel("N/A")
        self._raw_bytes_value.setObjectName("dataValueMetricValue")
        self._raw_bytes_value.setFont(value_font)
        self._raw_bytes_value.setWordWrap(False)
        bytes_layout.addWidget(self._raw_bytes_value)
        summary_layout.addWidget(bytes_block, 1, Qt.AlignmentFlag.AlignTop)

        summary_card.setLayout(summary_layout)
        layout.addWidget(summary_card)

        endian_row = QHBoxLayout()
        endian_row.setContentsMargins(2, 0, 2, 0)
        endian_row.setSpacing(14)

        self._endian_group = QButtonGroup(self)
        self._endian_group.setExclusive(True)

        self._little_endian_radio = QRadioButton("Little Endian")
        self._big_endian_radio = QRadioButton("Big Endian")
        self._endian_group.addButton(self._little_endian_radio)
        self._endian_group.addButton(self._big_endian_radio)
        self._little_endian_radio.setChecked(True)
        self._little_endian_radio.toggled.connect(self._on_endian_toggled)
        self._big_endian_radio.toggled.connect(self._on_endian_toggled)

        endian_row.addWidget(self._little_endian_radio)
        endian_row.addWidget(self._big_endian_radio)
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
            self._value_table.setRowHeight(row, CHROME.row_height)

        layout.addWidget(self._value_table, 1)
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
        if not checked:
            return
        self._byteorder = "big" if self._big_endian_radio.isChecked() else "little"
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
