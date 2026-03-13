"""
File Browser Panel

VSCode-like file tree for browsing files and folders.
"""

from datetime import datetime
import html
import os

from PyQt6.QtCore import QEvent, QModelIndex, QRect, QSize, Qt, QTimer, QItemSelectionModel, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QToolButton,
    QToolTip,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ...utils.format import FormatUtils
from ...utils.mime import MimeTypeDetector
from ..design_system import CHROME, panel_surface_qss


def _normalize_path(path: str | None) -> str:
    """Return a platform-safe normalized path for comparisons."""
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _build_folder_icon(*, root: bool = False) -> QIcon:
    """Build the shared folder icon used in the explorer."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#6287B8" if root else "#4F6E96"))
    painter.drawRoundedRect(1, 4, 14, 10, 2.5, 2.5)
    painter.setBrush(QColor("#90AFD7" if root else "#7896BC"))
    painter.drawRoundedRect(3, 2, 6, 4, 2, 2)
    painter.setBrush(QColor("#7398C7" if root else "#5F81AE"))
    painter.drawRoundedRect(2, 5, 12, 7, 2, 2)
    painter.end()

    return QIcon(pixmap)


def _build_file_icon() -> QIcon:
    """Build the shared muted file icon used in the explorer."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#7F8897"))
    painter.setBrush(QColor("#D8DEE7"))
    path = QPainterPath()
    path.moveTo(3.5, 1.5)
    path.lineTo(10.5, 1.5)
    path.lineTo(13.0, 4.0)
    path.lineTo(13.0, 14.5)
    path.lineTo(3.5, 14.5)
    path.closeSubpath()
    painter.drawPath(path)
    painter.setBrush(QColor("#BCC6D5"))
    fold = QPainterPath()
    fold.moveTo(10.5, 1.5)
    fold.lineTo(10.5, 4.8)
    fold.lineTo(13.0, 4.8)
    fold.closeSubpath()
    painter.drawPath(fold)
    painter.setPen(QColor("#8D98AB"))
    painter.drawLine(5, 7, 11, 7)
    painter.drawLine(5, 10, 11, 10)
    painter.end()

    return QIcon(pixmap)


