"""
HexEditor Main Window

Main hex editor widget with panels and views.
"""

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QTabWidget, QLabel, QProgressBar, QFrame, QToolButton,
                             QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QSettings, QTimer
from typing import List
from pathlib import Path
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

import os
import hashlib
import json

from ..models.document import DocumentModel
from ..models.file_handle import FileHandle, FileState
from ..models.undo_stack import UndoStack
from ..models.jump_history import JumpHistory
from ..core.data_model import DataModel, DisplayMode, ArrangementMode
from ..core.search_engine import SearchEngine, SearchMode, SearchResult
from ..utils.logger import logger
from ..utils.format import FormatUtils
from ..utils.i18n import tr
from ..ai import AIManager
from .agent_bridge import HexEditorAgentBridge
from .panels.data_value import DataValuePanel
from .panels.structure_view import StructureViewPanel
from .panels.ai_agent import AIAgentPanel


DEBUG_LOG_PATH = Path(__file__).resolve().parents[2] / "logs" / "debug.log"
DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _requires_save_as(doc: FileHandle | None) -> bool:
    """Return whether the document must prompt for a destination path."""
    return bool(doc) and not bool(getattr(doc, "file_path", None))


class HexEditorMainWindow(QWidget):
    """
    Main hex editor widget.

    Contains the hex view, file tree, and various panels.
    """

    # Signals
    file_opened = pyqtSignal(str)
    file_saved = pyqtSignal(str)
    cursor_changed = pyqtSignal(int)
    side_panel_state_changed = pyqtSignal(bool, bool, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._document_model = DocumentModel()
        self._data_model = DataModel()
        self._ascii_visible = True
        self._undo_stack = UndoStack()
        self._splitter = None
        self._file_tree_width = 250
        self._right_panel_width = 280
        self._right_panel_standard_width = 280
        self._right_panel_horizontal_width = 520
        self._panel_visibility = {
            "value": True,
            "ai": True,
            "structure": False,
        }
        self._panel_layout_mode = "tabs"
        self._active_panel_id = "value"

        # AI Manager
        self._ai_manager = AIManager(self)
        self._agent_bridge = HexEditorAgentBridge(self)

        # Search Engine
        self._search_engine = SearchEngine(self)
        self._search_results: List[SearchResult] = []
        self._current_result_index = 0
        self._last_search_pattern = ""
        self._last_search_mode = None

        # Jump History
        self._jump_history = JumpHistory(self)

        # Folding Manager
        from .dialogs.folding import FoldingManager
        self._folding_manager = FoldingManager(self)

        # Multi-view Manager
        from .views.multi_view import ViewSyncManager
        self._view_sync_manager = ViewSyncManager(self)

        self._init_ui()
        self._connect_signals()
        self._load_side_panel_settings()
        self._load_ai_settings()

        logger.info("HexEditorMainWindow initialized")

    def _get_settings(self) -> QSettings:
        """Return application settings when available."""
        app = QApplication.instance()
        settings = getattr(app, "settings", None)
        if isinstance(settings, QSettings):
            return settings
        if callable(settings):
            candidate = settings()
            if isinstance(candidate, QSettings):
                return candidate
        return QSettings("openhex", "openhex")

    def _load_ai_settings(self):
        """Load AI settings from app settings."""
        s = self._get_settings()
        settings = {
            'enabled': s.value('ai_enabled', True, type=bool),
            'provider': s.value('ai_provider', 'local'),
            'local': {
                'endpoint': s.value('ai_local_endpoint', 'http://localhost:11434'),
                'model': s.value('ai_local_model', 'qwen:7b'),
            },
            'cloud': {
                'provider': s.value('ai_cloud_provider', 'openai'),
                'api_key': s.value('ai_cloud_api_key', ''),
                'base_url': s.value('ai_cloud_base_url', ''),
                'model': s.value('ai_cloud_model', 'gpt-4o'),
            }
        }
        app = QApplication.instance()
        if app is not None:
            app._ai_settings = settings
        self._ai_manager.configure(settings)
        if hasattr(self, "_ai_panel_widget"):
            self._ai_panel_widget.refresh_provider_status()

    def _load_side_panel_settings(self):
        """Restore side panel visibility and layout settings."""
        s = self._get_settings()
        self._panel_visibility["value"] = s.value("side_panel/value_visible", True, type=bool)
        self._panel_visibility["ai"] = s.value("side_panel/ai_visible", True, type=bool)
        self._panel_visibility["structure"] = s.value("side_panel/structure_visible", False, type=bool)
        layout_mode = s.value("side_panel/layout_mode", "tabs", type=str)
        if layout_mode == "split":
            layout_mode = "vertical"
        self._panel_layout_mode = layout_mode if layout_mode in {"tabs", "vertical", "horizontal"} else "tabs"
        active_panel_id = s.value("side_panel/active_panel", "value", type=str)
        self._active_panel_id = active_panel_id if active_panel_id in self._panel_visibility else "value"
        self._refresh_side_panel_layout()
        self._sync_right_panel_visibility()
        self._apply_right_panel_width_for_layout()
        self._schedule_right_panel_width_restore()
        self._emit_side_panel_state_changed()

    def _save_side_panel_settings(self):
        """Persist side panel visibility and layout settings."""
        s = self._get_settings()
        s.setValue("side_panel/value_visible", self._panel_visibility["value"])
        s.setValue("side_panel/ai_visible", self._panel_visibility["ai"])
        s.setValue("side_panel/structure_visible", self._panel_visibility["structure"])
        s.setValue("side_panel/layout_mode", self._panel_layout_mode)
        s.setValue("side_panel/active_panel", self._active_panel_id)

    def _get_file_settings_key(self, file_path: str) -> str:
        """Generate a unique key for file settings based on absolute path."""
        # Use MD5 hash of absolute path for unique identification
        abs_path = os.path.abspath(file_path)
        path_hash = hashlib.md5(abs_path.encode()).hexdigest()[:16]
        return f"file_layout/{path_hash}"

    def _load_filter_condition_history(self) -> List[str]:
        """Load historical row filter conditions from settings."""
        s = self._get_settings()
        raw = s.value("filters/condition_history", "[]", type=str)
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            return []
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    def _save_filter_condition_history(self, history: List[str]) -> None:
        """Persist row filter history to settings."""
        s = self._get_settings()
        clean_history = [str(value).strip() for value in history if str(value).strip()]
        s.setValue("filters/condition_history", json.dumps(clean_history, ensure_ascii=False))

    def _load_saved_filter_groups(self) -> dict[str, List[str]]:
        """Load saved row filter groups from settings."""
        s = self._get_settings()
        raw = s.value("filters/saved_groups", "{}", type=str)
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if not isinstance(values, dict):
            return {}

        result: dict[str, List[str]] = {}
        for name, filters in values.items():
            key = str(name).strip()
            if not key or not isinstance(filters, list):
                continue
            result[key] = [str(value).strip() for value in filters if str(value).strip()]
        return result

    def _save_saved_filter_groups(self, groups: dict[str, List[str]]) -> None:
        """Persist saved row filter groups to settings."""
        s = self._get_settings()
        payload = {
            str(name).strip(): [str(value).strip() for value in filters if str(value).strip()]
            for name, filters in groups.items()
            if str(name).strip()
        }
        s.setValue("filters/saved_groups", json.dumps(payload, ensure_ascii=False))

    def _get_file_bytes_per_row(self, file_path: str) -> int:
        """Load bytes_per_row setting for a file from QSettings."""
        s = self._get_settings()
        key = self._get_file_settings_key(file_path)
        return s.value(key, 32, type=int)

    def _set_file_bytes_per_row(self, file_path: str, bytes_per_row: int):
        """Save bytes_per_row setting for a file to QSettings."""
        s = self._get_settings()
        key = self._get_file_settings_key(file_path)
        s.setValue(key, bytes_per_row)

    def _init_ui(self):
        """Initialize UI components."""
        # Main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create splitter for resizable panels
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - File browser
        from .panels.file_browser import FileBrowser
        self._file_browser = FileBrowser()
        self._file_browser.file_double_clicked.connect(self._on_file_open_request)
        self._splitter.addWidget(self._file_browser)

        # Center widget - Main editor area
        center_widget = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # Tab widget for multiple files
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.tabCloseRequested.connect(self._on_close_tab)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        # Style
        self._tab_widget.setStyleSheet("""
            QTabWidget::pane {
                background-color: #1e1e1e;
                border: none;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 6px 12px;
                border: none;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3c3c3c;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
        """)

        center_layout.addWidget(self._tab_widget)

        # Status bar
        self._status_bar = self._create_status_bar()
        center_layout.addWidget(self._status_bar)

        center_widget.setLayout(center_layout)
        self._splitter.addWidget(center_widget)

        # Right panel - Info panels
        self._right_panel = self._create_right_panel()
        self._splitter.addWidget(self._right_panel)

        # Set initial sizes
        self._splitter.setSizes([self._file_tree_width, 700, self._right_panel_width])

        main_layout.addWidget(self._splitter)
        self.setLayout(main_layout)

    def _create_status_bar(self):
        """Create status bar."""
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background-color: #252526;
                color: #cccccc;
                border-top: 1px solid #3c3c3c;
            }
        """)
        bar.setFixedHeight(24)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(16)

        # Label style without border/frame
        label_style = "QLabel { border: none; }"

        # Message label (for status messages)
        self._msg_label = QLabel("")
        self._msg_label.setStyleSheet("color: #4ec9b0; border: none;")
        layout.addWidget(self._msg_label)

        # Position label
        self._pos_label = QLabel("Offset: 0x00000000")
        self._pos_label.setStyleSheet(label_style)
        layout.addWidget(self._pos_label)

        # Selection label
        self._selection_label = QLabel("Sel: 0 bytes")
        self._selection_label.setStyleSheet(label_style)
        layout.addWidget(self._selection_label)

        # Arrangement mode label (shows bytes per row)
        self._arrangement_label = QLabel("等长帧: 32")
        self._arrangement_label.setStyleSheet(label_style)
        layout.addWidget(self._arrangement_label)

        # Encoding label
        self._encoding_label = QLabel("UTF-8")
        self._encoding_label.setStyleSheet(label_style)
        layout.addWidget(self._encoding_label)

        # File size label
        self._size_label = QLabel("Size: 0 B")
        self._size_label.setStyleSheet(label_style)
        layout.addWidget(self._size_label)

        # Progress indicator
        self._progress = QProgressBar()
        self._progress.setMaximumWidth(100)
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                height: 14px;
            }
            QProgressBar::chunk {
                background-color: #0e639c;
            }
        """)
        layout.addWidget(self._progress)

        layout.addStretch()

        # Mode label
        self._mode_label = QLabel("Hex")
        self._mode_label.setStyleSheet(label_style)
        layout.addWidget(self._mode_label)

        # Edit mode label (OVR/INS)
        self._edit_mode_label = QLabel("OVR")
        self._edit_mode_label.setStyleSheet("color: #569cd6; font-weight: bold; border: none;")
        layout.addWidget(self._edit_mode_label)

        bar.setLayout(layout)

        # Add showMessage method
        bar.showMessage = lambda msg, timeout=3000: self._show_status_message(msg)

        return bar

    def _show_status_message(self, message: str):
        """Show a temporary message in the status bar."""
        self._msg_label.setText(message)
        QTimer.singleShot(3000, lambda: self._msg_label.setText(""))

    def _create_right_panel(self):
        """Create right side info panel."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._right_panel_content = QWidget()
        self._right_panel_content.setStyleSheet("background-color: #252526;")
        self._right_panel_content_layout = QVBoxLayout()
        self._right_panel_content_layout.setContentsMargins(0, 0, 0, 0)
        self._right_panel_content_layout.setSpacing(0)
        self._right_panel_content.setLayout(self._right_panel_content_layout)

        self._panel_tabs = QTabWidget()
        self._panel_tabs.setDocumentMode(True)
        self._panel_tabs.tabBar().setDrawBase(False)
        self._panel_tabs.tabBar().setExpanding(False)
        self._panel_tabs.currentChanged.connect(self._on_side_panel_tab_changed)
        self._panel_tabs.setStyleSheet("""
            QTabWidget {
                background-color: #252526;
            }
            QTabWidget::pane {
                background-color: #252526;
                border: none;
                margin-top: 0px;
            }
            QTabBar {
                background-color: transparent;
            }
            QTabBar::tab {
                background-color: transparent;
                color: #a6a6a6;
                padding: 8px 14px 7px;
                margin: 0 6px 0 0;
                border: none;
                border-bottom: 2px solid transparent;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                color: #ffffff;
                border-bottom-color: #0e639c;
            }
            QTabBar::tab:hover:!selected {
                background-color: #2d2d30;
                color: #ffffff;
            }
        """)

        self._panel_vertical_splitter = self._create_side_panel_splitter(Qt.Orientation.Vertical)
        self._panel_horizontal_splitter = self._create_side_panel_splitter(Qt.Orientation.Horizontal)

        self._data_value = self._create_data_value_panel()
        self._ai_panel = self._create_ai_panel()
        self._structure_panel = self._create_structure_panel()
        self._side_panels = {
            "value": self._data_value,
            "ai": self._ai_panel,
            "structure": self._structure_panel,
        }

        layout.addWidget(self._right_panel_content)
        self._right_panel_status_bar = self._create_side_panel_status_bar()
        layout.addWidget(self._right_panel_status_bar)
        widget.setLayout(layout)
        widget.setMinimumWidth(240)

        self._refresh_side_panel_layout()
        return widget

    def _create_side_panel_splitter(self, orientation: Qt.Orientation):
        """Create a splitter used for multi-panel layouts."""
        splitter = QSplitter(orientation)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter {
                background-color: #252526;
            }
            QSplitter::handle {
                background-color: #3c3c3c;
            }
        """)
        return splitter

    def _create_side_panel_status_bar(self):
        """Create the side panel status bar shown when multiple panels are active."""
        bar = QFrame()
        bar.setFixedHeight(30)
        bar.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border-top: 1px solid #3c3c3c;
            }
            QPushButton {
                background-color: transparent;
                color: #cccccc;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #37373d;
            }
            QPushButton:checked {
                background-color: #094771;
                color: #ffffff;
            }
            QLabel {
                color: #cccccc;
                border: none;
            }
            QToolButton {
                background-color: transparent;
                border: none;
                padding: 4px;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: #37373d;
            }
            QToolButton:checked {
                background-color: #094771;
            }
            QToolButton:disabled {
                opacity: 0.45;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 6, 0)
        layout.setSpacing(4)

        self._right_panel_status_label = QLabel("")
        layout.addWidget(self._right_panel_status_label)
        layout.addStretch()

        self._layout_button_group = QButtonGroup(self)
        self._layout_button_group.setExclusive(True)
        self._panel_layout_buttons = {}

        for layout_mode, tooltip in (
            ("tabs", tr("panel_layout_tabs")),
            ("vertical", tr("panel_layout_vertical")),
            ("horizontal", tr("panel_layout_horizontal")),
        ):
            button = QToolButton()
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(self._create_panel_layout_icon(layout_mode))
            button.setToolTip(tooltip)
            button.clicked.connect(lambda checked=False, mode=layout_mode: self.set_side_panel_layout_mode(mode))
            self._layout_button_group.addButton(button)
            self._panel_layout_buttons[layout_mode] = button
            layout.addWidget(button)

        bar.setLayout(layout)
        bar.hide()

        self._update_panel_layout_button()
        return bar

    def _get_panel_label(self, panel_id: str) -> str:
        """Return the user-facing label for a side panel."""
        return {
            "value": tr("panel_value_tab"),
            "ai": tr("panel_ai_tab"),
            "structure": tr("panel_structure_tab"),
        }.get(panel_id, panel_id.title())

    def _get_active_panel_ids(self) -> List[str]:
        """Return visible side panels in their display order."""
        return [
            panel_id
            for panel_id in ("value", "ai", "structure")
            if self._panel_visibility.get(panel_id, False)
        ]

    def _clear_layout(self, layout):
        """Detach all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _detach_side_panel_widgets(self):
        """Remove side panels from any temporary container before rebuilding."""
        blocked = self._panel_tabs.blockSignals(True)
        while self._panel_tabs.count():
            widget = self._panel_tabs.widget(0)
            self._panel_tabs.removeTab(0)
            widget.setParent(None)
        self._panel_tabs.blockSignals(blocked)

        for splitter in (self._panel_vertical_splitter, self._panel_horizontal_splitter):
            while splitter.count():
                widget = splitter.widget(0)
                if widget is None:
                    break
                widget.setParent(None)

        for widget in self._side_panels.values():
            if widget.parent() is self._right_panel_content:
                widget.setParent(None)

    def _activate_side_panel_widgets(self, panel_ids: List[str]):
        """Ensure moved panel widgets become visible again after layout changes."""
        for panel_id in panel_ids:
            widget = self._side_panels[panel_id]
            widget.updateGeometry()

        if self._panel_layout_mode == "tabs" and len(panel_ids) > 1:
            active_panel_id = (
                self._active_panel_id if self._active_panel_id in panel_ids else panel_ids[0]
            )
            for panel_id in panel_ids:
                self._side_panels[panel_id].setVisible(panel_id == active_panel_id)
            return

        for panel_id in panel_ids:
            widget = self._side_panels[panel_id]
            widget.setVisible(True)
            widget.show()

    def _sync_tab_panel_visibility(self):
        """Keep only the active tab page visible when using tab layout."""
        if self._panel_layout_mode != "tabs":
            return

        active_panel_ids = self._get_active_panel_ids()
        if len(active_panel_ids) <= 1:
            return

        active_panel_id = (
            self._active_panel_id if self._active_panel_id in active_panel_ids else active_panel_ids[0]
        )
        for panel_id in active_panel_ids:
            self._side_panels[panel_id].setVisible(panel_id == active_panel_id)

    def _ensure_right_panel_width(self, minimum_width: int):
        """Expand the right panel when the active layout needs more space."""
        if self._splitter is None or not self._is_side_panel_visible(self._right_panel, 2):
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= 2 or sizes[2] >= minimum_width:
            return

        delta = minimum_width - sizes[2]
        if delta <= 0:
            return

        grow = min(delta, max(0, sizes[1] - 200))
        if grow <= 0:
            return

        sizes[2] += grow
        sizes[1] -= grow
        self._right_panel_width = sizes[2]
        self._right_panel_horizontal_width = sizes[2]
        self._splitter.setSizes(sizes)

    def _capture_right_panel_width(self):
        """Remember the current right panel width for the active layout family."""
        if self._splitter is None or not self._is_side_panel_visible(self._right_panel, 2):
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= 2 or sizes[2] <= 0:
            return

        current_width = sizes[2]
        self._right_panel_width = current_width
        if self._panel_layout_mode == "horizontal":
            self._right_panel_horizontal_width = current_width
        else:
            self._right_panel_standard_width = current_width

    def _set_right_panel_width(self, target_width: int):
        """Resize the right splitter pane to a target width when possible."""
        if self._splitter is None or not self._is_side_panel_visible(self._right_panel, 2):
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= 2:
            return

        available = sizes[1] + sizes[2]
        max_target = max(160, available - 200)
        clamped_target = max(160, min(target_width, max_target))
        if clamped_target == sizes[2]:
            self._right_panel_width = clamped_target
            return

        sizes[2] = clamped_target
        sizes[1] = available - clamped_target
        self._right_panel_width = clamped_target
        self._splitter.setSizes(sizes)

    def _apply_right_panel_width_for_layout(self):
        """Restore the expected right panel width for the current side panel layout."""
        active_panel_ids = self._get_active_panel_ids()
        if not active_panel_ids:
            return

        if len(active_panel_ids) > 1 and self._panel_layout_mode == "horizontal":
            target_width = max(self._right_panel_horizontal_width, 520)
        else:
            target_width = self._right_panel_standard_width

        self._set_right_panel_width(target_width)

    def _schedule_right_panel_width_restore(self):
        """Apply right panel width after Qt finishes processing pending layout changes."""
        QTimer.singleShot(0, self._apply_right_panel_width_for_layout)

    def _refresh_side_panel_layout(self):
        """Rebuild the right-side panel area based on visibility and layout state."""
        active_panel_ids = self._get_active_panel_ids()
        if self._active_panel_id not in active_panel_ids:
            self._active_panel_id = active_panel_ids[0] if active_panel_ids else "value"

        self._clear_layout(self._right_panel_content_layout)
        self._detach_side_panel_widgets()

        if not active_panel_ids:
            self._update_side_panel_status_bar(active_panel_ids)
            return

        if len(active_panel_ids) == 1:
            self._right_panel_content_layout.addWidget(self._side_panels[active_panel_ids[0]])
            self._activate_side_panel_widgets(active_panel_ids)
            self._active_panel_id = active_panel_ids[0]
            self._update_side_panel_status_bar(active_panel_ids)
            return

        if self._panel_layout_mode == "vertical":
            splitter = self._panel_vertical_splitter
            self._right_panel_content_layout.addWidget(splitter)
            for panel_id in active_panel_ids:
                splitter.addWidget(self._side_panels[panel_id])
            self._activate_side_panel_widgets(active_panel_ids)
            splitter.setVisible(True)
            splitter.show()
            QTimer.singleShot(0, lambda: splitter.setSizes([1] * len(active_panel_ids)))
        elif self._panel_layout_mode == "horizontal":
            splitter = self._panel_horizontal_splitter
            self._right_panel_content_layout.addWidget(splitter)
            for panel_id in active_panel_ids:
                splitter.addWidget(self._side_panels[panel_id])
            self._activate_side_panel_widgets(active_panel_ids)
            splitter.setVisible(True)
            splitter.show()
            self._ensure_right_panel_width(520)
            QTimer.singleShot(0, lambda: splitter.setSizes([1] * len(active_panel_ids)))
        else:
            blocked = self._panel_tabs.blockSignals(True)
            self._right_panel_content_layout.addWidget(self._panel_tabs)
            for panel_id in active_panel_ids:
                self._panel_tabs.addTab(self._side_panels[panel_id], self._get_panel_label(panel_id))
            target_index = active_panel_ids.index(self._active_panel_id) if self._active_panel_id in active_panel_ids else 0
            self._panel_tabs.setCurrentIndex(target_index)
            self._panel_tabs.blockSignals(blocked)
            self._activate_side_panel_widgets(active_panel_ids)
            self._panel_tabs.setVisible(True)
            self._panel_tabs.show()

        self._right_panel_content.setVisible(True)
        self._right_panel_content.show()
        right_panel = getattr(self, "_right_panel", None)
        if right_panel is not None:
            right_panel.updateGeometry()
        self._update_side_panel_status_bar(active_panel_ids)

    def _update_side_panel_status_bar(self, active_panel_ids: List[str]):
        """Update side panel buttons and layout action visibility."""
        show_bar = len(active_panel_ids) > 1
        self._right_panel_status_bar.setVisible(show_bar)
        self._update_panel_layout_button()

        if not show_bar:
            return

        labels = [self._get_panel_label(panel_id) for panel_id in active_panel_ids]
        self._right_panel_status_label.setText(" / ".join(labels))

    def _update_panel_layout_button(self):
        """Refresh the side panel layout switcher icon and action state."""
        has_multiple = len(self._get_active_panel_ids()) > 1
        for layout_mode, button in self._panel_layout_buttons.items():
            blocked = button.blockSignals(True)
            button.setChecked(self._panel_layout_mode == layout_mode)
            button.setEnabled(has_multiple)
            button.blockSignals(blocked)

    def _create_panel_layout_icon(self, mode: str) -> QIcon:
        """Create a VS Code inspired icon for tabs/split mode."""
        size = QSize(16, 16)
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#cccccc"))
        pen.setWidth(1)
        painter.setPen(pen)

        if mode == "vertical":
            painter.drawRoundedRect(2, 2, 12, 12, 1.5, 1.5)
            painter.drawLine(3, 8, 13, 8)
        elif mode == "horizontal":
            painter.drawRoundedRect(2, 2, 12, 12, 1.5, 1.5)
            painter.drawLine(8, 3, 8, 13)
        else:
            painter.drawRoundedRect(2, 4, 12, 10, 1.5, 1.5)
            painter.drawLine(2, 6, 14, 6)
            painter.fillRect(3, 2, 4, 2, QColor("#cccccc"))
            painter.fillRect(8, 2, 3, 2, QColor("#777777"))

        painter.end()
        return QIcon(pixmap)

    def _sync_right_panel_visibility(self):
        """Show or hide the right panel based on active side panels."""
        self._set_side_panel_visibility(
            self._right_panel,
            2,
            bool(self._get_active_panel_ids()),
            "_right_panel_width",
            280,
        )

    def is_right_panel_visible(self) -> bool:
        """Return whether the right-side splitter panel is currently visible."""
        if self._splitter is None:
            return not self._right_panel.isHidden()

        sizes = self._splitter.sizes()
        if len(sizes) <= 2:
            return not self._right_panel.isHidden()

        return not self._right_panel.isHidden() and sizes[2] > 0

    def _emit_side_panel_state_changed(self):
        """Notify outer UI that side panel state changed."""
        self.side_panel_state_changed.emit(
            self._panel_visibility["ai"],
            self._panel_visibility["value"],
            self._panel_visibility["structure"],
            self._panel_layout_mode,
        )

    def is_ai_panel_visible(self) -> bool:
        """Return whether the AI panel is enabled in the side panel."""
        return self._panel_visibility["ai"]

    def is_value_panel_visible(self) -> bool:
        """Return whether the Value panel is enabled in the side panel."""
        return self._panel_visibility["value"]

    def is_structure_panel_visible(self) -> bool:
        """Return whether the structure panel is enabled in the side panel."""
        return self._panel_visibility["structure"]

    def side_panel_layout_mode(self) -> str:
        """Return the current side panel layout mode."""
        return self._panel_layout_mode

    def set_side_panel_layout_mode(self, mode: str):
        """Switch between tabbed and split layouts."""
        if mode not in {"tabs", "vertical", "horizontal"} or self._panel_layout_mode == mode:
            return

        self._capture_right_panel_width()
        self._panel_layout_mode = mode
        self._refresh_side_panel_layout()
        self._apply_right_panel_width_for_layout()
        self._schedule_right_panel_width_restore()
        self._save_side_panel_settings()
        self._emit_side_panel_state_changed()

    def _on_side_panel_tab_changed(self, index: int):
        """Track the active tab for the right-side panel area."""
        if index < 0:
            return

        widget = self._panel_tabs.widget(index)
        for panel_id, panel_widget in self._side_panels.items():
            if widget is panel_widget:
                self._active_panel_id = panel_id
                self._sync_tab_panel_visibility()
                self._save_side_panel_settings()
                break

    def _set_side_panel_visibility(self, panel: QWidget, index: int, visible: bool,
                                   size_attr: str, default_size: int):
        """Show or hide a splitter side panel while preserving its width."""
        if self._splitter is None:
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= index:
            return

        current_visible = panel.isVisible() and sizes[index] > 0
        if current_visible == visible:
            if visible and panel.isHidden():
                panel.show()
            return

        center_index = 1
        if visible:
            panel.show()
            restore_size = max(getattr(self, size_attr, default_size), 160)
            sizes[index] = restore_size
            sizes[center_index] = max(200, sizes[center_index] - restore_size)
        else:
            if sizes[index] > 0:
                setattr(self, size_attr, sizes[index])
            sizes[center_index] += sizes[index]
            sizes[index] = 0
            panel.hide()

        self._splitter.setSizes(sizes)

    def _is_side_panel_visible(self, panel: QWidget, index: int) -> bool:
        """Return whether a splitter side panel is effectively visible."""
        if self._splitter is None:
            return panel.isVisible()

        sizes = self._splitter.sizes()
        if len(sizes) <= index:
            return panel.isVisible()

        return panel.isVisible() and sizes[index] > 0

    def _create_data_value_panel(self):
        """Create data value inspection panel."""
        return DataValuePanel(self)

    def _create_structure_panel(self):
        """Create structure parsing panel."""
        return StructureViewPanel(self)

    def _create_ai_panel(self):
        """Create AI analysis panel."""
        self._ai_panel_widget = AIAgentPanel(self, self._ai_manager, self._agent_bridge)
        self._ai_panel_widget.open_settings_requested.connect(self.show_ai_settings)
        return self._ai_panel_widget

    def _connect_signals(self):
        """Connect signals."""
        self._document_model.document_changed.connect(self._on_document_changed)
        self._document_model.document_modified.connect(self._on_document_modified)

    def _update_edit_mode_display(self, mode: str):
        """Update status bar with current edit mode."""
        self._edit_mode_label.setText("INS" if mode == 'insert' else "OVR")

    def _connect_hex_view_signals(self, hex_view):
        """Connect signals from hex view."""
        if hasattr(hex_view, 'edit_mode_changed'):
            hex_view.edit_mode_changed.connect(self._update_edit_mode_display)
        if hasattr(hex_view, 'cursor_moved'):
            hex_view.cursor_moved.connect(self._on_cursor_moved)
        if hasattr(hex_view, 'selection_changed'):
            hex_view.selection_changed.connect(self._on_selection_changed)

    def _get_current_hex_view(self):
        """Return the active hex view if available."""
        current_widget = self._tab_widget.currentWidget()
        if current_widget and hasattr(current_widget, 'hex_view'):
            return current_widget.hex_view
        return None

    def _reset_value_panel(self):
        """Clear the Value panel when no byte is available."""
        if hasattr(self, "_data_value"):
            self._data_value.clear_values()

    def _reset_structure_panel(self):
        """Clear the structure panel when no row data is available."""
        if hasattr(self, "_structure_panel"):
            self._structure_panel.clear_values()

    def _update_value_panel(self, offset: int):
        """Update the Value panel for the active document and byte offset."""
        doc = self._document_model.current_document
        if not doc or offset < 0 or offset >= doc.file_size:
            self._reset_value_panel()
            return

        data = doc.read(offset, DataValuePanel.MAX_BYTES)
        if not data:
            self._reset_value_panel()
            return

        self._data_value.update_values(offset, data)

    def _update_structure_panel(self, offset: int):
        """Update the structure panel for the current cursor row."""
        doc = self._document_model.current_document
        hex_view = self._get_current_hex_view()
        if not doc or not hex_view or offset < 0 or offset >= doc.file_size:
            self._reset_structure_panel()
            return

        row_start, row_end = hex_view.get_data_bounds_for_offset(offset)
        if row_end <= row_start:
            self._reset_structure_panel()
            return

        data = doc.read(row_start, row_end - row_start)
        if not data:
            self._reset_structure_panel()
            return

        self._structure_panel.update_row_data(row_start, data)

    def _refresh_current_view_state(self):
        """Refresh status labels and value panel from the active editor."""
        hex_view = self._get_current_hex_view()
        doc = self._document_model.current_document
        if not hex_view or not doc:
            self._pos_label.setText(tr("status_offset", "0x00000000"))
            self._selection_label.setText(tr("status_selection", 0))
            self._reset_value_panel()
            self._reset_structure_panel()
            return

        offset = hex_view.get_offset_at_cursor()
        self._on_cursor_moved(offset)

    def _on_cursor_moved(self, offset: int):
        """Update side UI from the active cursor position."""
        self._pos_label.setText(tr("status_offset", f"0x{max(0, offset):08X}"))
        self._update_value_panel(offset)
        self._update_structure_panel(offset)
        self.cursor_changed.emit(offset)

    def _on_selection_changed(self, start: int, end: int):
        """Update the status bar selection size."""
        length = end - start + 1 if start >= 0 and end >= start else 0
        self._selection_label.setText(tr("status_selection", length))

    # File operations
    def new_file(self):
        """Create new file."""
        doc = self._document_model.new_document()
        self._add_editor_tab(doc)
        
        # Ensure window is active and focus is on hex view
        self.activateWindow()
        self.raise_()
        
        # Set focus to hex view for immediate editing
        current_widget = self._tab_widget.currentWidget()
        if current_widget and hasattr(current_widget, 'hex_view'):
            hex_view = current_widget.hex_view
            hex_view.setFocus()
            hex_view.activateWindow()
            # Ensure the widget is focusable
            from PyQt6.QtCore import Qt
            hex_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def open_file(self, path=None):
        """Open file."""
        if path is None:
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open File",
                "",
                "All Files (*);;Text Files (*.txt);;Binary Files (*.bin)"
            )
            if not path:
                return

        self._open_file(path)

    def _open_file(self, path: str):
        """Open file from path."""
        doc = self._document_model.open_document(path)
        if doc:
            self._add_editor_tab(doc)

            # Load bytes_per_row from settings and apply to hex view
            bytes_per_row = self._get_file_bytes_per_row(path)
            current_widget = self._tab_widget.currentWidget()
            if hasattr(current_widget, 'hex_view'):
                current_widget.hex_view.set_bytes_per_row(bytes_per_row)

            # Update arrangement label in status bar
            self._arrangement_label.setText(f"等长帧: {bytes_per_row}")

            # Also update data model
            self._data_model.bytes_per_frame = bytes_per_row

            self.file_opened.emit(path)

    def _on_file_open_request(self, path: str):
        """Handle file open request from file browser."""
        if os.path.isfile(path):
            self._open_file(path)

    def open_folder(self, path=None):
        """Open folder in file tree."""
        from PyQt6.QtWidgets import QFileDialog
        if path is None:
            path = QFileDialog.getExistingDirectory(
                self,
                "Open Folder",
                ""
            )
        if path:
            self._file_browser.set_root_path(path)

    def save_file(self):
        """Save current file."""
        doc = self._document_model.current_document
        if not doc:
            self._status_bar.showMessage("No file to save")
            return

        if _requires_save_as(doc):
            # Unsaved documents must choose a destination first.
            self.save_file_as()
            return

        if self._document_model.save_current_document():
            self._show_save_success_message()
            if doc and doc.file_path:
                self.file_saved.emit(doc.file_path)
        else:
            self._status_bar.showMessage("Save failed", 3000)

    def save_file_as(self):
        """Save file as."""
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As",
            "",
            "All Files (*)"
        )
        if path:
            if self._document_model.save_current_document(path):
                doc = self._document_model.current_document
                if doc:
                    self._update_tab_name(self._tab_widget.currentIndex(), doc)
                    if doc.file_path:
                        self.file_saved.emit(doc.file_path)
                self._show_save_success_message()

    def _show_save_success_message(self):
        """Show a short save success message that does not stretch the status bar."""
        self._status_bar.showMessage(tr("status_saved"), 3000)

    def close_current_file(self):
        """Close current file."""
        return self._document_model.close_current_document()

    def close_all_files(self):
        """Close all files."""
        return self._document_model.close_all_documents()

    # Edit operations
    def undo(self):
        """Undo last action."""
        command = self._undo_stack.undo()
        if command:
            self._apply_undo(command)

    def redo(self):
        """Redo last undone action."""
        command = self._undo_stack.redo()
        if command:
            self._apply_redo(command)

    def _apply_undo(self, command):
        """Apply undo command to file."""
        from ..models.undo_stack import ReplaceCommand, InsertCommand, DeleteCommand, FillCommand

        doc = self._document_model.current_document
        if not doc:
            return

        # Get the undo action from command
        action = command.undo()
        if not action:
            return

        op = action[0]
        offset = action[1]
        data = action[2]

        if op == "replace":
            # Replace with old data
            doc.write(offset, data)
        elif op == "insert":
            # Delete the inserted data
            doc.delete(offset, len(data))
        elif op == "delete":
            # Re-insert the deleted data
            doc.insert(offset, data)
        elif op == "fill":
            # Fill is handled as replace
            doc.write(offset, data)

    def _apply_redo(self, command):
        """Apply redo command to file."""
        from ..models.undo_stack import ReplaceCommand, InsertCommand, DeleteCommand, FillCommand

        doc = self._document_model.current_document
        if not doc:
            return

        # Get the redo action from command
        action = command.redo()
        if not action:
            return

        op = action[0]
        offset = action[1]
        data = action[2]

        if op == "replace":
            # Replace with new data
            doc.write(offset, data)
        elif op == "insert":
            # Insert data
            doc.insert(offset, data)
        elif op == "delete":
            # Delete data
            doc.delete(offset, data)
        elif op == "fill":
            # Fill is handled as replace
            length = action[3] if len(action) > 3 else len(data)
            fill_data = data * ((length // len(data)) + 1)
            doc.write(offset, fill_data[:length])

    # View operations
    def set_arrangement_mode(self, mode: str):
        """Set arrangement mode."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QSpinBox, QDialogButtonBox, QLabel

        mode_map = {
            "equal_frame": ArrangementMode.EQUAL_FRAME,
            "header_length": ArrangementMode.HEADER_LENGTH,
        }

        # 保存用户输入的参数值
        param_value = None

        if mode == "header_length":
            # 弹出对话框让用户输入头长度
            dialog = QDialog(self)
            dialog.setWindowTitle("头长度参数设置")
            layout = QVBoxLayout()

            info_label = QLabel("请输入头部长度（1-8字节）：")
            layout.addWidget(info_label)

            header_spin = QSpinBox()
            header_spin.setRange(1, 8)
            header_spin.setValue(self._data_model.header_length if self._data_model.header_length > 0 else 4)
            layout.addWidget(header_spin)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            dialog.setLayout(layout)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return  # 用户取消

            # 保存用户输入的值
            param_value = header_spin.value()
            # 设置头长度
            self._data_model.header_length = param_value

        if mode in mode_map:
            self._data_model.arrangement_mode = mode_map[mode]

            # Update toolbar visibility (pass param_value if available)
            self._update_toolbar_for_mode(mode, param_value)

            # Update menu check state
            main_window = self.window()
            if hasattr(main_window, '_arrange_equal_action') and hasattr(main_window, '_arrange_header_action'):
                if mode == "equal_frame":
                    main_window._arrange_equal_action.setChecked(True)
                elif mode == "header_length":
                    main_window._arrange_header_action.setChecked(True)

            # Update all hex views
            for i in range(self._tab_widget.count()):
                widget = self._tab_widget.widget(i)
                if isinstance(widget, HexEditorTabWidget):
                    hex_view = widget.hex_view
                    if hasattr(hex_view, 'set_arrangement_mode'):
                        if mode == "equal_frame":
                            hex_view.set_arrangement_mode("equal_frame", self._data_model.bytes_per_frame)
                        elif mode == "header_length":
                            # 使用用户输入的值，而不是 data_model 的值
                            hex_view.set_arrangement_mode("header_length", param_value if param_value is not None else self._data_model.header_length)

    def _update_toolbar_for_mode(self, mode: str, param_value: int = None):
        """Update toolbar based on arrangement mode."""
        # Try to access main window's toolbar controls
        main_window = self.window()
        if hasattr(main_window, '_length_spinbox'):
            if mode == "equal_frame":
                # 等长帧模式：长度输入框范围1-65535
                main_window._length_spinbox.setRange(1, 65535)
                main_window._length_spinbox.setValue(self._data_model.bytes_per_frame)
                main_window._toolbar_length_label.setText("长度:")
                # Update status bar
                self._arrangement_label.setText(f"等长帧: {self._data_model.bytes_per_frame}")
            elif mode == "header_length":
                # 头长度模式：长度输入框范围1-8
                # 使用用户输入的值（如果提供）
                header_len = param_value if param_value is not None else self._data_model.header_length
                main_window._length_spinbox.setRange(1, 8)
                main_window._length_spinbox.setValue(header_len)
                main_window._toolbar_length_label.setText("头长度:")
                # Update status bar
                self._arrangement_label.setText(f"头长度: {header_len}")

    def set_arrangement_length(self, length: int):
        """Set bytes per frame for equal frame mode."""
        self._data_model.bytes_per_frame = length
        # Update hex view
        current_widget = self._tab_widget.currentWidget()
        if hasattr(current_widget, 'hex_view'):
            current_widget.hex_view.set_bytes_per_row(length)
        # Update status bar
        self._arrangement_label.setText(f"等长帧: {length}")

    def set_header_length(self, length: int):
        """Set header length for header length mode."""
        self._data_model.header_length = length
        # Update hex view
        self._update_hex_views()
        # Update status bar
        self._arrangement_label.setText(f"头长度: {length}")

    def set_display_mode(self, mode: str):
        """Set display mode."""
        mode_map = {
            "hex": DisplayMode.HEX,
            "binary": DisplayMode.BINARY,
            "ascii": DisplayMode.ASCII,
            "octal": DisplayMode.OCTAL,
        }
        if mode in mode_map:
            self._data_model.display_mode = mode_map[mode]
            if mode == "ascii":
                self._ascii_visible = True
            self._mode_label.setText(mode.upper())
            self._update_hex_views()

    def set_ascii_visible(self, visible: bool):
        """Show or hide the ASCII column."""
        visible = bool(visible)
        if self._ascii_visible != visible:
            self._ascii_visible = visible
            self._update_hex_views()

    def show_arrangement_dialog(self):
        """Show arrangement settings dialog."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QSpinBox, QDialogButtonBox, QLabel
        dialog = QDialog(self)
        dialog.setWindowTitle("Arrangement Settings")
        layout = QVBoxLayout()

        # Bytes per frame
        bytes_label = QLabel("Bytes per frame:")
        layout.addWidget(bytes_label)
        spin = QSpinBox()
        spin.setRange(1, 64)
        spin.setValue(self._data_model.bytes_per_frame)
        layout.addWidget(spin)

        # Header length
        header_label = QLabel("Header length:")
        layout.addWidget(header_label)
        header_spin = QSpinBox()
        header_spin.setRange(0, 256)
        header_spin.setValue(self._data_model.header_length)
        layout.addWidget(header_spin)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._data_model.bytes_per_frame = spin.value()
            self._data_model.header_length = header_spin.value()
            self._update_hex_views()

            # Save bytes_per_row to settings for current file
            doc = self._document_model.current_document
            if doc and doc.file_path:
                self._set_file_bytes_per_row(doc.file_path, spin.value())

    def show_batch_edit_dialog(self, operation="fill"):
        """Show batch edit dialog."""
        from .dialogs.batch_edit import BatchEditDialog

        doc = self._document_model.current_document
        if not doc:
            return

        # Get selection (using cursor position as offset, 16 bytes as default)
        offset = 0
        length = min(16, doc.file_size)

        dialog = BatchEditDialog(self, offset, length)
        if dialog.exec():
            self._apply_batch_edit(dialog.get_operation())

    def batch_edit(self, operation: str):
        """Apply batch edit operation."""
        doc = self._document_model.current_document
        if not doc:
            return

        # Default to first 16 bytes
        offset = 0
        length = min(16, doc.file_size)

        if operation == "fill":
            self._apply_batch_edit(("fill", b'\x00'))
        elif operation == "increment":
            self._apply_batch_edit(("increment", False, 0))
        elif operation == "decrement":
            self._apply_batch_edit(("decrement", False, 0))
        elif operation == "invert":
            self._apply_batch_edit(("invert",))
        elif operation == "reverse":
            self._apply_batch_edit(("reverse",))

    def _apply_batch_edit(self, operation):
        """Apply batch edit operation to file."""
        from ..models.undo_stack import FillCommand

        doc = self._document_model.current_document
        if not doc:
            return

        op_type = operation[0]

        # Default selection: first 16 bytes
        offset = 0
        length = min(16, doc.file_size)

        if length == 0:
            return

        # Read current data
        old_data = doc.read(offset, length)

        if op_type == "fill":
            fill_pattern = operation[1]
            # Expand fill pattern to length
            new_data = (fill_pattern * ((length // len(fill_pattern)) + 1))[:length]
        elif op_type == "increment":
            signed = operation[1] if len(operation) > 1 else False
            overflow_mode = operation[2] if len(operation) > 2 else 0

            new_data = bytearray(length)
            for i in range(length):
                val = old_data[i]
                if signed and val == 127:
                    val = -128
                else:
                    val = (val + 1) % 256
                new_data[i] = val
            new_data = bytes(new_data)
        elif op_type == "decrement":
            signed = operation[1] if len(operation) > 1 else False
            overflow_mode = operation[2] if len(operation) > 2 else 0

            new_data = bytearray(length)
            for i in range(length):
                val = old_data[i]
                if signed and val == 128:
                    val = 127
                else:
                    val = (val - 1) % 256
                new_data[i] = val
            new_data = bytes(new_data)
        elif op_type == "invert":
            new_data = bytes(~b & 0xFF for b in old_data)
        elif op_type == "reverse":
            new_data = old_data[::-1]
        else:
            return

        # Apply the change
        if old_data != new_data:
            doc.write(offset, new_data)

            # Add to undo stack
            cmd = FillCommand(offset, old_data, new_data[:1])
            self._undo_stack.push(cmd)

    def show_find_dialog(self):
        """Show find dialog."""
        from .dialogs.find_replace import FindReplaceDialog

        doc = self._document_model.current_document
        if not doc:
            return

        # Create and show dialog
        dialog = FindReplaceDialog(self)

        # Connect signals
        dialog.find_next.connect(self._on_find_next)
        dialog.replace_next.connect(self._on_replace_next)
        dialog.replace_all.connect(self._on_replace_all)

        # Connect search engine signals
        self._search_engine.search_progress.connect(dialog.update_progress)
        self._search_engine.search_finished.connect(self._on_search_finished)

        dialog.exec()

    def show_filter_dialog(self):
        """Show the row filter dialog for the active hex view."""
        from .dialogs.filter_dialog import FilterDialog

        hex_view = self._get_current_hex_view()
        if not hex_view:
            self._status_bar.showMessage(tr("filter_no_active_view"), 2000)
            return

        dialog = FilterDialog(
            active_filters=hex_view.get_row_filters(),
            condition_history=self._load_filter_condition_history(),
            saved_groups=self._load_saved_filter_groups(),
            parent=self,
        )

        accepted = dialog.exec() == dialog.DialogCode.Accepted
        self._save_filter_condition_history(dialog.get_condition_history())
        self._save_saved_filter_groups(dialog.get_saved_groups())

        if not accepted:
            return

        filters = dialog.get_active_filters()
        hex_view.set_row_filters(filters)

        visible_rows = hex_view.get_visible_row_count()
        total_rows = hex_view.get_total_row_count()
        if filters:
            self._status_bar.showMessage(tr("filter_status_applied", visible_rows, total_rows), 3000)
        else:
            self._status_bar.showMessage(tr("filter_status_cleared"), 3000)

    def show_nl_search_dialog(self):
        """Show natural language search dialog."""
        from .dialogs.nl_search import NaturalLanguageSearchDialog

        doc = self._document_model.current_document
        if not doc:
            return

        # Read data for search
        data = doc.read(0, min(doc.file_size, 10 * 1024 * 1024))  # Max 10MB

        dialog = NaturalLanguageSearchDialog(self, self._ai_manager, data)
        dialog.exec()

    def _on_find_next(self, pattern: str, mode: object):
        """Handle find next."""
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(f"[MAIN] _on_find_next: pattern='{pattern}', mode='{mode}', type={type(mode)}\n")
            f.write(f"[MAIN] last: pattern='{self._last_search_pattern}', mode={self._last_search_mode}\n")

        doc = self._document_model.current_document
        if not doc:
            with open(DEBUG_LOG_PATH, "a") as f:
                f.write("[MAIN] No document\n")
            return

        if not pattern:
            self._status_bar.showMessage("Enter search pattern", 2000)
            return

        # Convert mode - check all possible values
        search_mode = SearchMode.HEX
        if mode == "text" or mode == SearchMode.TEXT:
            search_mode = SearchMode.TEXT
        elif mode == "regex" or mode == SearchMode.REGEX:
            search_mode = SearchMode.REGEX
        elif mode == "hex" or mode == SearchMode.HEX:
            search_mode = SearchMode.HEX

        # Check if we should re-search or go to next result
        need_search = (pattern != self._last_search_pattern or search_mode != self._last_search_mode)

        if need_search:
            # New search
            with open(log_path, "a") as f:
                f.write(f"[MAIN] Performing new search\n")

            # Get data
            data = doc.read(0, doc.file_size)
            self._search_engine.set_data(data)

            with open(log_path, "a") as f:
                f.write(f"[MAIN] search_mode={search_mode}\n")

            # Search all results
            self._search_results = self._search_engine.search_all(pattern, search_mode)

            with open(log_path, "a") as f:
                f.write(f"[MAIN] search_results count: {len(self._search_results)}\n")
                for i, r in enumerate(self._search_results[:5]):
                    f.write(f"[MAIN] result[{i}]: offset={r.offset}, length={r.length}\n")

            # Save search params
            self._last_search_pattern = pattern
            self._last_search_mode = search_mode
            self._current_result_index = 0

            if self._search_results:
                self._status_bar.showMessage(f"Found {len(self._search_results)} matches", 3000)
                self._go_to_result(0)
            else:
                self._status_bar.showMessage("No matches found", 3000)
        else:
            # Go to next result
            with open(log_path, "a") as f:
                f.write(f"[MAIN] Going to next result, current index={self._current_result_index}\n")

            if self._search_results:
                next_index = (self._current_result_index + 1) % len(self._search_results)
                self._go_to_result(next_index)
                self._current_result_index = next_index
                self._status_bar.showMessage(f"Result {next_index + 1}/{len(self._search_results)}", 2000)

    def _on_replace_next(self, pattern: str, replacement: str, mode: object):
        """Handle replace next."""
        # TODO: Implement replace next
        pass

    def _on_replace_all(self, pattern: str, replacement: str, mode: object):
        """Handle replace all."""
        # TODO: Implement replace all
        pass

    def _on_search_finished(self, results):
        """Handle search finished."""
        self._search_results = results or []
        self._current_result_index = 0

        if self._search_results:
            # Go to first result
            self._go_to_result(0)

    def _go_to_result(self, index: int):
        """Go to search result at index."""
        if 0 <= index < len(self._search_results):
            result = self._search_results[index]
            self._current_result_index = index
            with open(DEBUG_LOG_PATH, "a") as f:
                f.write(f"[INFO] _go_to_result: offset={result.offset}, index={index}/{len(self._search_results)}\n")

            # Scroll to offset
            current_widget = self._tab_widget.currentWidget()
            with open(DEBUG_LOG_PATH, "a") as f:
                f.write(f"[INFO] current_widget: {current_widget}, type: {type(current_widget)}\n")

            if hasattr(current_widget, 'hex_view'):
                with open(log_path, "a") as f:
                    f.write(f"[INFO] Calling scrollToOffset({result.offset})\n")
                # Update search highlight
                current_widget.hex_view.set_search_results(self._search_results, index)
                current_widget.hex_view.scrollToOffset(result.offset)
            else:
                with open(log_path, "a") as f:
                    f.write(f"[WARNING] No hex_view attribute!\n")

    def _hex_to_bytes(self, hex_str: str) -> bytes:
        """Convert hex string to bytes."""
        hex_str = hex_str.replace(" ", "").replace("-", "")
        if len(hex_str) % 2 != 0:
            hex_str = "0" + hex_str
        try:
            return bytes.fromhex(hex_str)
        except ValueError:
            return b""

    def show_replace_dialog(self):
        """Show replace dialog."""
        from .dialogs.find_replace import FindReplaceDialog

        doc = self._document_model.current_document
        if not doc:
            return

        # Create and show dialog
        dialog = FindReplaceDialog(self)
        dialog.find_next.connect(self._on_find_next)
        dialog.replace_next.connect(self._on_replace_next)
        dialog.replace_all.connect(self._on_replace_all)

        # Connect search engine signals
        self._search_engine.search_progress.connect(dialog.update_progress)
        self._search_engine.search_finished.connect(self._on_search_finished)

        # Open Replace tab by default
        dialog.exec()

    def show_goto_dialog(self):
        """Show goto offset dialog."""
        from .dialogs.goto import GotoDialog

        doc = self._document_model.current_document
        if not doc:
            return

        dialog = GotoDialog(self, doc.file_size - 1)
        if dialog.exec():
            offset = dialog.get_offset()
            # Add to jump history
            self._jump_history.push(offset, f"Go to 0x{offset:X}")
            # Scroll to offset in current hex view
            current_widget = self._tab_widget.currentWidget()
            if hasattr(current_widget, 'hex_view'):
                current_widget.hex_view.scrollToOffset(offset)

    # Panel toggles
    def toggle_file_tree(self):
        """Toggle file tree visibility."""
        self._set_side_panel_visibility(
            self._file_browser,
            0,
            not self._is_side_panel_visible(self._file_browser, 0),
            "_file_tree_width",
            250,
        )

    def toggle_ai_panel(self):
        """Toggle the AI side panel from the View menu."""
        self.set_ai_panel_visible(not self.is_ai_panel_visible())

    def focus_ai_panel(self):
        """Ensure the AI side panel is visible and focused."""
        if not self.is_ai_panel_visible():
            self.set_ai_panel_visible(True)

        if self._active_panel_id != "ai":
            self._active_panel_id = "ai"
            self._refresh_side_panel_layout()
            self._save_side_panel_settings()

        if self._panel_layout_mode == "tabs":
            index = self._panel_tabs.indexOf(self._ai_panel)
            if index >= 0:
                self._panel_tabs.setCurrentIndex(index)
                self._sync_tab_panel_visibility()

        if hasattr(self, "_ai_panel_widget"):
            self._ai_panel_widget.focus_input()

    def submit_ai_prompt(self, prompt: str) -> bool:
        """Focus the AI panel and submit a prompt into the chat runtime."""
        self.focus_ai_panel()
        if not hasattr(self, "_ai_panel_widget"):
            return False
        return self._ai_panel_widget.send_preset_prompt(prompt)

    def toggle_value_panel(self):
        """Toggle Value panel visibility inside the side panel container."""
        self.set_value_panel_visible(not self.is_value_panel_visible())

    def toggle_structure_panel(self):
        """Toggle structure panel visibility inside the side panel container."""
        self.set_structure_panel_visible(not self.is_structure_panel_visible())

    def set_ai_panel_visible(self, visible: bool):
        """Enable or disable the AI panel."""
        self._set_panel_visible("ai", visible)

    def set_value_panel_visible(self, visible: bool):
        """Enable or disable the Value panel."""
        self._set_panel_visible("value", visible)

    def set_structure_panel_visible(self, visible: bool):
        """Enable or disable the structure panel."""
        self._set_panel_visible("structure", visible)

    def _set_panel_visible(self, panel_id: str, visible: bool):
        """Update a specific side panel visibility flag."""
        visible = bool(visible)
        if self._panel_visibility.get(panel_id) == visible:
            return

        self._capture_right_panel_width()
        self._panel_visibility[panel_id] = visible
        active_panel_ids = self._get_active_panel_ids()
        if panel_id in active_panel_ids:
            self._active_panel_id = panel_id
        elif self._active_panel_id not in active_panel_ids:
            self._active_panel_id = active_panel_ids[0] if active_panel_ids else "value"

        self._refresh_side_panel_layout()
        self._sync_right_panel_visibility()
        self._apply_right_panel_width_for_layout()
        self._schedule_right_panel_width_restore()
        self._save_side_panel_settings()
        self._emit_side_panel_state_changed()

    # Navigation
    def go_to_next_bookmark(self):
        """Go to next bookmark."""
        doc = self._document_model.current_document
        if not doc:
            return

        # Get current offset
        current_widget = self._tab_widget.currentWidget()
        if hasattr(current_widget, 'hex_view'):
            current_offset = current_widget.hex_view.get_offset_at_cursor()
        else:
            current_offset = 0

        # Find next bookmark
        next_bookmark = doc.get_next_bookmark(current_offset)
        if next_bookmark is not None:
            current_widget.hex_view.scrollToOffset(next_bookmark)

    def go_to_previous_bookmark(self):
        """Go to previous bookmark."""
        doc = self._document_model.current_document
        if not doc:
            return

        # Get current offset
        current_widget = self._tab_widget.currentWidget()
        if hasattr(current_widget, 'hex_view'):
            current_offset = current_widget.hex_view.get_offset_at_cursor()
        else:
            current_offset = 0

        # Find previous bookmark
        prev_bookmark = doc.get_prev_bookmark(current_offset)
        if prev_bookmark is not None:
            current_widget.hex_view.scrollToOffset(prev_bookmark)

    def toggle_bookmark_at_cursor(self):
        """Toggle bookmark at current cursor position."""
        doc = self._document_model.current_document
        if not doc:
            return

        # Get current offset
        current_widget = self._tab_widget.currentWidget()
        if hasattr(current_widget, 'hex_view'):
            current_offset = current_widget.hex_view.get_offset_at_cursor()
        else:
            current_offset = 0

        # Toggle bookmark
        doc.toggle_bookmark(current_offset)

    def go_back(self):
        """Go back in navigation history."""
        offset = self._jump_history.go_back()
        if offset is not None:
            current_widget = self._tab_widget.currentWidget()
            if hasattr(current_widget, 'hex_view'):
                current_widget.hex_view.scrollToOffset(offset)

    def go_forward(self):
        """Go forward in navigation history."""
        offset = self._jump_history.go_forward()
        if offset is not None:
            current_widget = self._tab_widget.currentWidget()
            if hasattr(current_widget, 'hex_view'):
                current_widget.hex_view.scrollToOffset(offset)

    # Folding
    def detect_folding_regions(self):
        """Auto-detect folding regions."""
        doc = self._document_model.current_document
        if not doc:
            return

        # Read first 4KB for detection
        data = doc.read(0, min(doc.file_size, 4096))
        self._folding_manager.auto_detect_regions(data)
        self._folding_manager.set_data_length(doc.file_size)

    def fold_all(self):
        """Fold all regions."""
        self._folding_manager.fold_all()

    def unfold_all(self):
        """Unfold all regions."""
        self._folding_manager.unfold_all()

    def toggle_fold_at_cursor(self):
        """Toggle fold at cursor position."""
        current_widget = self._tab_widget.currentWidget()
        if hasattr(current_widget, 'hex_view'):
            offset = current_widget.hex_view.get_offset_at_cursor()
            self._folding_manager.toggle_region(offset)

    # Multi-view
    def open_new_view(self):
        """Open a new view of current file."""
        # For now, this is a placeholder
        # A full implementation would create a new hex view synchronized with the current one
        pass

    def set_sync_scroll(self, enabled: bool):
        """Set scroll synchronization."""
        self._view_sync_manager.sync_horizontal = enabled
        self._view_sync_manager.sync_vertical = enabled

    def set_sync_cursor(self, enabled: bool):
        """Set cursor synchronization."""
        self._view_sync_manager.sync_cursor = enabled

    # Tools
    def compare_files(self):
        """Compare two files."""
        self._status_bar.showMessage("File compare not yet implemented", 3000)

    def show_checksum_dialog(self):
        """Show checksum dialog."""
        from .dialogs.checksum import ChecksumDialog

        doc = self._document_model.current_document
        if not doc:
            return

        dialog = ChecksumDialog(self, doc.file_path, doc.file_size)
        dialog.exec()

    # AI operations
    def analyze_selection(self):
        """Analyze selected data with AI."""
        doc = self._document_model.current_document
        if not doc:
            self._status_bar.showMessage("No file open", 3000)
            return

        hex_view = self._get_current_hex_view()
        if hex_view is not None:
            _data, start, end = hex_view.get_selection_data()
            if start >= 0 and end >= start:
                self.submit_ai_prompt(
                    "Analyze the current selection. "
                    "Start with read_selection, then explain the structure, encoding, and any unusual patterns."
                )
                return

        self.submit_ai_prompt(
            "Analyze the current file. "
            "Start with get_file_metadata and use read_bytes as needed to explain the file structure."
        )

    def detect_patterns(self):
        """Detect data patterns with AI."""
        doc = self._document_model.current_document
        if not doc:
            self._status_bar.showMessage("No file open", 3000)
            return

        self.submit_ai_prompt(
            "Detect important patterns in the active file. "
            "Start with get_file_metadata, then call detect_patterns and read_bytes if you need more detail. "
            "Summarize the most relevant patterns and offsets."
        )

    def generate_parsing_code(self):
        """Generate parsing code."""
        doc = self._document_model.current_document
        if not doc:
            self._status_bar.showMessage("No file open", 3000)
            return

        self.submit_ai_prompt(
            "Generate parsing code for the active file or current row. "
            "Start with get_file_metadata. If structure configs exist, inspect them with list_structure_configs "
            "and decode_structure before producing code. Include assumptions and return the final code in a code block."
        )

    def show_ai_settings(self):
        """Show AI settings dialog."""
        from .dialogs.ai_settings import AISettingsDialog

        # Get current settings
        current_settings = {}
        app = QApplication.instance()
        if hasattr(app, '_ai_settings'):
            current_settings = app._ai_settings

        dialog = AISettingsDialog(self, current_settings)
        if dialog.exec():
            settings = dialog.get_settings()
            # Save settings
            if hasattr(app, '_ai_settings'):
                app._ai_settings = settings
            # Save to persistent storage
            s = self._get_settings()
            s.setValue('ai_enabled', settings.get('enabled', True))
            s.setValue('ai_provider', settings.get('provider', 'local'))
            s.setValue('ai_local_endpoint', settings.get('local', {}).get('endpoint', ''))
            s.setValue('ai_local_model', settings.get('local', {}).get('model', ''))
            s.setValue('ai_cloud_provider', settings.get('cloud', {}).get('provider', ''))
            s.setValue('ai_cloud_api_key', settings.get('cloud', {}).get('api_key', ''))
            s.setValue('ai_cloud_base_url', settings.get('cloud', {}).get('base_url', ''))
            s.setValue('ai_cloud_model', settings.get('cloud', {}).get('model', ''))
            self._ai_manager.configure(settings)
            if hasattr(self, "_ai_panel_widget"):
                self._ai_panel_widget.refresh_provider_status()

    # Tab management
    def _add_editor_tab(self, doc: FileHandle):
        """Add editor tab for document."""
        # Create hex view widget
        hex_view_widget = HexEditorTabWidget(doc, self)
        index = self._tab_widget.addTab(hex_view_widget, doc.file_name)
        self._tab_widget.setCurrentIndex(index)
        self._update_tab_name(index, doc)

        # Connect hex view signals for status bar updates
        hex_view = hex_view_widget.hex_view
        self._connect_hex_view_signals(hex_view)
        hex_view_widget.data_changed.connect(self._refresh_current_view_state)
        self._refresh_current_view_state()

    def _update_tab_name(self, index: int, doc: FileHandle):
        """Update tab name with modification indicator."""
        name = doc.file_name
        if doc.file_state == FileState.MODIFIED:
            name = "● " + name
        self._tab_widget.setTabText(index, name)

    def _update_hex_views(self):
        """Update all hex views with current settings."""
        # Get current display mode from data model
        mode_map = {
            DisplayMode.HEX: "hex",
            DisplayMode.BINARY: "binary",
            DisplayMode.ASCII: "ascii",
            DisplayMode.OCTAL: "octal",
        }
        current_mode = mode_map.get(self._data_model.display_mode, "hex")

        # Update arrangement label in status bar
        arrangement_mode = self._data_model.arrangement_mode
        if arrangement_mode == ArrangementMode.EQUAL_FRAME:
            self._arrangement_label.setText(f"等长帧: {self._data_model.bytes_per_frame}")
        elif arrangement_mode == ArrangementMode.HEADER_LENGTH:
            self._arrangement_label.setText(f"头长度: {self._data_model.header_length}")
        else:
            self._arrangement_label.setText(f"自定义: {self._data_model.bytes_per_frame}")

        for i in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(i)
            if isinstance(widget, HexEditorTabWidget):
                # Update hex view display mode
                hex_view = widget.hex_view
                if hasattr(hex_view, 'set_display_mode'):
                    hex_view.set_display_mode(current_mode)
                if hasattr(hex_view, 'set_ascii_visible'):
                    hex_view.set_ascii_visible(self._ascii_visible)

    def _on_close_tab(self, index: int):
        """Handle tab close."""
        # Get document before closing to save its settings
        doc = self._document_model.get_document(index)
        if doc and doc.file_path:
            # Save bytes_per_row setting for this file
            widget = self._tab_widget.widget(index)
            if hasattr(widget, 'hex_view'):
                bytes_per_row = widget.hex_view._model._bytes_per_row
                self._set_file_bytes_per_row(doc.file_path, bytes_per_row)

        if self._document_model.close_document(index):
            self._tab_widget.removeTab(index)

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        if index >= 0:
            doc = self._document_model.get_document(index)
            if doc:
                self._document_model.set_current_document(doc)
        self._selection_label.setText(tr("status_selection", 0))
        self._refresh_current_view_state()

    def _on_document_changed(self, doc: FileHandle):
        """Handle document change."""
        if doc:
            self._size_label.setText(f"Size: {FormatUtils.format_size(doc.file_size)}")
        self._refresh_current_view_state()

    def _on_document_modified(self, doc: FileHandle):
        """Handle document modification."""
        # Find tab and update name
        for i in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(i)
            if isinstance(widget, HexEditorTabWidget):
                if widget.document == doc:
                    self._update_tab_name(i, doc)
                    break


class HexEditorTabWidget(QWidget):
    """Hex editor tab widget for a single document."""

    data_changed = pyqtSignal()

    def __init__(self, document: FileHandle, parent=None):
        super().__init__(parent)
        self.document = document
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        """Initialize hex view UI."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create hex view
        from .views.hex_view import HexViewWidget
        self._hex_view = HexViewWidget()
        self._hex_view.set_file_handle(self.document)

        layout.addWidget(self._hex_view)
        self.setLayout(layout)

        # Connect document signals
        self.document.data_changed.connect(self._on_data_changed)

    def _load_data(self):
        """Load data into hex view."""
        pass  # Already handled by set_file_handle

    def _on_data_changed(self, start: int, end: int):
        """Handle data change."""
        self.data_changed.emit()

    @property
    def hex_view(self):
        """Get hex view."""
        return self._hex_view.hex_view

    def update_display(self):
        """Update display settings."""
        # Apply current display mode and arrangement
        pass
