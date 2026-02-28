"""
Goto Dialog

Go to offset dialog.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QComboBox, QGroupBox,
                             QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt


class GotoDialog(QDialog):
    """
    Go to offset dialog.

    Allows jumping to specific offsets in the file.
    """

    def __init__(self, parent=None, max_offset=0):
        super().__init__(parent)
        self._max_offset = max_offset
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("Go To Offset")
        self.resize(400, 180)

        layout = QVBoxLayout()

        # Offset input
        layout.addWidget(QLabel("Enter offset:"))
        self._offset_input = QLineEdit()
        self._offset_input.setPlaceholderText("e.g., 0x1000 or 4096")
        self._offset_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._offset_input)

        # Format selection
        format_group = QGroupBox("Format")
        format_layout = QHBoxLayout()

        self._format_group = QButtonGroup()

        hex_btn = QRadioButton("Hexadecimal (0x...)")
        hex_btn.setChecked(True)
        self._format_group.addButton(hex_btn, 0)
        format_layout.addWidget(hex_btn)

        dec_btn = QRadioButton("Decimal")
        self._format_group.addButton(dec_btn, 1)
        format_layout.addWidget(dec_btn)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # Reference point
        ref_group = QGroupBox("From")
        ref_layout = QHBoxLayout()

        self._ref_group = QButtonGroup()

        start_btn = QRadioButton("Start of file")
        start_btn.setChecked(True)
        self._ref_group.addButton(start_btn, 0)
        ref_layout.addWidget(start_btn)

        end_btn = QRadioButton("End of file")
        self._ref_group.addButton(end_btn, 1)
        ref_layout.addWidget(end_btn)

        ref_group.setLayout(ref_layout)
        layout.addWidget(ref_group)

        # Info
        if self._max_offset > 0:
            self._info_label = QLabel(f"Valid range: 0x0 - 0x{self._max_offset:X} ({self._max_offset})")
            layout.addWidget(self._info_label)

        # Buttons
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        go_btn = QPushButton("Go To")
        go_btn.clicked.connect(self.accept)
        go_btn.setDefault(True)
        button_layout.addWidget(go_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _on_text_changed(self, text):
        """Handle text change."""
        text = text.strip()

        # Try to parse
        try:
            if text.startswith("0x") or text.startswith("0X"):
                # Hex
                value = int(text, 16)
            elif text.startswith("$"):
                # Alternative hex prefix
                value = int(text[1:], 16)
            else:
                # Try decimal first
                try:
                    value = int(text, 10)
                except ValueError:
                    # Try hex anyway
                    value = int(text, 16)

            # Validate
            if self._max_offset > 0 and value > self._max_offset:
                self._offset_input.setStyleSheet("QLineEdit { background-color: #5c2b2b; }")
            else:
                self._offset_input.setStyleSheet("")
        except (ValueError, TypeError):
            if text:
                self._offset_input.setStyleSheet("QLineEdit { background-color: #5c2b2b; }")
            else:
                self._offset_input.setStyleSheet("")

    def get_offset(self) -> int:
        """Get entered offset."""
        text = self._offset_input.text().strip()
        if not text:
            return 0

        try:
            if text.startswith("0x") or text.startswith("0X"):
                return int(text, 16)
            elif text.startswith("$"):
                return int(text[1:], 16)
            else:
                format_id = self._format_group.checkedId()
                if format_id == 0:  # Hex
                    return int(text, 16)
                else:  # Decimal
                    return int(text, 10)
        except (ValueError, TypeError):
            return 0

    def set_max_offset(self, max_offset: int):
        """Set maximum offset."""
        self._max_offset = max_offset
        if max_offset > 0:
            self._info_label.setText(f"Valid range: 0x0 - 0x{self._max_offset:X} ({self._max_offset})")
