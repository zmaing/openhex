"""
Structure View

结构化视图 - 显示解析后的数据结构
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                             QLabel, QComboBox, QPushButton, QGroupBox)
from PyQt6.QtCore import Qt

from ...core.parser.template_manager import TemplateManager


class StructureViewPanel(QWidget):
    """
    Structure view panel.

    Displays parsed binary structure using templates.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self._template_manager = TemplateManager(self)
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        # Template selection
        group = QGroupBox("Structure Template")
        group_layout = QVBoxLayout()

        self._template_combo = QComboBox()
        self._template_combo.addItems(self._template_manager.get_template_names())
        self._template_combo.currentTextChanged.connect(self._on_template_changed)
        group_layout.addWidget(self._template_combo)

        # Auto-detect button
        auto_btn = QPushButton("Auto-Detect")
        auto_btn.clicked.connect(self._on_auto_detect)
        group_layout.addWidget(auto_btn)

        group.setLayout(group_layout)
        layout.addWidget(group)

        # Structure tree
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Field", "Value", "Description"])
        self._tree.setColumnWidth(0, 150)
        self._tree.setColumnWidth(1, 150)
        layout.addWidget(self._tree)

        self.setLayout(layout)

    def set_data(self, data: bytes):
        """Set data to parse."""
        self._data = data
        self._on_template_changed(self._template_combo.currentText())

    def _on_template_changed(self, template_name: str):
        """Handle template selection changed."""
        self._tree.clear()

        if not self._data:
            return

        template = self._template_manager.get_template(template_name)
        if not template:
            return

        # Parse data using template
        self._parse_template(template)

    def _parse_template(self, template):
        """Parse data using template."""
        if not self._data:
            return

        # Add root item
        root = QTreeWidgetItem([template.name, "", template.description or ""])
        self._tree.addTopLevelItem(root)

        # Add field items
        for field in template.fields:
            offset = field.get("offset", 0)
            size = field.get("size", 0)
            field_type = field.get("type", "bytes")
            name = field.get("name", "")
            desc = field.get("desc", "")

            # Read value
            value = self._read_value(offset, size, field_type)

            item = QTreeWidgetItem([name, value, desc])
            item.setData(0, Qt.ItemDataRole.UserRole, offset)
            root.addChild(item)

        root.setExpanded(True)

    def _read_value(self, offset: int, size: int, field_type: str) -> str:
        """Read and format value."""
        if offset + size > len(self._data):
            return "(out of range)"

        try:
            data = self._data[offset:offset + size]

            if field_type == "bytes":
                return " ".join(f"{b:02X}" for b in data)
            elif field_type == "uint8":
                return str(data[0])
            elif field_type == "uint16":
                return str(int.from_bytes(data, 'little'))
            elif field_type == "uint32":
                return str(int.from_bytes(data, 'little'))
            elif field_type == "int32":
                val = int.from_bytes(data, 'little', signed=True)
                return str(val)
            else:
                return " ".join(f"{b:02X}" for b in data)
        except Exception as e:
            return f"Error: {e}"

    def _on_auto_detect(self):
        """Auto-detect file format."""
        if not self._data:
            return

        format_name = self._template_manager.detect_format(self._data)
        if format_name:
            index = self._template_combo.findText(format_name)
            if index >= 0:
                self._template_combo.setCurrentIndex(index)
        else:
            # Clear tree if no format detected
            self._tree.clear()
