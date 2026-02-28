"""
File Info Panel

Displays file information.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QFont

from ...utils.format import FormatUtils


class FileInfoPanel(QWidget):
    """
    File information panel.

    Displays file metadata and checksums.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("File Information")
        title.setStyleSheet("font-weight: bold; color: #cccccc;")
        layout.addWidget(title)

        # File name
        self._name_label = QLabel("-")
        self._name_label.setWordWrap(True)
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self._name_label)

        # File size
        self._size_label = QLabel("0 B")
        layout.addWidget(QLabel("Size:"))
        layout.addWidget(self._size_label)

        # File type
        self._type_label = QLabel("-")
        layout.addWidget(QLabel("Type:"))
        layout.addWidget(self._type_label)

        # Path
        self._path_label = QLabel("-")
        self._path_label.setWordWrap(True)
        layout.addWidget(QLabel("Path:"))
        layout.addWidget(self._path_label)

        # Checksums section
        checksum_label = QLabel("Checksums")
        checksum_label.setStyleSheet("font-weight: bold; margin-top: 8px; color: #cccccc;")
        layout.addWidget(checksum_label)

        self._md5_label = QLabel("-")
        self._md5_label.setFont(QFont("Monospace", 9))
        self._md5_label.setWordWrap(True)
        layout.addWidget(QLabel("MD5:"))
        layout.addWidget(self._md5_label)

        self._sha256_label = QLabel("-")
        self._sha256_label.setFont(QFont("Monospace", 9))
        self._sha256_label.setWordWrap(True)
        layout.addWidget(QLabel("SHA256:"))
        layout.addWidget(self._sha256_label)

        layout.addStretch()
        self.setLayout(layout)

    def update_file_info(self, file_handle):
        """Update panel with file information."""
        if not file_handle:
            self._name_label.setText("-")
            self._size_label.setText("0 B")
            self._type_label.setText("-")
            self._path_label.setText("-")
            self._md5_label.setText("-")
            self._sha256_label.setText("-")
            return

        self._name_label.setText(file_handle.file_name)
        self._size_label.setText(FormatUtils.format_size(file_handle.file_size))

        # File type
        file_type = file_handle.file_type.name if hasattr(file_handle, 'file_type') else 'UNKNOWN'
        self._type_label.setText(file_type)

        # Path
        self._path_label.setText(file_handle.file_path or "Untitled")

        # Checksums
        if file_handle.file_size < 100 * 1024 * 1024:  # 100MB
            self._md5_label.setText("Click to calculate...")
            self._sha256_label.setText("Click to calculate...")
        else:
            self._md5_label.setText("(too large)")
            self._sha256_label.setText("(too large)")
