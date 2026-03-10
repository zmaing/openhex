"""
File Browser Panel

VSCode-like file tree for browsing files and folders.
"""

from datetime import datetime
import html
import os

from PyQt6.QtCore import QEvent, QModelIndex, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QToolTip,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ...utils.format import FormatUtils
from ...utils.mime import MimeTypeDetector


class FileItem(QStandardItem):
    """File system item for tree view."""

    def __init__(self, path: str, is_dir: bool = False, show_hidden: bool = False):
        super().__init__()
        self._path = path
        self._is_dir = is_dir
        self._is_loaded = False
        self._show_hidden = show_hidden

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

    def build_info_tooltip(self) -> str:
        """Build tooltip text for the item."""
        name = html.escape(self.text() or os.path.basename(self._path) or self._path)
        path = html.escape(self._path)

        if self._is_dir:
            return self._build_directory_tooltip(name, path)
        return self._build_file_tooltip(name, path)

    def _build_directory_tooltip(self, name: str, path: str) -> str:
        """Build folder tooltip."""
        try:
            entries = os.listdir(self._path)
            if not self._show_hidden:
                entries = [entry for entry in entries if not entry.startswith(".")]
            item_count = len(entries)
            items_text = f"{item_count} item{'s' if item_count != 1 else ''}"
        except OSError:
            items_text = "Unavailable"

        return (
            "<qt>"
            "<b>Folder Information</b><br>"
            f"<b>Name:</b> {name}<br>"
            "<b>Type:</b> Folder<br>"
            f"<b>Items:</b> {html.escape(items_text)}<br>"
            f"<b>Path:</b> {path}"
            "</qt>"
        )

    def _build_file_tooltip(self, name: str, path: str) -> str:
        """Build file tooltip."""
        try:
            stat = os.stat(self._path)
            size_text = FormatUtils.format_size(stat.st_size)
            modified_text = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            size_text = "Unavailable"
            modified_text = "Unavailable"

        file_type, mime_type = MimeTypeDetector.detect_path(self._path)
        type_text = file_type.upper() if file_type else "UNKNOWN"

        return (
            "<qt>"
            "<b>File Information</b><br>"
            f"<b>Name:</b> {name}<br>"
            f"<b>Size:</b> {html.escape(size_text)}<br>"
            f"<b>Type:</b> {html.escape(type_text)}<br>"
            f"<b>MIME:</b> {html.escape(mime_type)}<br>"
            f"<b>Modified:</b> {html.escape(modified_text)}<br>"
            f"<b>Path:</b> {path}"
            "</qt>"
        )


class FileTreeDelegate(QStyledItemDelegate):
    """Draw an info icon immediately after the file name."""

    _ICON_SIZE = 12
    _ICON_MARGIN_LEFT = 6
    _ICON_MARGIN_RIGHT = 8

    def paint(self, painter, option, index):
        """Paint the row with a trailing info icon."""
        item = self._get_item(index)
        if item is None:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        text_rect = self._text_rect(opt)
        available_width = max(
            0,
            text_rect.width() - self._ICON_SIZE - self._ICON_MARGIN_LEFT - self._ICON_MARGIN_RIGHT,
        )
        opt.text = opt.fontMetrics.elidedText(
            opt.text,
            Qt.TextElideMode.ElideMiddle,
            available_width,
        )

        super().paint(painter, opt, index)

        info_rect = self.info_icon_rect(opt, index)
        if not info_rect.isValid():
            return

        self._paint_info_icon(painter, info_rect, opt)

    def info_icon_rect(self, option, index) -> QRect:
        """Return the info icon rectangle for the given index."""
        item = self._get_item(index)
        if item is None:
            return QRect()

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        text_rect = self._text_rect(opt)
        available_width = max(
            0,
            text_rect.width() - self._ICON_SIZE - self._ICON_MARGIN_LEFT - self._ICON_MARGIN_RIGHT,
        )
        display_text = opt.fontMetrics.elidedText(
            opt.text,
            Qt.TextElideMode.ElideMiddle,
            available_width,
        )
        display_width = opt.fontMetrics.horizontalAdvance(display_text)

        max_x = opt.rect.right() - self._ICON_SIZE - self._ICON_MARGIN_RIGHT
        icon_x = min(text_rect.left() + display_width + self._ICON_MARGIN_LEFT, max_x)
        icon_x = max(icon_x, text_rect.left())
        icon_y = opt.rect.top() + (opt.rect.height() - self._ICON_SIZE) // 2

        return QRect(icon_x, icon_y, self._ICON_SIZE, self._ICON_SIZE)

    def _get_item(self, index) -> FileItem | None:
        """Resolve the file item for the index."""
        if not index.isValid():
            return None

        model = index.model()
        if not hasattr(model, "itemFromIndex"):
            return None

        item = model.itemFromIndex(index)
        return item if isinstance(item, FileItem) else None

    def _text_rect(self, option: QStyleOptionViewItem) -> QRect:
        """Get the text rectangle for the item."""
        widget = option.widget
        style = widget.style() if widget is not None else self.parent().style()
        return style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, widget)

    def _paint_info_icon(self, painter, rect: QRect, option: QStyleOptionViewItem):
        """Paint a compact circled info icon."""
        if option.state & QStyle.StateFlag.State_Selected:
            color = QColor("#ffffff")
        elif option.state & QStyle.StateFlag.State_MouseOver:
            color = QColor("#9CDCFE")
        else:
            color = QColor("#858585")

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect.adjusted(1, 1, -1, -1))

        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(font.pointSize() - 1, 7))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "i")
        painter.restore()


