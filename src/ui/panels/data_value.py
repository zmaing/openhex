"""
Data Value Panel

Displays data values at cursor position.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QFont


class DataValuePanel(QWidget):
    """
    Data value inspection panel.

    Shows various representations of the byte at cursor.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Data Inspector")
        title.setStyleSheet("font-weight: bold; color: #cccccc;")
        layout.addWidget(title)

        # Offset display
        self._offset_label = QLabel("0x00000000")
        self._offset_label.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Offset:"))
        layout.addWidget(self._offset_label)

        # Hex value
        self._hex_label = QLabel("00")
        self._hex_label.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Hex:"))
        layout.addWidget(self._hex_label)

        # Decimal values
        self._dec_signed_label = QLabel("0")
        self._dec_signed_label.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Signed:"))
        layout.addWidget(self._dec_signed_label)

        self._dec_unsigned_label = QLabel("0")
        self._dec_unsigned_label.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Unsigned:"))
        layout.addWidget(self._dec_unsigned_label)

        # Binary
        self._bin_label = QLabel("00000000")
        self._bin_label.setFont(QFont("Monospace", 10))
        layout.addWidget(QLabel("Binary:"))
        layout.addWidget(self._bin_label)

        # ASCII
        self._ascii_label = QLabel(".")
        self._ascii_label.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("ASCII:"))
        layout.addWidget(self._ascii_label)

        # Octal
        self._octal_label = QLabel("0o00")
        self._octal_label.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Octal:"))
        layout.addWidget(self._octal_label)

        layout.addStretch()
        self.setLayout(layout)

    def set_data(self, data: bytes):
        """Set data to inspect."""
        self._data = data

    def update_at_offset(self, offset: int):
        """Update display for offset."""
        if not self._data or offset < 0 or offset >= len(self._data):
            self._offset_label.setText("0x00000000")
            self._hex_label.setText("00")
            self._dec_signed_label.setText("0")
            self._dec_unsigned_label.setText("0")
            self._bin_label.setText("00000000")
            self._ascii_label.setText(".")
            self._octal_label.setText("0o00")
            return

        byte = self._data[offset]

        # Update labels
        self._offset_label.setText(f"0x{offset:08X}")
        self._hex_label.setText(f"{byte:02X}")
        self._dec_signed_label.setText(str(int.from_bytes([byte], 'signed',).decode('latin-1') if 32 <= byte < 127 else str(byte - 256 if byte > 127 else byte)))
        self._dec_unsigned_label.setText(str(byte))
        self._bin_label.setText(f"{byte:08b}")
        self._ascii_label.setText(chr(byte) if 32 <= byte < 127 else '.')
        self._octal_label.setText(f"0o{byte:03o}")
