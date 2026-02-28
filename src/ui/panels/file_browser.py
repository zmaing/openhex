"""
File Browser Panel

VSCode-like file tree for browsing files and folders.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QTreeView, QLineEdit, QPushButton, QFrame)
from PyQt6.QtCore import Qt, QDir, QModelIndex, pyqtSignal, QAbstractItemModel, QItemSelectionModel
from PyQt6.QtGui import QIcon, QPixmap, QStandardItemModel, QStandardItem, QFileSystemModel

import os


class FileItem(QStandardItem):
    """File system item for tree view."""

    def __init__(self, path: str, is_dir: bool = False):
        super().__init__()
        self._path = path
        self._is_dir = is_dir
        self._is_loaded = False

        # Set display text
        self.setText(os.path.basename(path))

        # Set icon
        self._set_icon()

        # Set editable
        self.setEditable(False)

    def _set_icon(self):
        """Set icon based on file type."""
        if self._is_dir:
            self.setIcon(self._get_folder_icon())
        else:
            self.setIcon(self._get_file_icon())

    def _get_folder_icon(self) -> QIcon:
        """Get folder icon."""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Draw folder icon (simplified)
        from PyQt6.QtGui import QPainter, QColor
        painter = QPainter(pixmap)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#DCAD5D"))
        painter.drawRect(2, 4, 12, 10)
        painter.setBrush(QColor("#C79A4A"))
        painter.drawRect(2, 2, 12, 3)
        painter.end()

        return QIcon(pixmap)

    def _get_file_icon(self) -> QIcon:
        """Get file icon."""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Draw file icon (simplified)
        from PyQt6.QtGui import QPainter, QColor
        painter = QPainter(pixmap)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#6A9955"))
        painter.drawRect(3, 2, 10, 12)
        painter.setBrush(QColor("#5E8C47"))
        painter.drawRect(3, 2, 10, 2)
        painter.end()

        return QIcon(pixmap)

    @property
    def path(self) -> str:
        """Get file path."""
        return self._path

    @property
    def is_dir(self) -> bool:
        """Check if is directory."""
        return self._is_dir


class FileTreeModel(QStandardItemModel):
    """File tree model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path = ""
        self._show_hidden = False

        # Set column count
        self.setColumnCount(1)

    def set_root_path(self, path: str):
        """Set root path."""
        self._root_path = path
        self.clear()

        if not path or not os.path.isdir(path):
            return

        # Add root item
        root_item = FileItem(path, True)
        root_item.setText(os.path.basename(path) or path)
        self.appendRow(root_item)

        # Load children
        self._load_children(root_item)

    def _load_children(self, parent_item: FileItem):
        """Load children of directory."""
        if not parent_item.is_dir:
            return

        try:
            entries = os.listdir(parent_item.path)
        except (PermissionError, OSError):
            return

        # Filter entries
        if not self._show_hidden:
            entries = [e for e in entries if not e.startswith('.')]

        # Sort: directories first, then files
        dirs = []
        files = []
        for entry in entries:
            full_path = os.path.join(parent_item.path, entry)
            if os.path.isdir(full_path):
                dirs.append(entry)
            else:
                files.append(entry)

        # Add directories
        for name in sorted(dirs):
            path = os.path.join(parent_item.path, name)
            child = FileItem(path, True)
            parent_item.appendRow(child)
            # Add placeholder for lazy loading
            child.appendRow(QStandardItem())

        # Add files
        for name in sorted(files):
            path = os.path.join(parent_item.path, name)
            child = FileItem(path, False)
            parent_item.appendRow(child)

        parent_item._is_loaded = True

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        """Check if parent has children."""
        if not parent.isValid():
            return bool(self._root_path)

        item = self.itemFromIndex(parent)
        if isinstance(item, FileItem):
            return item.is_dir
        return False

    def canFetchMore(self, parent: QModelIndex) -> bool:
        """Check if can fetch more."""
        if not parent.isValid():
            return False

        item = self.itemFromIndex(parent)
        if isinstance(item, FileItem):
            return item.is_dir and not item._is_loaded
        return False

    def fetchMore(self, parent: QModelIndex):
        """Fetch more children."""
        if not parent.isValid():
            return

        item = self.itemFromIndex(parent)
        if isinstance(item, FileItem) and item.is_dir:
            # Clear placeholder
            item.removeRows(0, item.rowCount())
            # Load children
            self._load_children(item)


