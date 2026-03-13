"""
Import/Export Dialog

导入/导出对话框
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QGroupBox, QRadioButton, QButtonGroup,
                             QTextEdit, QFileDialog, QLineEdit)
from PyQt6.QtCore import Qt

from .chrome import create_dialog_header


class ImportExportDialog(QDialog):
    """
    Import/Export dialog.

    Import data from text or export to various formats.
    """

    def __init__(self, parent=None, mode="export"):
        super().__init__(parent)
        self._mode = mode  # "import" or "export"
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        if self._mode == "import":
            self.setWindowTitle("Import Data")
            self.resize(560, 470)
        else:
            self.setWindowTitle("Export Data")
            self.resize(560, 500)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        if self._mode == "import":
            layout.addWidget(
                create_dialog_header(
                    "Import Data",
                    "把外部文本或数组格式导入当前缓冲区，并与导出流程共用统一的苹果式弹窗结构。",
                )
            )
        else:
            layout.addWidget(
                create_dialog_header(
                    "Export Data",
                    "按格式和范围导出当前数据，输出区、参数区和动作区保持一致的层级关系。",
                )
            )

        if self._mode == "import":
            self._init_import_ui(layout)
        else:
            self._init_export_ui(layout)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        if self._mode == "import":
            import_btn = QPushButton("Import")
            import_btn.clicked.connect(self.accept)
            import_btn.setDefault(True)
            btn_layout.addWidget(import_btn)
        else:
            export_btn = QPushButton("Export")
            export_btn.clicked.connect(self.accept)
            export_btn.setDefault(True)
            btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _init_import_ui(self, layout):
        """Initialize import UI."""
        # Format selection
        format_group = QGroupBox("Import Format")
        format_layout = QVBoxLayout()
        format_layout.setSpacing(10)

        self._format_group = QButtonGroup()

        hex_text_btn = QRadioButton("Hex Text (48 65 6C 6C 6F)")
        hex_text_btn.setChecked(True)
        self._format_group.addButton(hex_text_btn, 0)
        format_layout.addWidget(hex_text_btn)

        c_array_btn = QRadioButton("C Array ({ 0x48, 0x65, ... })")
        self._format_group.addButton(c_array_btn, 1)
        format_layout.addWidget(c_array_btn)

        python_list_btn = QRadioButton("Python List ([0x48, 0x65, ...])")
        self._format_group.addButton(python_list_btn, 2)
        format_layout.addWidget(python_list_btn)

        raw_text_btn = QRadioButton("Raw Text")
        self._format_group.addButton(raw_text_btn, 3)
        format_layout.addWidget(raw_text_btn)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # Input
        layout.addWidget(QLabel("Data:"))
        self._input_text = QTextEdit()
        self._input_text.setPlaceholderText("Enter hex data or paste from clipboard...")
        layout.addWidget(self._input_text)

    def _init_export_ui(self, layout):
        """Initialize export UI."""
        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QVBoxLayout()
        format_layout.setSpacing(10)

        self._format_group = QButtonGroup()

        hex_text_btn = QRadioButton("Hex Text (48 65 6C 6C 6F)")
        hex_text_btn.setChecked(True)
        self._format_group.addButton(hex_text_btn, 0)
        format_layout.addWidget(hex_text_btn)

        c_array_btn = QRadioButton("C Array")
        self._format_group.addButton(c_array_btn, 1)
        format_layout.addWidget(c_array_btn)

        python_list_btn = QRadioButton("Python List")
        self._format_group.addButton(python_list_btn, 2)
        format_layout.addWidget(python_list_btn)

        binary_btn = QRadioButton("Binary File")
        self._format_group.addButton(binary_btn, 3)
        format_layout.addWidget(binary_btn)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # Export range
        range_group = QGroupBox("Export Range")
        range_layout = QHBoxLayout()
        range_layout.setSpacing(8)

        range_layout.addWidget(QLabel("Offset:"))
        self._offset_input = QLineEdit("0")
        range_layout.addWidget(self._offset_input)

        range_layout.addWidget(QLabel("Length:"))
        self._length_input = QLineEdit("-1 (all)")
        range_layout.addWidget(self._length_input)

        range_group.setLayout(range_layout)
        layout.addWidget(range_group)

        # Output
        layout.addWidget(QLabel("Output:"))
        self._output_text = QTextEdit()
        self._output_text.setReadOnly(True)
        layout.addWidget(self._output_text)

        # Copy/Save buttons
        action_layout = QHBoxLayout()

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self._on_copy)
        action_layout.addWidget(copy_btn)

        save_btn = QPushButton("Save to File...")
        save_btn.clicked.connect(self._on_save)
        action_layout.addWidget(save_btn)

        layout.addLayout(action_layout)

    def get_import_data(self) -> bytes:
        """Get imported data."""
        if self._mode != "import":
            return b""

        text = self._input_text.toPlainText()
        fmt = self._format_group.checkedId()

        try:
            if fmt == 0:  # Hex text
                hex_str = text.replace(" ", "").replace("\n", "").replace("-", "")
                return bytes.fromhex(hex_str)
            elif fmt == 1:  # C array
                import re
                # Extract hex values from { 0x48, 0x65, ... }
                matches = re.findall(r'0x([0-9a-fA-F]{2})', text)
                return bytes.fromhex("".join(matches))
            elif fmt == 2:  # Python list
                import re
                # Extract values from [0x48, 0x65, ...]
                matches = re.findall(r'0x([0-9a-fA-F]{2})', text)
                return bytes.fromhex("".join(matches))
            elif fmt == 3:  # Raw text
                return text.encode('utf-8')
        except Exception:
            return b""

        return b""

    def set_export_data(self, data: bytes):
        """Set data to export."""
        if self._mode != "export":
            return

        self._data = data
        self._update_output()

    def _update_output(self):
        """Update export output."""
        if not hasattr(self, '_data'):
            return

        data = self._data
        fmt = self._format_group.checkedId()

        if fmt == 0:  # Hex text
            output = " ".join(f"{b:02X}" for b in data)
        elif fmt == 1:  # C array
            lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_str = ", ".join(f"0x{b:02X}" for b in chunk)
                lines.append(f"    {hex_str},")
            output = "{\n" + "\n".join(lines) + "\n}"
        elif fmt == 2:  # Python list
            lines = []
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_str = ", ".join(f"0x{b:02X}" for b in chunk)
                lines.append(f"    {hex_str},")
            output = "[\n" + "\n".join(lines) + "\n]"
        elif fmt == 3:  # Binary
            output = f"<{len(data)} bytes>"

        self._output_text.setPlainText(output)

    def _on_copy(self):
        """Copy to clipboard."""
        text = self._output_text.toPlainText()
        clipboard = self.window().clipboard()
        clipboard.setText(text)

    def _on_save(self):
        """Save to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Export", "", "All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'wb') as f:
                    f.write(self._data)
            except Exception as e:
                pass


# Import QLineEdit
from PyQt6.QtWidgets import QLineEdit
