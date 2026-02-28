"""
Bookmarks Panel

Displays and manages bookmarks.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal


class BookmarksPanel(QWidget):
    """
    Bookmarks panel.

    Displays list of bookmarks and allows navigation.
    """

    # Signals
    bookmark_selected = pyqtSignal(int)  # Offset

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_handle = None
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Bookmarks")
        title.setStyleSheet("font-weight: bold; color: #cccccc;")
        layout.addWidget(title)

        # Bookmarks list
        self._bookmarks_list = QListWidget()
        self._bookmarks_list.itemDoubleClicked.connect(self._on_bookmark_clicked)
        layout.addWidget(self._bookmarks_list)

        # Buttons
        btn_layout = QHBoxLayout()

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._on_remove_bookmark)
        btn_layout.addWidget(remove_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_bookmarks)
        btn_layout.addWidget(clear_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def set_file_handle(self, file_handle):
        """Set file handle to track."""
        self._file_handle = file_handle
        self._refresh_bookmarks()

    def _refresh_bookmarks(self):
        """Refresh bookmarks list."""
        self._bookmarks_list.clear()

        if not self._file_handle:
            return

        bookmarks = self._file_handle.bookmarks
        for offset in bookmarks:
            item = QListWidgetItem(f"0x{offset:08X}")
            item.setData(Qt.ItemDataRole.UserRole, offset)
            self._bookmarks_list.addItem(item)

    def _on_bookmark_clicked(self, item):
        """Handle bookmark clicked."""
        offset = item.data(Qt.ItemDataRole.UserRole)
        if offset is not None:
            self.bookmark_selected.emit(offset)

    def _on_remove_bookmark(self):
        """Remove selected bookmark."""
        current_item = self._bookmarks_list.currentItem()
        if current_item and self._file_handle:
            offset = current_item.data(Qt.ItemDataRole.UserRole)
            if offset is not None:
                self._file_handle.remove_bookmark(offset)
                self._refresh_bookmarks()

    def _on_clear_bookmarks(self):
        """Clear all bookmarks."""
        if self._file_handle:
            # Clear all bookmarks
            bookmarks = self._file_handle.bookmarks.copy()
            for offset in bookmarks:
                self._file_handle.remove_bookmark(offset)
            self._refresh_bookmarks()

    def update(self):
        """Update bookmarks display."""
        self._refresh_bookmarks()