class FileBrowser(QWidget):
    """
    File browser panel.

    Displays a file tree for navigating and opening files.
    """

    # Signals
    file_selected = pyqtSignal(str)  # File path
    file_double_clicked = pyqtSignal(str)  # File path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path = ""
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Path bar
        self._path_bar = QLineEdit()
        self._path_bar.setPlaceholderText("Enter folder path...")
        self._path_bar.setStyleSheet("""
            QLineEdit {
                background-color: #2d2d2d;
                color: #cccccc;
                border: none;
                padding: 4px 8px;
            }
        """)
        self._path_bar.returnPressed.connect(self._on_path_entered)
        layout.addWidget(self._path_bar)

        # Tree view - create first so header can use it
        self._tree_view = QTreeView()
        self._model = FileTreeModel()
        self._tree_view.setModel(self._model)
        self._tree_view.setAnimated(True)
        self._tree_view.setIndentation(16)
        self._tree_view.setSortingEnabled(True)
        self._tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._tree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self._tree_view.setHeaderHidden(True)

        # Connect signals
        self._tree_view.clicked.connect(self._on_item_clicked)
        self._tree_view.doubleClicked.connect(self._on_item_double_clicked)
        self._tree_view.expanded.connect(self._on_item_expanded)

        # Style
        self._tree_view.setStyleSheet("""
            QTreeView {
                background-color: #252526;
                color: #cccccc;
                border: none;
            }
            QTreeView::item {
                padding: 2px;
            }
            QTreeView::item:hover {
                background-color: #2a2d2e;
            }
            QTreeView::item:selected {
                background-color: #264f78;
                color: #ffffff;
            }
        """)

        layout.addWidget(self._tree_view)
        self.setLayout(layout)

    def _create_header(self):
        """Create header with title and buttons."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-bottom: 1px solid #3c3c3c;
            }
        """)
        header.setFixedHeight(32)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 8, 0)

        # Title
        title = QLabel("Explorer")
        title.setStyleSheet("color: #cccccc; font-weight: bold;")
        layout.addWidget(title)

        layout.addStretch()

        # Buttons
        btn_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                color: #cccccc;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
        """

        # Refresh button
        refresh_btn = QPushButton("⟳")
        refresh_btn.setStyleSheet(btn_style)
        refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(refresh_btn)

        # Collapse button
        collapse_btn = QPushButton("⊟")
        collapse_btn.setStyleSheet(btn_style)
        collapse_btn.clicked.connect(self._collapse_all)
        layout.addWidget(collapse_btn)

        header.setLayout(layout)
        return header

    def set_root_path(self, path: str):
        """Set root path."""
        if not path or not os.path.isdir(path):
            return

        self._root_path = path
        self._path_bar.setText(path)
        self._model.set_root_path(path)

    def get_root_path(self) -> str:
        """Get root path."""
        return self._root_path

    def _on_path_entered(self):
        """Handle path entry."""
        path = self._path_bar.text().strip()
        if path:
            self.set_root_path(path)

    def _on_item_clicked(self, index: QModelIndex):
        """Handle item click."""
        item = self._model.itemFromIndex(index)
        if isinstance(item, FileItem):
            if not item.is_dir:
                self.file_selected.emit(item.path)

    def _on_item_double_clicked(self, index: QModelIndex):
        """Handle item double click."""
        item = self._model.itemFromIndex(index)
        if isinstance(item, FileItem):
            if not item.is_dir:
                self.file_double_clicked.emit(item.path)
            else:
                # Toggle directory expansion
                if self._tree_view.isExpanded(index):
                    self._tree_view.collapse(index)
                else:
                    self._tree_view.expand(index)

    def _on_item_expanded(self, index: QModelIndex):
        """Handle item expansion."""
        # Trigger lazy loading
        self._model.fetchMore(index)

    def _collapse_all(self):
        """Collapse all tree items."""
        if hasattr(self, '_tree_view'):
            self._tree_view.collapseAll()

    def _on_refresh(self):
        """Handle refresh."""
        if self._root_path:
            self.set_root_path(self._root_path)