class FileTreeView(QTreeView):
    """Tree view with icon-only hover tooltips."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def tooltip_for_pos(self, pos) -> str:
        """Return the tooltip text if the mouse is over an info icon."""
        index, rect = self._info_hit_test(pos)
        if not index.isValid() or not rect.contains(pos):
            return ""

        model = self.model()
        if not hasattr(model, "itemFromIndex"):
            return ""

        item = model.itemFromIndex(index)
        if not isinstance(item, FileItem):
            return ""

        return item.build_info_tooltip()

    def mouseMoveEvent(self, event):
        """Update cursor only when hovering the info icon."""
        cursor_shape = Qt.CursorShape.ArrowCursor
        _, rect = self._info_hit_test(event.position().toPoint())
        if rect.isValid() and rect.contains(event.position().toPoint()):
            cursor_shape = Qt.CursorShape.PointingHandCursor
        self.viewport().setCursor(cursor_shape)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Restore the default cursor when leaving the tree."""
        self.viewport().unsetCursor()
        super().leaveEvent(event)

    def viewportEvent(self, event):
        """Show tooltip only for the info icon hit area."""
        if event.type() == QEvent.Type.ToolTip:
            tooltip = self.tooltip_for_pos(event.pos())
            if tooltip:
                index = self.indexAt(event.pos())
                QToolTip.showText(event.globalPos(), tooltip, self.viewport(), self.visualRect(index))
            else:
                QToolTip.hideText()
                event.ignore()
            return True

        return super().viewportEvent(event)

    def _info_hit_test(self, pos):
        """Resolve the item index and icon rect for a viewport position."""
        index = self.indexAt(pos)
        if not index.isValid():
            return QModelIndex(), QRect()

        delegate = self.itemDelegateForIndex(index)
        if not hasattr(delegate, "info_icon_rect"):
            return QModelIndex(), QRect()

        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        option.rect = self.visualRect(index)

        return index, delegate.info_icon_rect(option, index)


class FileTreeModel(QStandardItemModel):
    """File tree model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path = ""
        self._show_hidden = False

        # Single tree column; the trailing info icon is painted by a delegate.
        self.setColumnCount(1)

    def set_root_path(self, path: str):
        """Set root path."""
        self._root_path = path
        self.clear()

        if not path or not os.path.isdir(path):
            return

        # Add root item
        root_item = FileItem(path, True, self._show_hidden)
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
            child = FileItem(path, True, self._show_hidden)
            parent_item.appendRow(child)
            # Add placeholder for lazy loading
            child.appendRow(QStandardItem())

        # Add files
        for name in sorted(files):
            path = os.path.join(parent_item.path, name)
            child = FileItem(path, False, self._show_hidden)
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
        self._tree_view = FileTreeView()
        self._model = FileTreeModel()
        self._tree_view.setModel(self._model)
        self._tree_view.setItemDelegate(FileTreeDelegate(self._tree_view))
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
