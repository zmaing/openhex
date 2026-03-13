"""
Batch Edit Dialog

批量修改对话框 - 填充/递增/递减/取反
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QGroupBox, QRadioButton,
                             QButtonGroup, QCheckBox, QSpinBox, QComboBox)
from PyQt6.QtCore import Qt

from .chrome import create_dialog_header


class BatchEditDialog(QDialog):
    """
    Batch edit dialog.

    Provides fill, increment/decrement, invert operations.
    """

    def __init__(self, parent=None, offset=0, length=0):
        super().__init__(parent)
        self._offset = offset
        self._length = length
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("Batch Edit")
        self.resize(520, 430)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            create_dialog_header(
                "Batch Edit",
                "在一个弹窗里完成填充、递增、递减和反转操作，并让参数区与动作区保持统一卡片层级。",
            )
        )

        # Selection info
        info_group = QGroupBox("Selection")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)

        self._offset_label = QLabel(f"Offset: 0x{self._offset:08X}")
        info_layout.addWidget(self._offset_label)

        self._length_label = QLabel(f"Length: {self._length} bytes")
        info_layout.addWidget(self._length_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Operation type
        op_group = QGroupBox("Operation")
        op_layout = QVBoxLayout()
        op_layout.setSpacing(10)

        self._op_group = QButtonGroup()

        fill_btn = QRadioButton("Fill (填充)")
        fill_btn.setChecked(True)
        self._op_group.addButton(fill_btn, 0)
        op_layout.addWidget(fill_btn)

        increment_btn = QRadioButton("Increment (递增 +1)")
        self._op_group.addButton(increment_btn, 1)
        op_layout.addWidget(increment_btn)

        decrement_btn = QRadioButton("Decrement (递减 -1)")
        self._op_group.addButton(decrement_btn, 2)
        op_layout.addWidget(decrement_btn)

        invert_btn = QRadioButton("Invert (按位取反)")
        self._op_group.addButton(invert_btn, 3)
        op_layout.addWidget(invert_btn)

        reverse_btn = QRadioButton("Reverse (字节反转)")
        self._op_group.addButton(reverse_btn, 4)
        op_layout.addWidget(reverse_btn)

        op_group.setLayout(op_layout)
        layout.addWidget(op_group)

        # Fill options
        self._fill_group = QGroupBox("Fill Options")
        fill_options_layout = QVBoxLayout()
        fill_options_layout.setSpacing(10)

        hex_layout = QHBoxLayout()
        hex_layout.addWidget(QLabel("Hex:"))
        self._hex_input = QLineEdit()
        self._hex_input.setPlaceholderText("e.g., 00, FF, AB CD")
        self._hex_input.setText("00")
        hex_layout.addWidget(self._hex_input)
        fill_options_layout.addLayout(hex_layout)

        # Quick fill buttons
        quick_layout = QHBoxLayout()
        zero_btn = QPushButton("Zero (00)")
        zero_btn.clicked.connect(lambda: self._hex_input.setText("00"))
        quick_layout.addWidget(zero_btn)

        ff_btn = QPushButton("FF")
        ff_btn.clicked.connect(lambda: self._hex_input.setText("FF"))
        quick_layout.addWidget(ff_btn)

        aa_btn = QPushButton("AA")
        aa_btn.clicked.connect(lambda: self._hex_input.setText("AA"))
        quick_layout.addWidget(aa_btn)

        quick_layout.addStretch()
        fill_options_layout.addLayout(quick_layout)

        self._fill_group.setLayout(fill_options_layout)
        layout.addWidget(self._fill_group)

        # Increment/Decrement options
        self._num_group = QGroupBox("Number Options")
        num_layout = QVBoxLayout()
        num_layout.setSpacing(10)

        signed_layout = QHBoxLayout()
        signed_layout.addWidget(QLabel("Type:"))
        self._signed_combo = QComboBox()
        self._signed_combo.addItems(["Unsigned", "Signed"])
        signed_layout.addWidget(self._signed_combo)
        num_layout.addLayout(signed_layout)

        overflow_layout = QHBoxLayout()
        overflow_layout.addWidget(QLabel("Overflow:"))
        self._overflow_combo = QComboBox()
        self._overflow_combo.addItems(["Wrap (环绕)", "Clamp (截断)", "Stop (停止)"])
        overflow_layout.addWidget(self._overflow_combo)
        num_layout.addLayout(overflow_layout)

        self._num_group.setLayout(num_layout)
        self._num_group.setVisible(False)
        layout.addWidget(self._num_group)

        # Connect radio buttons to show/hide options
        fill_btn.toggled.connect(lambda: self._update_options(0))
        increment_btn.toggled.connect(lambda: self._update_options(1))
        decrement_btn.toggled.connect(lambda: self._update_options(2))
        invert_btn.toggled.connect(lambda: self._update_options(3))

        # Buttons
        buttons_layout = QHBoxLayout()

        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self._on_preview)
        buttons_layout.addWidget(preview_btn)

        buttons_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.accept)
        apply_btn.setDefault(True)
        buttons_layout.addWidget(apply_btn)

        layout.addLayout(buttons_layout)

        self.setLayout(layout)

    def _update_options(self, op_type):
        """Update visible options based on operation type."""
        self._fill_group.setVisible(op_type == 0)
        self._num_group.setVisible(op_type in (1, 2))

    def _on_preview(self):
        """Show preview of changes."""
        # TODO: Implement preview
        pass

    def get_operation(self):
        """Get selected operation parameters."""
        op_type = self._op_group.checkedId()

        if op_type == 0:
            # Fill
            hex_str = self._hex_input.text().replace(" ", "").replace("-", "")
            try:
                fill_data = bytes.fromhex(hex_str) if hex_str else b'\x00'
            except ValueError:
                fill_data = b'\x00'
            return ("fill", fill_data)
        elif op_type == 1:
            # Increment
            signed = self._signed_combo.currentIndex() == 1
            overflow = self._overflow_combo.currentIndex()
            return ("increment", signed, overflow)
        elif op_type == 2:
            # Decrement
            signed = self._signed_combo.currentIndex() == 1
            overflow = self._overflow_combo.currentIndex()
            return ("decrement", signed, overflow)
        elif op_type == 3:
            # Invert
            return ("invert",)
        elif op_type == 4:
            # Reverse
            return ("reverse",)

        return None