class FileItem(QStandardItem):
    """File system item for tree view."""

    def __init__(
        self,
        path: str,
        is_dir: bool = False,
        show_hidden: bool = False,
        *,
        is_root: bool = False,
    ):
        super().__init__()
        self._path = path
        self._is_dir = is_dir
        self._is_loaded = False
        self._show_hidden = show_hidden
        self._is_root = is_root

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
        return _build_folder_icon(root=self._is_root)

    def _get_file_icon(self) -> QIcon:
        """Get file icon."""
        return _build_file_icon()

    @property
    def path(self) -> str:
        """Get file path."""
        return self._path

    @property
    def is_dir(self) -> bool:
        """Check if is directory."""
        return self._is_dir

    @property
    def is_root(self) -> bool:
        """Check if this item represents the current workspace root."""
        return self._is_root

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
    """Elide long file names while keeping hover detection on the text itself."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_file_path = ""

    @property
    def active_file_path(self) -> str:
        """Return the normalized active file path."""
        return self._active_file_path

    def set_active_file_path(self, path: str | None) -> None:
        """Set the file path that should keep a subtle active-state marker."""
        self._active_file_path = _normalize_path(path)
        parent = self.parent()
        if parent is not None and hasattr(parent, "viewport"):
            parent.viewport().update()

    def paint(self, painter, option, index):
        """Paint the row using a middle-elided file name."""
        item = self._get_item(index)
        if item is None:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        active_file = self._is_active_file(item)
        root_directory = item.is_root and item.is_dir
        accent_fill = QColor(CHROME.accent)
        accent_fill.setAlpha(20)
        active_marker = QColor(CHROME.accent_hover)
        active_marker.setAlpha(210)

        painter.save()
        row_rect = option.rect.adjusted(2, 1, -2, -1)
        if selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(CHROME.surface_raised))
            painter.drawRoundedRect(row_rect, 6, 6)
            accent_rect = QRect(
                row_rect.left(),
                row_rect.top() + 3,
                1,
                max(6, row_rect.height() - 6),
            )
            painter.setBrush(QColor(CHROME.accent))
            painter.drawRoundedRect(accent_rect, 1, 1)
        elif active_file:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent_fill)
            painter.drawRoundedRect(row_rect, 6, 6)

            marker_rect = QRect(row_rect.left(), row_rect.top() + 4, 1, max(6, row_rect.height() - 8))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(active_marker)
            painter.drawRoundedRect(marker_rect, 1, 1)
        elif hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(CHROME.surface_alt))
            painter.drawRoundedRect(row_rect, 6, 6)
        painter.restore()

        text_rect = self._text_rect(opt)
        opt.text = opt.fontMetrics.elidedText(
            opt.text,
            Qt.TextElideMode.ElideMiddle,
            max(0, text_rect.width()),
        )
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        opt.backgroundBrush = QBrush(Qt.BrushStyle.NoBrush)
        if selected or active_file or root_directory:
            opt.palette.setColor(QPalette.ColorRole.Text, QColor(CHROME.text_primary))
            opt.palette.setColor(QPalette.ColorRole.WindowText, QColor(CHROME.text_primary))
        else:
            opt.palette.setColor(QPalette.ColorRole.Text, QColor(CHROME.text_secondary))
            opt.palette.setColor(QPalette.ColorRole.WindowText, QColor(CHROME.text_secondary))
        if root_directory:
            opt.font.setWeight(QFont.Weight.DemiBold)
        if active_file:
            opt.font.setWeight(QFont.Weight.Medium)

        super().paint(painter, opt, index)

    def text_hit_rect(self, option, index) -> QRect:
        """Return the hover-sensitive rectangle for the displayed file name."""
        item = self._get_item(index)
        if item is None:
            return QRect()

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        text_rect = self._text_rect(opt)
        display_text = opt.fontMetrics.elidedText(
            opt.text,
            Qt.TextElideMode.ElideMiddle,
            max(0, text_rect.width()),
        )
        if not display_text:
            return QRect()

        display_width = opt.fontMetrics.horizontalAdvance(display_text)
        return self._text_hit_rect(text_rect, display_width)

    def _get_item(self, index) -> FileItem | None:
        """Resolve the file item for the index."""
        if not index.isValid():
            return None

        model = index.model()
        if not hasattr(model, "itemFromIndex"):
            return None

        item = model.itemFromIndex(index)
        return item if isinstance(item, FileItem) else None

    def _is_active_file(self, item: FileItem) -> bool:
        """Return whether the item maps to the active editor file."""
        return (not item.is_dir) and _normalize_path(item.path) == self._active_file_path

    def _text_rect(self, option: QStyleOptionViewItem) -> QRect:
        """Get the text rectangle for the item."""
        widget = option.widget
        style = widget.style() if widget is not None else self.parent().style()
        return style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, widget)

    @classmethod
    def _text_hit_rect(cls, text_rect: QRect, display_width: int) -> QRect:
        """Clamp the interactive text area to the actually drawn label width."""
        return QRect(
            text_rect.left(),
            text_rect.top(),
            max(0, min(text_rect.width(), display_width)),
            text_rect.height(),
        )


class FileTreeView(QTreeView):
    """Tree view with tooltips shown when hovering file names."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def drawBranches(self, painter, rect, index):
        """Draw VS Code-like disclosure chevrons without connector lines."""
        model = self.model()
        if model is None or not model.hasChildren(index):
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(
            QColor(CHROME.text_secondary if self.isExpanded(index) else CHROME.text_muted)
        )
        pen.setWidthF(1.1)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        center_x = rect.center().x()
        center_y = rect.center().y()
        if self.isExpanded(index):
            painter.drawLine(center_x - 2, center_y - 1, center_x, center_y + 1)
            painter.drawLine(center_x, center_y + 1, center_x + 2, center_y - 1)
        else:
            painter.drawLine(center_x - 1, center_y - 2, center_x + 1, center_y)
            painter.drawLine(center_x + 1, center_y, center_x - 1, center_y + 2)
        painter.restore()

    def tooltip_for_pos(self, pos) -> str:
        """Return the tooltip text if the mouse is over a file name."""
        index, rect = self._text_hit_test(pos)
        if not index.isValid() or not rect.contains(pos):
            return ""

        model = self.model()
        if not hasattr(model, "itemFromIndex"):
            return ""

        item = model.itemFromIndex(index)
        if not isinstance(item, FileItem):
            return ""

        return item.build_info_tooltip()

    def viewportEvent(self, event):
        """Show tooltip only for the file name hit area."""
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

    def _text_hit_test(self, pos):
        """Resolve the item index and text rect for a viewport position."""
        index = self.indexAt(pos)
        if not index.isValid():
            return QModelIndex(), QRect()

        delegate = self.itemDelegateForIndex(index)
        if not hasattr(delegate, "text_hit_rect"):
            return QModelIndex(), QRect()

        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        option.rect = self.visualRect(index)

        return index, delegate.text_hit_rect(option, index)


