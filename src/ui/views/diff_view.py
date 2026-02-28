"""
Diff View

File comparison view for binary files.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QSplitter, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class DiffView(QWidget):
    """
    Diff view widget.

    Compares two binary files and shows differences.
    """

    # Signals
    diff_complete = pyqtSignal(object)  # DiffResults

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Diff display
        self._diff_display = self._create_diff_display()
        layout.addWidget(self._diff_display)

        self.setLayout(layout)

    def _create_header(self):
        """Create header."""
        header = QFrame()
        header.setStyleSheet("background-color: #2d2d2d;")
        header.setFixedHeight(40)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 8, 0)

        title = QLabel("File Comparison")
        title.setStyleSheet("color: #cccccc; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        # Compare button
        compare_btn = QPushButton("Compare")
        compare_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
        """)
        compare_btn.clicked.connect(self._on_compare)
        layout.addWidget(compare_btn)

        header.setLayout(layout)
        return header

    def _create_diff_display(self):
        """Create diff display."""
        # Create splitter for two views
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left file view
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        self._left_label = QLabel("Left file: Not loaded")
        self._left_label.setStyleSheet("color: #cccccc; padding: 4px;")
        left_layout.addWidget(self._left_label)

        self._left_view = QTextEdit()
        self._left_view.setReadOnly(True)
        self._left_view.setFont(QFont("Menlo", 10))
        self._left_view.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
        """)
        left_layout.addWidget(self._left_view)

        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # Right file view
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        self._right_label = QLabel("Right file: Not loaded")
        self._right_label.setStyleSheet("color: #cccccc; padding: 4px;")
        right_layout.addWidget(self._right_label)

        self._right_view = QTextEdit()
        self._right_view.setReadOnly(True)
        self._right_view.setFont(QFont("Menlo", 10))
        self._right_view.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
        """)
        right_layout.addWidget(self._right_view)

        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([400, 400])
        return splitter

    def set_files(self, left_path: str, right_path: str):
        """Set files to compare."""
        self._left_path = left_path
        self._right_path = right_path

        # Update labels
        import os
        self._left_label.setText(f"Left: {os.path.basename(left_path)}")
        self._right_label.setText(f"Right: {os.path.basename(right_path)}")

        # Load file contents
        try:
            with open(left_path, 'rb') as f:
                self._left_data = f.read(1024)  # First 1KB
        except:
            self._left_data = b''

        try:
            with open(right_path, 'rb') as f:
                self._right_data = f.read(1024)
        except:
            self._right_data = b''

    def _on_compare(self):
        """Handle compare."""
        if not hasattr(self, '_left_data') or not hasattr(self, '_right_data'):
            return

        # Simple byte-by-byte comparison
        left = self._left_data
        right = self._right_data

        diff_result = []

        # Compare common length
        common_len = min(len(left), len(right))
        for i in range(common_len):
            if left[i] != right[i]:
                diff_result.append({
                    'offset': i,
                    'left': left[i],
                    'right': right[i],
                    'type': 'modified'
                })

        # Check for additions/deletions
        if len(left) < len(right):
            for i in range(len(left), len(right)):
                diff_result.append({
                    'offset': i,
                    'left': None,
                    'right': right[i],
                    'type': 'added'
                })
        elif len(right) < len(left):
            for i in range(len(right), len(left)):
                diff_result.append({
                    'offset': i,
                    'left': left[i],
                    'right': None,
                    'type': 'deleted'
                })

        # Display results
        self._display_diff(diff_result)

        # Emit signal
        self.diff_complete.emit(diff_result)

    def _display_diff(self, diffs):
        """Display diff results."""
        left_text = ""
        right_text = ""

        for diff in diffs[:100]:  # Limit display
            offset = diff['offset']
            left_val = diff['left']
            right_val = diff['right']
            diff_type = diff['type']

            if diff_type == 'modified':
                left_text += f"{offset:08X}: {left_val:02X} -> {right_val:02X}\n"
                right_text += f"{offset:08X}: {right_val:02X} -> {left_val:02X}\n"
            elif diff_type == 'added':
                right_text += f"{offset:08X}: +{right_val:02X}\n"
            elif diff_type == 'deleted':
                left_text += f"{offset:08X}: -{left_val:02X}\n"

        if not diffs:
            left_text = "No differences found (in first 1KB)"
            right_text = "No differences found (in first 1KB)"

        self._left_view.setPlainText(left_text)
        self._right_view.setPlainText(right_text)


class DiffResults:
    """Container for diff results."""

    def __init__(self):
        self.left_path = ""
        self.right_path = ""
        self.differences = []
        self.similarity = 0.0

    @property
    def has_differences(self) -> bool:
        return len(self.differences) > 0

    @property
    def diff_count(self) -> int:
        return len(self.differences)

    def get_summary(self) -> str:
        """Get summary string."""
        if not self.has_differences:
            return "Files are identical"

        return f"Found {self.diff_count} difference(s)"