class FileTreeModel(QStandardItemModel):
    """File tree model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path = ""
        self._show_hidden = False

        # Single tree column; long names are middle-elided by a delegate.
        self.setColumnCount(1)

    def set_root_path(self, path: str):
        """Set root path."""
        self._root_path = path
        self.clear()

        if not path or not os.path.isdir(path):
            return

        # Add root item
        root_item = FileItem(path, True, self._show_hidden, is_root=True)
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
        self._active_file_path = ""
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setObjectName("fileBrowserPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            panel_surface_qss("QWidget#fileBrowserPanel")
            + f"""
            QWidget#fileBrowserHeader {{
                background: transparent;
                border: none;
            }}
            QLabel#fileBrowserTitle {{
                color: {CHROME.text_muted};
                font-size: 10px;
                font-weight: 700;
                padding-left: 2px;
            }}
            QTreeView#fileBrowserTree {{
                background-color: transparent;
                color: {CHROME.text_secondary};
                border: none;
                border-radius: 0px;
                padding: 2px 0px;
                outline: none;
                show-decoration-selected: 0;
            }}
            QTreeView#fileBrowserTree::branch {{
                background: transparent;
            }}
            QTreeView#fileBrowserTree::branch:selected {{
                background: transparent;
            }}
            QTreeView#fileBrowserTree::item {{
                height: {CHROME.row_height}px;
                padding: 1px 5px;
                border-radius: 5px;
            }}
            QTreeView#fileBrowserTree::item:hover {{
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_primary};
            }}
            QTreeView#fileBrowserTree::item:selected {{
                background-color: {CHROME.surface_raised};
                color: {CHROME.text_primary};
            }}
            QToolButton#fileBrowserHeaderButton {{
                background-color: transparent;
                color: {CHROME.text_secondary};
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 0;
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
            }}
            QToolButton#fileBrowserHeaderButton:hover {{
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_primary};
                border-color: {CHROME.border};
            }}
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Tree view - create first so header can use it
        self._tree_view = FileTreeView()
        self._tree_view.setObjectName("fileBrowserTree")
        self._model = FileTreeModel()
        self._tree_view.setModel(self._model)
        self._delegate = FileTreeDelegate(self._tree_view)
        self._tree_view.setItemDelegate(self._delegate)
        self._tree_view.setAnimated(True)
        self._tree_view.setIndentation(12)
        self._tree_view.setIconSize(QSize(13, 13))
        self._tree_view.setUniformRowHeights(True)
        # The model already inserts children in sorted order. Keeping view-level
        # sorting enabled on a lazily loaded tree can reorder rows during
        # expansion and destabilize Qt's internal layout bookkeeping on macOS.
        self._tree_view.setSortingEnabled(False)
        self._tree_view.setSelectionMode(QTreeView.SelectionMode.SingleSelection)
        self._tree_view.setHeaderHidden(True)
        # Directory expansion is handled explicitly in _on_item_double_clicked.
        # Leaving Qt's default double-click expansion enabled causes the same
        # directory toggle to run twice and can race with lazy loading.
        self._tree_view.setExpandsOnDoubleClick(False)

        # Connect signals
        self._tree_view.clicked.connect(self._on_item_clicked)
        self._tree_view.doubleClicked.connect(self._on_item_double_clicked)

        layout.addWidget(self._tree_view)
        self.setLayout(layout)

    def _create_header(self):
        """Create header with title and buttons."""
        header = QFrame()
        header.setObjectName("fileBrowserHeader")
        header.setFixedHeight(24)

        layout = QHBoxLayout()
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(6)

        # Title
        title = QLabel("EXPLORER")
        title.setObjectName("fileBrowserTitle")
        layout.addWidget(title)

        layout.addStretch()

        # Refresh button
        refresh_btn = self._create_header_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
            "Refresh workspace",
        )
        refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(refresh_btn)

        # Collapse button
        collapse_btn = self._create_header_button(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp),
            "Collapse all",
        )
        collapse_btn.clicked.connect(self._collapse_all)
        layout.addWidget(collapse_btn)

        header.setLayout(layout)
        return header

    def _create_header_button(self, icon: QIcon, tooltip: str) -> QToolButton:
        """Create a compact header action button."""
        button = QToolButton(self)
        button.setObjectName("fileBrowserHeaderButton")
        button.setIcon(icon)
        button.setIconSize(QSize(12, 12))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setAutoRaise(False)
        return button

    def set_root_path(self, path: str):
        """Set root path."""
        if not path or not os.path.isdir(path):
            return

        self._root_path = path
        self._model.set_root_path(path)
        self._sync_active_file_index()

    def get_root_path(self) -> str:
        """Get root path."""
        return self._root_path

    def set_active_file(self, path: str | None) -> None:
        """Keep the active editor file visible and visually marked in the tree."""
        self._active_file_path = _normalize_path(path)
        self._delegate.set_active_file_path(path)
        self._sync_active_file_index()

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
                # Defer toggling until the current mouse event fully unwinds.
                QTimer.singleShot(0, lambda idx=index: self._toggle_directory(idx))

    def _toggle_directory(self, index: QModelIndex):
        """Expand or collapse a directory outside the active mouse event."""
        if not index.isValid():
            return
        if self._tree_view.isExpanded(index):
            self._tree_view.collapse(index)
        else:
            self._tree_view.expand(index)

    def _collapse_all(self):
        """Collapse all tree items."""
        if hasattr(self, '_tree_view'):
            self._tree_view.collapseAll()

    def _on_refresh(self):
        """Handle refresh."""
        if self._root_path:
            self.set_root_path(self._root_path)

    def _sync_active_file_index(self) -> None:
        """Reveal and select the active file when it lives inside the current root."""
        if not self._active_file_path:
            self._tree_view.viewport().update()
            return

        index = self._index_for_path(self._active_file_path)
        if not index.isValid():
            self._tree_view.viewport().update()
            return

        root_index = self._model.index(0, 0)
        if root_index.isValid():
            self._tree_view.expand(root_index)

        selection_model = self._tree_view.selectionModel()
        if selection_model is not None:
            selection_model.setCurrentIndex(
                index,
                QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QItemSelectionModel.SelectionFlag.Rows,
            )
        self._tree_view.setCurrentIndex(index)
        self._tree_view.scrollTo(index, QTreeView.ScrollHint.PositionAtCenter)
        self._tree_view.viewport().update()

    def _index_for_path(self, path: str) -> QModelIndex:
        """Return the model index for a path, loading intermediate folders as needed."""
        normalized_root = _normalize_path(self._root_path)
        if not normalized_root or not path:
            return QModelIndex()

        try:
            if os.path.commonpath([normalized_root, path]) != normalized_root:
                return QModelIndex()
        except ValueError:
            return QModelIndex()

        root_item = self._model.item(0, 0)
        if not isinstance(root_item, FileItem):
            return QModelIndex()

        root_index = self._model.indexFromItem(root_item)
        if path == normalized_root:
            return root_index

        relative_path = os.path.relpath(path, normalized_root)
        current_item = root_item
        current_index = root_index

        for segment in [part for part in relative_path.split(os.sep) if part and part != os.curdir]:
            if self._model.canFetchMore(current_index):
                self._model.fetchMore(current_index)

            child_item = self._find_child_item(current_item, segment)
            if child_item is None:
                return QModelIndex()

            current_index = self._model.indexFromItem(child_item)
            current_item = child_item

            if child_item.is_dir:
                self._tree_view.expand(current_index)

        return current_index

    @staticmethod
    def _find_child_item(parent_item: FileItem, name: str) -> FileItem | None:
        """Find a direct child item by file-system name."""
        target_name = os.path.normcase(name)
        for row in range(parent_item.rowCount()):
            child = parent_item.child(row, 0)
            if isinstance(child, FileItem) and os.path.normcase(child.text()) == target_name:
                return child
        return None
