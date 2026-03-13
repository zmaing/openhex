"""
HexEditor Main Window

Main hex editor widget with panels and views.
"""

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QTabWidget, QTabBar, QLabel, QProgressBar, QFrame, QToolButton,
                             QPushButton, QStackedLayout, QSizePolicy, QStyle)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal, QSize, QSettings, QTimer
from typing import List
from pathlib import Path
from PyQt6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QPixmap

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
from .design_system import CHROME, MONO_FONT_FAMILY, UI_FONT_FAMILY
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
        self.setObjectName("hexEditorWorkspace")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#hexEditorWorkspace {{
                background-color: {CHROME.workspace_bg};
                border-radius: 14px;
            }}
            QWidget#editorCenterColumn,
            QWidget#editorAIPanelShell,
            QWidget#rightPanelShell {{
                background-color: {CHROME.surface};
                border: 1px solid {CHROME.border};
                border-radius: 14px;
            }}
            QFrame#editorEmptyStateCard {{
                background-color: {CHROME.surface_alt};
                border: 1px solid {CHROME.border};
                border-radius: 12px;
            }}
            QLabel#editorEmptyStateTitle {{
                color: {CHROME.text_primary};
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#editorEmptyStateBody {{
                color: {CHROME.text_secondary};
                font-size: 12px;
            }}
            QLabel#editorEmptyStateMeta {{
                color: {CHROME.text_muted};
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton#editorEmptyStatePrimary {{
                background-color: {CHROME.accent_surface};
                border: 1px solid {CHROME.accent_surface_strong};
                border-radius: 10px;
                padding: 6px 14px;
                min-height: 30px;
                font-weight: 700;
            }}
            QPushButton#editorEmptyStatePrimary:hover {{
                background-color: {CHROME.accent_surface_strong};
            }}
            QPushButton#editorEmptyStateSecondary {{
                background-color: {CHROME.surface};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
                padding: 6px 14px;
                min-height: 30px;
            }}
        """)
        self._document_model = DocumentModel()
        self._data_model = DataModel()
        self._ascii_visible = True
        self._undo_stack = UndoStack()
        self._splitter = None
        self._file_tree_width = CHROME.sidebar_width
        self._ai_panel_width = max(280, CHROME.right_panel_width)
        self._right_panel_width = CHROME.right_panel_width
        self._right_panel_standard_width = CHROME.right_panel_width
        self._right_panel_horizontal_width = CHROME.right_panel_horizontal_width
        self._panel_visibility = {
            "value": True,
            "ai": True,
            "structure": False,
        }
        self._panel_layout_mode = "horizontal"
        self._active_panel_id = "data"
        self._resolved_side_panel_signature = None

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
        if not settings.get("enabled", True) and self._panel_visibility.get("ai", False):
            self.set_ai_panel_visible(False)
        if hasattr(self, "_ai_panel_widget"):
            self._ai_panel_widget.refresh_provider_status()

    def _load_side_panel_settings(self):
        """Restore side panel visibility and layout settings."""
        s = self._get_settings()
        self._panel_visibility["value"] = s.value("side_panel/value_visible", True, type=bool)
        self._panel_visibility["ai"] = s.value("side_panel/ai_visible", False, type=bool)
        self._panel_visibility["structure"] = s.value("side_panel/structure_visible", False, type=bool)
        self._panel_layout_mode = "horizontal"

        saved_active_panel_id = s.value("side_panel/active_panel", "value", type=str)
        self._active_panel_id = {
            "value": "data",
            "data": "data",
            "structure": "structure",
            "info": "data",
            "ai": "data",
        }.get(saved_active_panel_id, "data")
        self._refresh_side_panel_layout()
        self._sync_ai_panel_visibility()
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
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Create splitter for resizable panels
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("editorWorkspaceSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(6)
        self._splitter.setStyleSheet(f"""
            QSplitter {{
                background: transparent;
            }}
            QSplitter::handle {{
                background: transparent;
                margin: 6px 1px;
                border-radius: 3px;
            }}
            QSplitter::handle:hover {{
                background: {CHROME.border};
            }}
        """)

        # Left panel - File browser
        from .panels.file_browser import FileBrowser
        self._file_browser = FileBrowser()
        self._file_browser.setMinimumWidth(220)
        self._file_browser.file_double_clicked.connect(self._on_file_open_request)
        self._splitter.addWidget(self._file_browser)

        # Center widget - Main editor area
        center_widget = QWidget()
        center_widget.setObjectName("editorCenterColumn")
        center_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(8, 8, 8, 8)
        center_layout.setSpacing(6)

        # Tab widget for multiple files
        self._tab_widget = QTabWidget()
        self._tab_widget.setObjectName("editorTabWidget")
        self._tab_widget.setDocumentMode(True)
        self._tab_widget.tabBar().setDrawBase(False)
        self._tab_widget.tabBar().setExpanding(False)
        self._tab_widget.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self._tab_widget.setTabsClosable(False)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        # Style
        self._tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {CHROME.surface_alt};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
                margin-top: 4px;
            }}
            QTabBar::tab {{
                background-color: {CHROME.surface};
                color: {CHROME.text_muted};
                padding: 3px 8px;
                margin-right: 3px;
                margin-bottom: 1px;
                border: 1px solid {CHROME.border};
                border-radius: 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_primary};
                border-color: {CHROME.border_strong};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {CHROME.surface_hover};
                color: {CHROME.text_primary};
            }}
            QToolButton#editorTabCloseButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                min-width: 14px;
                max-width: 14px;
                min-height: 14px;
                max-height: 14px;
                padding: 0;
                margin-left: 3px;
            }}
            QToolButton#editorTabCloseButton:hover {{
                background-color: {CHROME.surface_raised};
                border-color: {CHROME.border_strong};
            }}
            QToolButton#editorTabCloseButton:pressed {{
                background-color: {CHROME.surface_hover};
                border-color: {CHROME.accent_surface_strong};
            }}
            QTabWidget::tab-bar {{
                alignment: left;
                left: 1px;
            }}
        """)

        self._center_stack_host = QWidget()
        self._center_stack_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._center_stack = QStackedLayout()
        self._center_stack.setContentsMargins(0, 0, 0, 0)
        self._center_stack.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self._center_empty_state = self._create_center_empty_state()
        self._center_stack.addWidget(self._center_empty_state)
        self._center_stack.addWidget(self._tab_widget)
        self._center_stack_host.setLayout(self._center_stack)

        center_layout.addWidget(self._center_stack_host, 1)

        # Status bar
        self._status_bar = self._create_status_bar()
        center_layout.addWidget(self._status_bar)

        center_widget.setLayout(center_layout)
        self._splitter.addWidget(center_widget)

        self._ai_panel = self._create_ai_panel()
        self._ai_panel_shell = self._create_ai_workspace_panel()
        self._splitter.addWidget(self._ai_panel_shell)

        # Right panel - Info panels
        self._right_panel = self._create_right_panel()
        self._splitter.addWidget(self._right_panel)

        # Set initial sizes
        self._splitter.setSizes([self._file_tree_width, 780, self._ai_panel_width, self._right_panel_width])

        main_layout.addWidget(self._splitter)
        self.setLayout(main_layout)
        self._update_center_empty_state()

    def _create_status_bar(self):
        """Create status bar."""
        bar = QFrame()
        bar.setObjectName("workspaceStatusBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(f"""
            QFrame#workspaceStatusBar {{
                background: transparent;
                border: none;
            }}
            QFrame#workspaceStatusRail {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {CHROME.surface_alt},
                    stop: 1 {CHROME.surface}
                );
                border: 1px solid {CHROME.border_strong};
                border-radius: 12px;
            }}
            QFrame#statusDocumentGroup,
            QFrame#statusMetricGroup,
            QFrame#statusModeGroup {{
                background: transparent;
                border: none;
                border-radius: 0;
                min-height: 30px;
                max-height: 30px;
            }}
            QFrame#statusDocumentAccent {{
                min-width: 4px;
                max-width: 4px;
                min-height: 16px;
                max-height: 16px;
                border-radius: 2px;
                background-color: {CHROME.success};
            }}
            QFrame#statusDocumentAccent[stateTone="saved"] {{
                background-color: {CHROME.success};
            }}
            QFrame#statusDocumentAccent[stateTone="modified"] {{
                background-color: {CHROME.danger};
            }}
            QFrame#statusDocumentAccent[stateTone="draft"] {{
                background-color: {CHROME.warning};
            }}
            QFrame#statusClusterDivider {{
                background-color: {CHROME.border};
                min-width: 1px;
                max-width: 1px;
                min-height: 12px;
                margin: 6px 2px;
            }}
            QFrame#statusDocumentStateDot {{
                min-width: 8px;
                max-width: 8px;
                min-height: 8px;
                max-height: 8px;
                border-radius: 4px;
                background-color: {CHROME.success};
            }}
            QFrame#statusDocumentStateDot[stateTone="saved"] {{
                background-color: {CHROME.success};
            }}
            QFrame#statusDocumentStateDot[stateTone="modified"] {{
                background-color: {CHROME.danger};
            }}
            QFrame#statusDocumentStateDot[stateTone="draft"] {{
                background-color: {CHROME.warning};
            }}
            QFrame#statusField {{
                background: transparent;
                border: none;
            }}
            QLabel#statusMessageChip {{
                background-color: {CHROME.accent_surface};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.accent_surface_strong};
                border-radius: 9px;
                min-height: 28px;
                max-height: 28px;
                padding: 0 10px;
                font-size: 10px;
                font-weight: 700;
                font-family: {UI_FONT_FAMILY};
            }}
            QLabel#statusDocumentName {{
                color: {CHROME.text_primary};
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: 700;
                font-family: {UI_FONT_FAMILY};
            }}
            QLabel#statusDocumentMeta {{
                color: {CHROME.text_muted};
                background: transparent;
                border: none;
                font-size: 9px;
                font-weight: 500;
                font-family: {UI_FONT_FAMILY};
            }}
            QLabel#statusDocumentTypeChip,
            QLabel#statusDocumentStateChip {{
                min-height: 20px;
                max-height: 20px;
                padding: 0 2px;
                border: none;
                background: transparent;
                font-size: 10px;
                font-weight: 700;
                font-family: {UI_FONT_FAMILY};
            }}
            QLabel#statusDocumentTypeChip {{
                color: {CHROME.text_secondary};
            }}
            QLabel#statusDocumentStateChip[stateTone="saved"] {{
                color: {CHROME.success};
            }}
            QLabel#statusDocumentStateChip[stateTone="modified"] {{
                color: {CHROME.danger};
            }}
            QLabel#statusDocumentStateChip[stateTone="draft"] {{
                color: {CHROME.warning};
            }}
            QLabel#statusFieldCaption {{
                color: {CHROME.text_muted};
                background: transparent;
                border: none;
                font-size: 8px;
                font-weight: 700;
                font-family: {UI_FONT_FAMILY};
            }}
            QLabel#statusFieldValue {{
                color: {CHROME.text_secondary};
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: 600;
                font-family: {MONO_FONT_FAMILY};
            }}
            QLabel#statusFieldValueStrong {{
                color: {CHROME.text_primary};
                background: transparent;
                border: none;
                font-size: 10px;
                font-weight: 700;
                font-family: {MONO_FONT_FAMILY};
            }}
            QProgressBar#statusProgressBar {{
                background-color: {CHROME.surface_raised};
                border: 1px solid {CHROME.border_strong};
                border-radius: 7px;
                min-height: 20px;
                max-height: 20px;
                padding: 1px;
                color: {CHROME.text_secondary};
                text-align: center;
            }}
            QProgressBar#statusProgressBar::chunk {{
                background-color: {CHROME.accent_surface_strong};
                border-radius: 6px;
                margin: 2px;
            }}
        """)
        bar.setFixedHeight(max(CHROME.status_bar_height, 34))

        root_layout = QHBoxLayout(bar)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        rail = QFrame()
        rail.setObjectName("workspaceStatusRail")
        rail.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        rail_layout = QHBoxLayout(rail)
        rail_layout.setContentsMargins(6, 3, 6, 3)
        rail_layout.setSpacing(6)

        self._document_status_group = self._create_document_status_group()
        rail_layout.addWidget(self._document_status_group, 0, Qt.AlignmentFlag.AlignVCenter)
        self._document_metric_divider = self._create_status_divider_widget("statusRailSectionDivider")
        rail_layout.addWidget(self._document_metric_divider, 0, Qt.AlignmentFlag.AlignVCenter)

        metric_group, metric_layout = self._create_status_cluster("statusMetricGroup")
        self._offset_field, self._pos_label = self._create_status_field(tr("status_caption_offset"), "0x00000000")
        metric_layout.addWidget(self._offset_field)
        self._metric_offset_selection_divider = self._create_status_divider_widget()
        metric_layout.addWidget(self._metric_offset_selection_divider)

        self._selection_field, self._selection_label = self._create_status_field(tr("status_caption_selection"), "0 B")
        metric_layout.addWidget(self._selection_field)
        self._metric_selection_arrangement_divider = self._create_status_divider_widget()
        metric_layout.addWidget(self._metric_selection_arrangement_divider)

        self._arrangement_field, self._arrangement_label = self._create_status_field(
            tr("status_caption_layout"),
            self._format_arrangement_status("equal_frame", self._data_model.bytes_per_frame),
        )
        metric_layout.addWidget(self._arrangement_field)
        self._metric_arrangement_encoding_divider = self._create_status_divider_widget()
        metric_layout.addWidget(self._metric_arrangement_encoding_divider)

        self._encoding_field, self._encoding_label = self._create_status_field(tr("status_caption_encoding"), "UTF-8")
        metric_layout.addWidget(self._encoding_field)
        self._metric_encoding_size_divider = self._create_status_divider_widget()
        metric_layout.addWidget(self._metric_encoding_size_divider)

        self._size_field, self._size_label = self._create_status_field(tr("status_caption_size"), "0 B")
        metric_layout.addWidget(self._size_field)
        rail_layout.addWidget(metric_group, 0, Qt.AlignmentFlag.AlignVCenter)

        self._msg_label = QLabel("")
        self._msg_label.setObjectName("statusMessageChip")
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setVisible(False)
        rail_layout.addWidget(self._msg_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._progress = QProgressBar()
        self._progress.setObjectName("statusProgressBar")
        self._progress.setFixedWidth(88)
        self._progress.setVisible(False)
        rail_layout.addWidget(self._progress, 0, Qt.AlignmentFlag.AlignVCenter)

        mode_group, mode_layout = self._create_status_cluster("statusModeGroup")
        self._view_mode_field, self._mode_label = self._create_status_field(
            tr("status_caption_view"),
            "Hex",
            value_object_name="statusFieldValueStrong",
        )
        mode_layout.addWidget(self._view_mode_field)
        self._mode_group_divider = self._create_status_divider_widget()
        mode_layout.addWidget(self._mode_group_divider)

        self._edit_mode_field, self._edit_mode_label = self._create_status_field(
            tr("status_caption_edit"),
            "OVR",
            value_object_name="statusFieldValueStrong",
        )
        mode_layout.addWidget(self._edit_mode_field)
        self._metric_mode_divider = self._create_status_divider_widget("statusRailSectionDivider")
        rail_layout.addWidget(self._metric_mode_divider, 0, Qt.AlignmentFlag.AlignVCenter)
        rail_layout.addWidget(mode_group, 0, Qt.AlignmentFlag.AlignVCenter)
        rail_layout.addStretch(1)

        root_layout.addWidget(rail)

        # Add showMessage method
        bar.showMessage = lambda msg, timeout=3000: self._show_status_message(msg, timeout)
        self._apply_balanced_status_bar_visibility()
        self._stabilize_status_bar_widths()

        return bar

    def _create_document_status_group(self) -> QFrame:
        """Create the document summary block embedded in the workspace status bar."""
        group = QFrame()
        group.setObjectName("statusDocumentGroup")
        group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._document_status_accent = QFrame()
        self._document_status_accent.setObjectName("statusDocumentAccent")
        self._document_status_accent.setProperty("stateTone", "saved")
        layout.addWidget(self._document_status_accent, 0, Qt.AlignmentFlag.AlignVCenter)

        self._document_status_state_dot = QFrame()
        self._document_status_state_dot.setObjectName("statusDocumentStateDot")
        self._document_status_state_dot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._document_status_state_dot.setProperty("stateTone", "saved")
        self._document_status_state_dot.setToolTip(tr("status_saved"))
        layout.addWidget(self._document_status_state_dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self._document_status_name = QLabel("Untitled")
        self._document_status_name.setObjectName("statusDocumentName")
        self._document_status_name.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._document_status_name, 0, Qt.AlignmentFlag.AlignVCenter)

        self._document_status_meta = QLabel("")
        self._document_status_meta.setObjectName("statusDocumentMeta")
        self._document_status_meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._document_status_meta.setMinimumWidth(0)
        layout.addWidget(self._document_status_meta, 1, Qt.AlignmentFlag.AlignVCenter)

        self._document_status_chip_divider = self._create_status_divider_widget()
        layout.addWidget(self._document_status_chip_divider, 0, Qt.AlignmentFlag.AlignVCenter)

        self._document_status_kind_chip = QLabel("BIN")
        self._document_status_kind_chip.setObjectName("statusDocumentTypeChip")
        layout.addWidget(self._document_status_kind_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        self._document_status_state_divider = self._create_status_divider_widget()
        layout.addWidget(self._document_status_state_divider, 0, Qt.AlignmentFlag.AlignVCenter)

        self._document_status_state_chip = QLabel(tr("status_saved"))
        self._document_status_state_chip.setObjectName("statusDocumentStateChip")
        self._document_status_state_chip.setProperty("stateTone", "saved")
        layout.addWidget(self._document_status_state_chip, 0, Qt.AlignmentFlag.AlignVCenter)
        return group

    def _create_status_cluster(self, object_name: str) -> tuple[QFrame, QHBoxLayout]:
        """Create a shared capsule group for compact footer chrome."""
        group = QFrame()
        group.setObjectName(object_name)
        group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)
        return group, layout

    def _add_status_cluster_divider(self, layout: QHBoxLayout, object_name: str = "statusClusterDivider") -> None:
        """Insert a subtle divider inside a footer capsule group."""
        layout.addWidget(self._create_status_divider_widget(object_name))

    def _create_status_divider_widget(self, object_name: str = "statusClusterDivider") -> QFrame:
        """Create a subtle vertical divider shared by footer groups."""
        divider = QFrame()
        divider.setObjectName(object_name)
        divider.setFrameShape(QFrame.Shape.VLine)
        return divider

    def _create_status_field(
        self,
        caption: str,
        value: str,
        value_object_name: str = "statusFieldValue",
    ) -> tuple[QFrame, QLabel]:
        """Create a compact key-value field for the workspace status rail."""
        field = QFrame()
        field.setObjectName("statusField")

        layout = QHBoxLayout(field)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(5)

        caption_label = QLabel(caption)
        caption_label.setObjectName("statusFieldCaption")
        layout.addWidget(caption_label)

        value_label = QLabel(value)
        value_label.setObjectName(value_object_name)
        layout.addWidget(value_label)

        return field, value_label

    def _apply_balanced_status_bar_visibility(self) -> None:
        """Hide secondary footer details so the lower rail stays readable on narrower windows."""
        for widget in (
            self._document_status_accent,
            self._document_status_meta,
            self._document_status_chip_divider,
            self._document_status_kind_chip,
            self._document_status_state_divider,
            self._document_status_state_chip,
            self._document_metric_divider,
            self._metric_offset_selection_divider,
            self._metric_selection_arrangement_divider,
            self._arrangement_field,
            self._metric_arrangement_encoding_divider,
            self._encoding_field,
            self._metric_encoding_size_divider,
            self._metric_mode_divider,
            self._mode_group_divider,
        ):
            widget.hide()

    def _stabilize_status_bar_widths(self) -> None:
        """Reserve stable widths for dynamic footer tokens so saving does not resize the window."""
        self._document_status_kind_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._document_status_state_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        kind_width = max(
            52,
            self._status_label_width(
                self._document_status_kind_chip,
                ["BIN", "DAT", "JSON", "ASCII", "MARKDOWN", "PCAPNG"],
                padding=16,
            ),
        )
        state_width = max(
            72,
            self._status_label_width(
                self._document_status_state_chip,
                [
                    tr("status_saved"),
                    tr("workspace_state_draft"),
                    tr("workspace_state_modified"),
                ],
                padding=22,
            ),
        )
        name_width = max(
            112,
            self._status_label_width(
                self._document_status_name,
                [
                    self._compact_status_text("requirements.txt", max_chars=18),
                    self._compact_status_text(
                        "very_long_filename_placeholder.bin",
                        max_chars=18,
                    ),
                ],
                padding=10,
            ),
        )
        message_width = max(
            96,
            self._status_label_width(
                self._msg_label,
                [
                    tr("status_saved"),
                    "Save failed",
                    "No file open",
                    "No file to save",
                    tr("filter_status_cleared"),
                ],
                padding=20,
            ),
        )

        self._document_status_name.setFixedWidth(name_width)
        self._document_status_kind_chip.setFixedWidth(kind_width)
        self._document_status_state_chip.setFixedWidth(state_width)
        self._msg_label.setFixedWidth(message_width)
        self._msg_label.setFixedHeight(28)

    def _status_label_width(self, label: QLabel, texts: list[str], padding: int = 16) -> int:
        """Estimate a fixed label width for a set of short state strings."""
        metrics = QFontMetrics(label.font())
        return max(metrics.horizontalAdvance(text) for text in texts) + padding

    def _format_arrangement_status(self, mode: str, value: int) -> str:
        """Return a compact arrangement summary for the workspace status rail."""
        if mode == "header_length":
            return tr("status_arrangement_header", value)
        if mode == "custom":
            return tr("status_arrangement_custom", value)
        return tr("status_arrangement_equal", value)

    def _create_center_empty_state(self):
        """Create the empty-state canvas shown before any file is open."""
        card = QFrame()
        card.setObjectName("editorEmptyStateCard")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addStretch()

        content = QWidget(card)
        content.setFixedWidth(560)
        content.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        title = QLabel("Open a binary workspace")
        title.setObjectName("editorEmptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title)

        body = QLabel(
            "先打开文件或文件夹，再从右侧智能面板进入分析和后续编辑流程。"
        )
        body.setObjectName("editorEmptyStateBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_layout.addWidget(body)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 6, 0, 6)
        actions.setSpacing(10)
        actions.addStretch()

        open_file_btn = QPushButton("Open File")
        open_file_btn.setObjectName("editorEmptyStatePrimary")
        open_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_file_btn.clicked.connect(lambda checked=False: self.open_file())
        actions.addWidget(open_file_btn)

        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setObjectName("editorEmptyStateSecondary")
        open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder_btn.clicked.connect(lambda checked=False: self.open_folder())
        actions.addWidget(open_folder_btn)

        actions.addStretch()
        content_layout.addLayout(actions)

        meta = QLabel("Tips: Cmd/Ctrl+O 打开文件，Explorer 浏览目录，AI 面板会自动读取当前上下文。")
        meta.setObjectName("editorEmptyStateMeta")
        meta.setWordWrap(True)
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_layout.addWidget(meta)

        content.setLayout(content_layout)
        layout.addWidget(content, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

        card.setLayout(layout)
        return card

    def _update_center_empty_state(self):
        """Show the empty-state canvas when no editor tabs are open."""
        if hasattr(self, "_center_stack"):
            has_tabs = self._tab_widget.count() > 0
            self._center_stack.setCurrentIndex(0 if not has_tabs else 1)
            self._update_document_status_summary(self._document_model.current_document if has_tabs else None)

    def _update_document_status_summary(self, doc: FileHandle | None):
        """Refresh the document summary embedded in the workspace status bar."""
        if not hasattr(self, "_document_status_group"):
            return

        if not doc:
            empty_name = "Untitled"
            empty_meta = tr("workspace_unsaved")
            self._document_status_name.setText(self._compact_status_text(empty_name, max_chars=16))
            self._document_status_name.setToolTip(empty_name)
            self._document_status_meta.setText(self._compact_status_text(empty_meta, max_chars=18))
            self._document_status_meta.setToolTip(empty_meta)
            self._document_status_kind_chip.setText("BIN")
            state_text = tr("workspace_state_draft")
            self._document_status_state_chip.setText(state_text)
            self._document_status_state_chip.setProperty("stateTone", "draft")
            self._document_status_accent.setProperty("stateTone", "draft")
            self._document_status_state_dot.setProperty("stateTone", "draft")
            self._document_status_state_dot.setToolTip(state_text)
            self._repolish_widget(self._document_status_state_chip)
            self._repolish_widget(self._document_status_accent)
            self._repolish_widget(self._document_status_state_dot)
            return

        self._document_status_name.setText(self._compact_status_text(doc.file_name, max_chars=18))
        self._document_status_name.setToolTip(doc.file_name)

        if doc.file_path:
            parent_path = str(Path(doc.file_path).parent)
            self._document_status_meta.setText(self._compact_status_text(parent_path, max_chars=20))
            self._document_status_meta.setToolTip(doc.file_path)
        else:
            draft_text = tr("workspace_unsaved")
            self._document_status_meta.setText(self._compact_status_text(draft_text, max_chars=18))
            self._document_status_meta.setToolTip(draft_text)

        suffix = Path(doc.file_name).suffix.upper().lstrip(".") or "BIN"
        self._document_status_kind_chip.setText(suffix[:10])

        if doc.file_state == FileState.MODIFIED:
            state_text = tr("workspace_state_modified")
            tone = "modified"
        elif doc.file_state == FileState.NEW:
            state_text = tr("workspace_state_draft")
            tone = "draft"
        else:
            state_text = tr("status_saved")
            tone = "saved"
        self._document_status_state_chip.setText(state_text)
        self._document_status_state_chip.setProperty("stateTone", tone)
        self._document_status_accent.setProperty("stateTone", tone)
        self._document_status_state_dot.setProperty("stateTone", tone)
        self._document_status_state_dot.setToolTip(state_text)
        self._repolish_widget(self._document_status_state_chip)
        self._repolish_widget(self._document_status_accent)
        self._repolish_widget(self._document_status_state_dot)

    def _compact_status_text(self, text: str, max_chars: int = 30) -> str:
        """Return a compact single-line status-bar label with middle truncation."""
        compact = " ".join(str(text).split())
        if len(compact) <= max_chars:
            return compact
        head = max_chars // 2 - 1
        tail = max_chars - head - 1
        return f"{compact[:head]}…{compact[-tail:]}"

    def _repolish_widget(self, widget):
        """Refresh styles after dynamic property updates."""
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()

    def _create_tab_close_icon(self) -> QIcon:
        """Create a subtle close icon for editor tabs."""
        icon = QIcon()
        for mode, color in (
            (QIcon.Mode.Normal, QColor(CHROME.text_muted)),
            (QIcon.Mode.Active, QColor(CHROME.text_primary)),
            (QIcon.Mode.Selected, QColor(CHROME.text_primary)),
            (QIcon.Mode.Disabled, QColor(CHROME.border_strong)),
        ):
            pixmap = QPixmap(12, 12)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(color)
            pen.setWidthF(1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(3, 3, 9, 9)
            painter.drawLine(9, 3, 3, 9)
            painter.end()
            icon.addPixmap(pixmap, mode)
        return icon

    def _refresh_tab_close_buttons(self):
        """Replace default tab close buttons with the shared chrome version."""
        if not hasattr(self, "_tab_widget"):
            return

        tab_bar = self._tab_widget.tabBar()
        close_side = self._tab_close_button_position()
        for index in range(tab_bar.count()):
            tab_widget = self._tab_widget.widget(index)
            for side in (QTabBar.ButtonPosition.LeftSide, QTabBar.ButtonPosition.RightSide):
                existing = tab_bar.tabButton(index, side)
                if existing is not None:
                    tab_bar.setTabButton(index, side, None)
                    existing.deleteLater()

            button = QToolButton(tab_bar)
            button.setObjectName("editorTabCloseButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoRaise(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setIcon(self._create_tab_close_icon())
            button.setIconSize(QSize(9, 9))
            button.setToolTip(tr("menu_close"))
            button.clicked.connect(
                lambda checked=False, tab=tab_widget: self._close_editor_tab_widget(tab)
            )
            tab_bar.setTabButton(index, close_side, button)

    def _tab_close_button_position(self) -> QTabBar.ButtonPosition:
        """Return the style-preferred side for editor tab close buttons."""
        if not hasattr(self, "_tab_widget"):
            return QTabBar.ButtonPosition.RightSide

        tab_bar = self._tab_widget.tabBar()
        style = tab_bar.style()
        if style is None:
            return QTabBar.ButtonPosition.RightSide

        close_side = style.styleHint(QStyle.StyleHint.SH_TabBar_CloseButtonPosition, None, tab_bar)
        if close_side in (
            QTabBar.ButtonPosition.LeftSide,
            QTabBar.ButtonPosition.LeftSide.value,
        ):
            return QTabBar.ButtonPosition.LeftSide
        return QTabBar.ButtonPosition.RightSide

    def _close_editor_tab_widget(self, tab_widget: QWidget):
        """Close the tab that owns a custom close button."""
        if not hasattr(self, "_tab_widget") or tab_widget is None:
            return

        index = self._tab_widget.indexOf(tab_widget)
        if index >= 0:
            self._on_close_tab(index)

    def _show_status_message(self, message: str, timeout: int = 3000):
        """Show a temporary message in the status bar."""
        if not hasattr(self, "_status_message_timer"):
            self._status_message_timer = QTimer(self)
            self._status_message_timer.setSingleShot(True)
            self._status_message_timer.timeout.connect(self._clear_current_status_message)
        self._msg_label.setText(self._compact_status_text(message, max_chars=18))
        self._msg_label.setToolTip(message)
        self._msg_label.setVisible(bool(message))
        if timeout and message:
            self._status_message_timer.start(timeout)
        elif hasattr(self, "_status_message_timer"):
            self._status_message_timer.stop()

    def _clear_current_status_message(self):
        """Clear the current transient status message."""
        self._msg_label.clear()
        self._msg_label.setToolTip("")
        self._msg_label.setVisible(False)

    def _create_right_panel(self):
        """Create right side info panel."""
        widget = QWidget()
        widget.setObjectName("rightPanelShell")
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setStyleSheet(f"""
            QFrame#rightPanelSwitcher {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {CHROME.border};
            }}
            QTabBar#rightPanelTabBar {{
                background: transparent;
                border: none;
            }}
            QTabBar#rightPanelTabBar::tab {{
                background-color: transparent;
                color: {CHROME.text_muted};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 0 12px;
                min-height: 26px;
                font-size: 10px;
                font-weight: 700;
                margin-right: 6px;
            }}
            QTabBar#rightPanelTabBar::tab:hover:!selected {{
                background-color: {CHROME.surface_alt};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                color: {CHROME.text_primary};
            }}
            QTabBar#rightPanelTabBar::tab:selected {{
                background-color: transparent;
                border-bottom-color: {CHROME.accent};
                color: {CHROME.text_primary};
            }}
            QFrame#sidePanelViewFrame {{
                background: transparent;
                border: none;
            }}
            QFrame#sidePanelViewFrame[activeView="true"] {{
                background: transparent;
                border: none;
            }}
            QFrame#sidePanelViewHeader {{
                background: transparent;
                border: none;
            }}
            QFrame#sidePanelViewAccent {{
                min-width: 4px;
                max-width: 4px;
                min-height: 14px;
                max-height: 14px;
                border-radius: 2px;
                background-color: {CHROME.border_strong};
            }}
            QFrame#sidePanelViewFrame[activeView="true"] QFrame#sidePanelViewAccent {{
                background-color: {CHROME.accent};
            }}
            QLabel#sidePanelViewLabel {{
                color: {CHROME.text_muted};
                font-size: 9px;
                font-weight: 700;
            }}
            QFrame#sidePanelViewBody {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(5)

        self._right_panel_switcher = QFrame()
        self._right_panel_switcher.setObjectName("rightPanelSwitcher")
        self._right_panel_switcher.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._right_panel_switcher.setFixedHeight(34)
        self._right_panel_switcher.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._right_panel_switcher_layout = QHBoxLayout(self._right_panel_switcher)
        self._right_panel_switcher_layout.setContentsMargins(0, 0, 0, 0)
        self._right_panel_switcher_layout.setSpacing(0)
        self._right_panel_tab_bar = QTabBar(self._right_panel_switcher)
        self._right_panel_tab_bar.setObjectName("rightPanelTabBar")
        self._right_panel_tab_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._right_panel_tab_bar.setDrawBase(False)
        self._right_panel_tab_bar.setDocumentMode(True)
        self._right_panel_tab_bar.setElideMode(Qt.TextElideMode.ElideNone)
        self._right_panel_tab_bar.setExpanding(False)
        self._right_panel_tab_bar.setMovable(False)
        self._right_panel_tab_bar.setUsesScrollButtons(False)
        self._right_panel_tab_bar.currentChanged.connect(self._on_side_panel_switcher_changed)
        self._right_panel_switcher_layout.addWidget(self._right_panel_tab_bar, 0, Qt.AlignmentFlag.AlignVCenter)
        self._right_panel_switcher_layout.addStretch()
        self._right_panel_switcher.hide()
        self._panel_switcher_tabs = {}
        layout.addWidget(self._right_panel_switcher)

        self._right_panel_content = QWidget()
        self._right_panel_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._right_panel_content.setObjectName("rightPanelContent")
        self._right_panel_content.setStyleSheet("background: transparent;")
        self._right_panel_content_layout = QVBoxLayout()
        self._right_panel_content_layout.setContentsMargins(0, 0, 0, 0)
        self._right_panel_content_layout.setSpacing(0)
        self._right_panel_content.setLayout(self._right_panel_content_layout)

        self._data_value = self._create_data_value_panel()
        self._structure_panel = self._create_structure_panel()
        self._panel_horizontal_splitter = self._create_side_panel_splitter(Qt.Orientation.Horizontal)
        self._side_panels = {
            "data": self._data_value,
            "structure": self._structure_panel,
        }
        self._side_panel_hosts = {
            panel_id: self._create_side_panel_host(panel_id, panel)
            for panel_id, panel in self._side_panels.items()
        }
        self._right_panel_stack_host = QWidget(self._right_panel_content)
        self._right_panel_stack_host.setObjectName("rightPanelStackHost")
        self._right_panel_stack_host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._right_panel_stack_host.setStyleSheet("background: transparent;")
        self._right_panel_stack = QStackedLayout()
        self._right_panel_stack.setContentsMargins(0, 0, 0, 0)
        self._right_panel_stack.setStackingMode(QStackedLayout.StackingMode.StackOne)
        for panel_id in ("data", "structure"):
            self._right_panel_stack.addWidget(self._side_panel_hosts[panel_id])
        self._right_panel_stack_host.setLayout(self._right_panel_stack)
        self._right_panel_content_layout.addWidget(self._right_panel_stack_host, 1)

        layout.addWidget(self._right_panel_content, 1)
        self._right_panel_status_bar = self._create_side_panel_status_bar()
        layout.addWidget(self._right_panel_status_bar)
        widget.setLayout(layout)
        widget.setMinimumWidth(228)
        widget.installEventFilter(self)

        self._refresh_side_panel_layout()
        return widget

    def _create_side_panel_splitter(self, orientation: Qt.Orientation):
        """Create a splitter used for multi-panel layouts."""
        splitter = QSplitter(orientation)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(f"""
            QSplitter {{
                background: transparent;
            }}
            QSplitter::handle {{
                background-color: transparent;
                margin: 1px;
                border-radius: 3px;
            }}
            QSplitter::handle:hover {{
                background-color: {CHROME.border};
            }}
        """)
        return splitter

    def _create_side_panel_host(self, panel_id: str, panel_widget: QWidget) -> QFrame:
        """Wrap a panel in a compact host container for multi-view layouts."""
        host = QFrame()
        host.setObjectName("sidePanelViewFrame")
        host.setProperty("panelId", panel_id)
        host.setProperty("activeView", "false")
        host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame(host)
        header.setObjectName("sidePanelViewHeader")
        header.setFixedHeight(24)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 4)
        header_layout.setSpacing(6)

        accent = QFrame(header)
        accent.setObjectName("sidePanelViewAccent")
        header_layout.addWidget(accent, 0, Qt.AlignmentFlag.AlignVCenter)

        label = QLabel(self._get_panel_label(panel_id))
        label.setObjectName("sidePanelViewLabel")
        header_layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch()

        body = QFrame(host)
        body.setObjectName("sidePanelViewBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(panel_widget)

        layout.addWidget(header)
        layout.addWidget(body, 1)

        host._header = header
        return host

    def _clear_side_panel_switcher(self):
        """Remove any previously rendered inspector tabs."""
        blocked = self._right_panel_tab_bar.blockSignals(True)
        while self._right_panel_tab_bar.count():
            self._right_panel_tab_bar.removeTab(0)
        self._right_panel_tab_bar.blockSignals(blocked)
        self._panel_switcher_tabs = {}

    def _rebuild_side_panel_switcher(self, active_panel_ids: List[str]):
        """Render VS Code-style tabs for the currently visible inspector panels."""
        self._clear_side_panel_switcher()
        show_switcher = len(active_panel_ids) > 1
        self._right_panel_switcher.setVisible(show_switcher)
        if not show_switcher:
            return

        blocked = self._right_panel_tab_bar.blockSignals(True)
        for panel_id in active_panel_ids:
            index = self._right_panel_tab_bar.addTab(self._get_panel_tab_label(panel_id))
            self._right_panel_tab_bar.setTabData(index, panel_id)
            self._right_panel_tab_bar.setTabToolTip(index, self._get_panel_label(panel_id))
            self._panel_switcher_tabs[panel_id] = index
        self._update_side_panel_switcher_state(active_panel_ids)
        self._right_panel_tab_bar.blockSignals(blocked)

    def _update_side_panel_switcher_state(self, active_panel_ids: List[str] | None = None):
        """Refresh the visible tab selection for the current panel set."""
        if active_panel_ids is None:
            active_panel_ids = self._get_active_panel_ids()

        target_index = self._panel_switcher_tabs.get(self._active_panel_id, -1)
        if target_index < 0 and active_panel_ids:
            target_index = self._panel_switcher_tabs.get(active_panel_ids[0], -1)
        if target_index < 0:
            return

        blocked = self._right_panel_tab_bar.blockSignals(True)
        self._right_panel_tab_bar.setCurrentIndex(target_index)
        self._right_panel_tab_bar.blockSignals(blocked)

    def _on_side_panel_switcher_changed(self, index: int) -> None:
        """Switch the visible inspector page when the tab bar selection changes."""
        panel_id = self._right_panel_tab_bar.tabData(index)
        if not panel_id:
            return
        self._set_active_side_panel(str(panel_id))

    def _set_active_side_panel(self, panel_id: str):
        """Focus a specific side panel from the inspector tab bar."""
        active_panel_ids = self._get_active_panel_ids()
        if panel_id not in active_panel_ids:
            return

        self._active_panel_id = panel_id
        self._show_active_side_panel(panel_id, active_panel_ids)
        self._save_side_panel_settings()

    def _show_active_side_panel(self, panel_id: str, active_panel_ids: List[str] | None = None) -> None:
        """Display the requested side panel inside the stacked inspector content area."""
        if active_panel_ids is None:
            active_panel_ids = self._get_active_panel_ids()
        host = self._side_panel_hosts.get(panel_id)
        if host is None:
            return
        self._right_panel_stack.setCurrentWidget(host)
        for current_panel_id, current_host in self._side_panel_hosts.items():
            should_show = current_panel_id in active_panel_ids and current_panel_id == panel_id
            current_host.setVisible(should_show)
            if should_show:
                current_host.show()
            else:
                current_host.hide()
        self._update_side_panel_host_states(active_panel_ids, emphasized_panel_id=panel_id)
        self._update_side_panel_switcher_state(active_panel_ids)

    def _update_side_panel_host_states(
        self,
        active_panel_ids: List[str],
        *,
        emphasized_panel_id: str | None = None,
        show_headers: bool = False,
    ) -> None:
        """Update host chrome to match the current right-panel arrangement."""
        for panel_id, host in self._side_panel_hosts.items():
            host.setProperty("activeView", "true" if panel_id == emphasized_panel_id else "false")
            header = getattr(host, "_header", None)
            if header is not None:
                header.setVisible(show_headers and panel_id in active_panel_ids)
            host.style().unpolish(host)
            host.style().polish(host)

        self._update_side_panel_switcher_state(active_panel_ids)

    def _create_side_panel_status_bar(self):
        """Create the compact footer for the inspector shell."""
        bar = QFrame()
        bar.setObjectName("sidePanelStatusBar")
        bar.setFixedHeight(30)
        bar.setStyleSheet(f"""
            QFrame#sidePanelStatusBar {{
                background: transparent;
                border: none;
            }}
            QFrame#sidePanelSummaryGroup,
            QFrame#sidePanelControlsGroup {{
                background-color: {CHROME.surface_alt};
                border: 1px solid {CHROME.border};
                border-radius: 9px;
            }}
            QFrame#sidePanelGroupDivider {{
                background-color: {CHROME.border};
                min-width: 1px;
                max-width: 1px;
                min-height: 12px;
                margin: 5px 2px;
            }}
            QLabel#sidePanelCountChip {{
                background-color: {CHROME.surface_raised};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.border_strong};
                border-radius: 7px;
                padding: 2px 7px;
                font-size: 9px;
                font-weight: 700;
            }}
            QLabel#sidePanelSummaryChip,
            QLabel#sidePanelModeChip {{
                background: transparent;
                color: {CHROME.text_secondary};
                border: none;
                padding: 0 6px;
                font-size: 9px;
                font-weight: 600;
            }}
            QLabel#sidePanelModeChip {{
                color: {CHROME.text_primary};
                font-weight: 700;
                padding-right: 8px;
            }}
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        summary_group, summary_layout = self._create_status_cluster("sidePanelSummaryGroup")
        summary_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._right_panel_count_label = QLabel("")
        self._right_panel_count_label.setObjectName("sidePanelCountChip")
        summary_layout.addWidget(self._right_panel_count_label)
        self._add_status_cluster_divider(summary_layout, "sidePanelGroupDivider")

        self._right_panel_status_label = QLabel("")
        self._right_panel_status_label.setObjectName("sidePanelSummaryChip")
        self._right_panel_status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        summary_layout.addWidget(self._right_panel_status_label, 1)
        layout.addWidget(summary_group, 1, Qt.AlignmentFlag.AlignVCenter)

        controls_group, controls_layout = self._create_status_cluster("sidePanelControlsGroup")
        self._right_panel_mode_label = QLabel("")
        self._right_panel_mode_label.setObjectName("sidePanelModeChip")
        controls_layout.addWidget(self._right_panel_mode_label)
        layout.addWidget(controls_group, 0, Qt.AlignmentFlag.AlignVCenter)

        bar.setLayout(layout)
        bar.hide()
        return bar

    def _get_panel_label(self, panel_id: str) -> str:
        """Return the user-facing label for a side panel."""
        return {
            "data": tr("panel_data_tab"),
            "structure": tr("panel_structure_tab"),
            "info": tr("panel_info_tab"),
            "ai": tr("panel_ai_tab"),
        }.get(panel_id, panel_id.title())

    def _get_panel_tab_label(self, panel_id: str) -> str:
        """Return the compact label used in the right-side tab switcher."""
        return {
            "data": tr("panel_data_tab_short"),
            "structure": tr("panel_structure_tab_short"),
            "info": tr("panel_info_tab_short"),
            "ai": tr("panel_ai_tab_short"),
        }.get(panel_id, self._get_panel_label(panel_id))

    def _get_active_panel_ids(self) -> List[str]:
        """Return visible inspector panels hosted inside the right column."""
        active_panel_ids: list[str] = []
        if self._panel_visibility["value"]:
            active_panel_ids.append("data")
        if self._panel_visibility["structure"]:
            active_panel_ids.append("structure")
        return active_panel_ids

    def _current_right_panel_content_width(self) -> int:
        """Return the best-known width for the inspector content area."""
        if hasattr(self, "_right_panel_content") and self._right_panel_content.width() > 0:
            return self._right_panel_content.width()
        if hasattr(self, "_right_panel") and self._right_panel.width() > 0:
            return self._right_panel.width()
        if self._splitter is not None:
            sizes = self._splitter.sizes()
            if len(sizes) > 3 and sizes[3] > 0:
                return sizes[3]
        return max(self._right_panel_width, 0)

    def _resolved_side_panel_layout(self, active_panel_ids: List[str]) -> tuple[str, List[str]]:
        """Resolve the top-level inspector arrangement."""
        ordered_ids = list(active_panel_ids)
        if len(ordered_ids) <= 1:
            return "single", ordered_ids
        return "tabs", ordered_ids

    def _clear_splitter(self, splitter: QSplitter) -> None:
        """Remove all child widgets from a splitter."""
        while splitter.count():
            widget = splitter.widget(0)
            if widget is None:
                break
            widget.setParent(None)

    def _clear_layout(self, layout):
        """Detach all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _panel_host_minimum_width(self, panel_id: str, panel_count: int) -> int:
        """Return a readability-focused minimum width for horizontal panel rows."""
        if panel_id == "ai":
            return 300
        if panel_id == "info":
            return 320 if panel_count > 1 else 260
        return 300 if panel_count > 1 else 260

    def _update_right_panel_minimum_width(
        self,
        active_panel_ids: List[str],
        resolved_layout: str,
    ) -> None:
        """Keep the inspector shell wide enough to avoid unreadable micro-panels."""
        right_panel = getattr(self, "_right_panel", None)
        if right_panel is None:
            return
        minimum_width = 228
        if resolved_layout == "tabs":
            minimum_width = 292
        right_panel.setMinimumWidth(minimum_width)

    def _detach_side_panel_widgets(self):
        """Remove side panels from any temporary container before rebuilding."""
        self._clear_splitter(self._panel_horizontal_splitter)

    def _activate_side_panel_widgets(self, panel_ids: List[str]):
        """Refresh geometry for hosted inspector pages before selecting one."""
        for current_panel_id, widget in self._side_panel_hosts.items():
            widget.setVisible(current_panel_id in panel_ids)
            widget.updateGeometry()

    def _sync_tab_panel_visibility(self):
        """Legacy no-op kept for callers that previously used tabbed shell layouts."""
        return

    def _ensure_right_panel_width(self, minimum_width: int):
        """Expand the right panel when the active layout needs more space."""
        right_panel = getattr(self, "_right_panel", None)
        if self._splitter is None or right_panel is None or not self._is_side_panel_visible(right_panel, 3):
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= 3 or sizes[3] >= minimum_width:
            return

        delta = minimum_width - sizes[3]
        if delta <= 0:
            return

        grow = min(delta, max(0, sizes[1] - 200))
        if grow <= 0:
            return

        sizes[3] += grow
        sizes[1] -= grow
        self._right_panel_width = sizes[3]
        self._right_panel_horizontal_width = sizes[3]
        self._splitter.setSizes(sizes)

    def _capture_right_panel_width(self):
        """Remember the current right panel width for the active layout family."""
        if self._splitter is None or not self._is_side_panel_visible(self._right_panel, 3):
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= 3 or sizes[3] <= 0:
            return

        current_width = sizes[3]
        self._right_panel_width = current_width
        resolved_layout, _ = self._resolved_side_panel_layout(self._get_active_panel_ids())
        if resolved_layout == "horizontal":
            self._right_panel_horizontal_width = current_width
        else:
            self._right_panel_standard_width = current_width

    def _set_right_panel_width(self, target_width: int):
        """Resize the right splitter pane to a target width when possible."""
        if self._splitter is None or not self._is_side_panel_visible(self._right_panel, 3):
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= 3:
            return

        available = sizes[1] + sizes[3]
        max_target = max(160, available - 200)
        clamped_target = max(160, min(target_width, max_target))
        if clamped_target == sizes[3]:
            self._right_panel_width = clamped_target
            return

        sizes[3] = clamped_target
        sizes[1] = available - clamped_target
        self._right_panel_width = clamped_target
        self._splitter.setSizes(sizes)

    def _apply_right_panel_width_for_layout(self):
        """Restore the expected right panel width for the current side panel layout."""
        active_panel_ids = self._get_active_panel_ids()
        if not active_panel_ids:
            return

        resolved_layout, _ = self._resolved_side_panel_layout(active_panel_ids)
        if len(active_panel_ids) > 1 and resolved_layout == "horizontal":
            target_width = max(self._right_panel_horizontal_width, 620)
        else:
            target_width = self._right_panel_standard_width

        self._set_right_panel_width(target_width)

    def _schedule_right_panel_width_restore(self):
        """Apply right panel width after Qt finishes processing pending layout changes."""
        QTimer.singleShot(0, self._apply_right_panel_width_for_layout_safe)

    def _apply_right_panel_width_for_layout_safe(self) -> None:
        """Safely restore panel width when deferred callbacks outlive transient widgets."""
        try:
            self._apply_right_panel_width_for_layout()
        except RuntimeError:
            return

    def _apply_splitter_sizes_safe(self, splitter: QSplitter, sizes: List[int]) -> None:
        """Apply splitter ratios while tolerating widgets destroyed during teardown."""
        try:
            splitter.setSizes(list(sizes))
        except RuntimeError:
            return

    def _schedule_splitter_sizes(self, splitter: QSplitter, sizes: List[int]) -> None:
        """Queue a splitter resize after Qt finishes the current layout pass."""
        planned_sizes = list(sizes)
        QTimer.singleShot(
            0,
            lambda target_splitter=splitter, target_sizes=planned_sizes: self._apply_splitter_sizes_safe(
                target_splitter,
                target_sizes,
            ),
        )

    def _refresh_side_panel_layout_safe(self) -> None:
        """Safely rebuild inspector layout from deferred resize callbacks."""
        try:
            self._refresh_side_panel_layout()
        except RuntimeError:
            return

    def _refresh_side_panel_layout(self):
        """Rebuild the right-side panel area based on visibility and layout state."""
        active_panel_ids = self._get_active_panel_ids()
        if self._active_panel_id not in active_panel_ids:
            self._active_panel_id = active_panel_ids[0] if active_panel_ids else "data"

        resolved_layout, ordered_panel_ids = self._resolved_side_panel_layout(active_panel_ids)
        self._resolved_side_panel_signature = (
            resolved_layout,
            tuple(ordered_panel_ids),
        )

        self._rebuild_side_panel_switcher(active_panel_ids)
        self._update_right_panel_minimum_width(active_panel_ids, resolved_layout)

        if not active_panel_ids:
            self._right_panel_content.setVisible(False)
            self._update_side_panel_host_states(active_panel_ids)
            self._update_side_panel_status_bar(active_panel_ids)
            return

        self._right_panel_content.setVisible(True)
        self._right_panel_content.show()
        self._activate_side_panel_widgets(ordered_panel_ids)
        self._show_active_side_panel(self._active_panel_id, active_panel_ids)
        right_panel = getattr(self, "_right_panel", None)
        if right_panel is not None:
            right_panel.updateGeometry()
        self._update_side_panel_status_bar(active_panel_ids)

    def _update_side_panel_status_bar(self, active_panel_ids: List[str]):
        """Hide the legacy right footer so the tabbed inspector stays visually quiet."""
        self._right_panel_status_bar.hide()

    def _update_panel_layout_button(self):
        """Legacy no-op kept while the footer no longer owns layout toggles."""
        return

    def _create_panel_layout_icon(self, mode: str) -> QIcon:
        """Create a unified linear icon for side-panel layout actions."""
        icon = QIcon()
        states = (
            (QIcon.Mode.Normal, QIcon.State.Off, QColor(CHROME.text_secondary)),
            (QIcon.Mode.Active, QIcon.State.Off, QColor(CHROME.text_primary)),
            (QIcon.Mode.Selected, QIcon.State.Off, QColor(CHROME.text_primary)),
            (QIcon.Mode.Disabled, QIcon.State.Off, QColor(CHROME.text_muted)),
            (QIcon.Mode.Normal, QIcon.State.On, QColor(CHROME.text_primary)),
            (QIcon.Mode.Active, QIcon.State.On, QColor(CHROME.text_primary)),
            (QIcon.Mode.Selected, QIcon.State.On, QColor(CHROME.text_primary)),
        )
        for icon_mode, state, color in states:
            icon.addPixmap(self._create_panel_layout_icon_pixmap(mode, color), icon_mode, state)
        return icon

    def _create_panel_layout_icon_pixmap(self, mode: str, color: QColor) -> QPixmap:
        """Paint one state of a side-panel layout icon."""
        size = QSize(14, 14)
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color)
        pen.setWidthF(1.15)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        if mode == "adaptive":
            painter.drawRoundedRect(2, 2, 10, 10, 2, 2)
            painter.drawLine(7, 4, 7, 10)
            painter.drawLine(9, 7, 10, 7)
        elif mode == "vertical":
            painter.drawRoundedRect(2, 2, 10, 10, 2, 2)
            painter.drawLine(4, 7, 10, 7)
        elif mode == "horizontal":
            painter.drawRoundedRect(2, 2, 10, 10, 2, 2)
            painter.drawLine(7, 4, 7, 10)
        else:
            painter.drawRoundedRect(2, 4, 10, 6, 2, 2)
            painter.drawLine(4, 7, 10, 7)
            painter.drawLine(4, 2, 6, 2)
            painter.drawLine(8, 2, 10, 2)

        painter.end()
        return pixmap

    def _sync_right_panel_visibility(self):
        """Show or hide the right panel based on active side panels."""
        self._set_side_panel_visibility(
            self._right_panel,
            3,
            bool(self._get_active_panel_ids()),
            "_right_panel_width",
            240,
        )

    def _sync_ai_panel_visibility(self):
        """Show or hide the AI column beside the editor."""
        self._set_side_panel_visibility(
            self._ai_panel_shell,
            2,
            self._panel_visibility["ai"],
            "_ai_panel_width",
            max(280, CHROME.right_panel_width),
        )

    def is_right_panel_visible(self) -> bool:
        """Return whether the right-side splitter panel is currently visible."""
        if self._splitter is None:
            return not self._right_panel.isHidden()

        sizes = self._splitter.sizes()
        if len(sizes) <= 3:
            return not self._right_panel.isHidden()

        return not self._right_panel.isHidden() and sizes[3] > 0

    def _emit_side_panel_state_changed(self):
        """Notify outer UI that side panel state changed."""
        self.side_panel_state_changed.emit(
            self._panel_visibility["ai"],
            self._panel_visibility["value"],
            self._panel_visibility["structure"],
            self._panel_layout_mode,
        )

    def is_ai_panel_visible(self) -> bool:
        """Return whether the AI workspace column is enabled."""
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
        """Legacy setter kept for compatibility with older tests and settings."""
        if self._panel_layout_mode == "horizontal":
            return

        self._panel_layout_mode = "horizontal"
        self._update_side_panel_status_bar(self._get_active_panel_ids())
        self._save_side_panel_settings()
        self._emit_side_panel_state_changed()

    def _on_side_panel_tab_changed(self, index: int):
        """Legacy no-op kept after removing top-level tabbed shell layouts."""
        return

    def eventFilter(self, watched, event):
        """Track splitter width changes for the inspector shell."""
        if watched is getattr(self, "_right_panel", None) and event.type() == QEvent.Type.Resize:
            self._capture_right_panel_width()
        elif (
            watched is getattr(self, "_ai_panel_shell", None)
            and event.type() == QEvent.Type.Resize
            and self._is_side_panel_visible(self._ai_panel_shell, 2)
        ):
            self._ai_panel_width = max(self._ai_panel_shell.width(), 160)
        return super().eventFilter(watched, event)

    def _set_side_panel_visibility(self, panel: QWidget, index: int, visible: bool,
                                   size_attr: str, default_size: int):
        """Show or hide a splitter side panel while preserving its width."""
        if self._splitter is None:
            return

        sizes = self._splitter.sizes()
        if len(sizes) <= index:
            return

        current_visible = (not panel.isHidden()) and sizes[index] > 0
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
            return not panel.isHidden()

        sizes = self._splitter.sizes()
        if len(sizes) <= index:
            return not panel.isHidden()

        return (not panel.isHidden()) and sizes[index] > 0

    def _create_data_value_panel(self):
        """Create data value inspection panel."""
        return DataValuePanel(self)

    def _create_structure_panel(self):
        """Create structure parsing panel."""
        return StructureViewPanel(self)

    def _create_ai_workspace_panel(self):
        """Create the AI column that lives beside the editor workspace."""
        shell = QWidget()
        shell.setObjectName("editorAIPanelShell")
        shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shell.setMinimumWidth(260)
        shell.installEventFilter(self)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._ai_panel)
        return shell

    def _create_ai_panel(self):
        """Create AI analysis panel."""
        self._ai_panel_widget = AIAgentPanel(self, self._ai_manager, self._agent_bridge)
        self._ai_panel_widget.open_settings_requested.connect(self.show_ai_settings)
        return self._ai_panel_widget

    def _connect_signals(self):
        """Connect signals."""
        self._document_model.document_changed.connect(self._on_document_changed)
        self._document_model.document_modified.connect(self._on_document_modified)

    def shutdown(self) -> None:
        """Tear down background UI helpers before the window is destroyed."""
        if hasattr(self, "_ai_panel_widget"):
            self._ai_panel_widget.shutdown()

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
            self._pos_label.setText("0x00000000")
            self._selection_label.setText("0 B")
            self._size_label.setText("0 B")
            self._update_document_status_summary(None)
            self._sync_file_browser_active_file(None)
            self._reset_value_panel()
            self._reset_structure_panel()
            self._sync_current_view_bytes_per_row()
            return

        self._sync_file_browser_active_file(doc)
        self._update_document_status_summary(doc)
        self._size_label.setText(FormatUtils.format_size(doc.file_size))
        offset = hex_view.get_offset_at_cursor()
        self._on_cursor_moved(offset)
        self._sync_current_view_bytes_per_row()

    def _on_cursor_moved(self, offset: int):
        """Update side UI from the active cursor position."""
        self._pos_label.setText(f"0x{max(0, offset):08X}")
        self._update_value_panel(offset)
        self._update_structure_panel(offset)
        self.cursor_changed.emit(offset)

    def _on_selection_changed(self, start: int, end: int):
        """Update the status bar selection size."""
        length = end - start + 1 if start >= 0 and end >= start else 0
        self._selection_label.setText(f"{length} B")

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
        if isinstance(path, bool):
            path = None
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
        normalized_path = os.path.abspath(path)
        doc = self._document_model.open_document(normalized_path)
        if doc:
            _index, created = self._add_editor_tab(doc)

            if created:
                bytes_per_row = self._get_file_bytes_per_row(doc.file_path or normalized_path)
                current_widget = self._tab_widget.currentWidget()
                if hasattr(current_widget, 'hex_view'):
                    current_widget.hex_view.set_bytes_per_row(bytes_per_row)
            self._sync_current_view_bytes_per_row()

            self.file_opened.emit(doc.file_path or normalized_path)

    def _on_file_open_request(self, path: str):
        """Handle file open request from file browser."""
        if os.path.isfile(path):
            self._open_file(path)

    def open_folder(self, path=None):
        """Open folder in file tree."""
        from PyQt6.QtWidgets import QFileDialog
        if isinstance(path, bool):
            path = None
        if path is None:
            path = QFileDialog.getExistingDirectory(
                self,
                "Open Folder",
                ""
            )
        if path:
            if not self._is_side_panel_visible(self._file_browser, 0):
                self._set_side_panel_visibility(
                    self._file_browser,
                    0,
                    True,
                    "_file_tree_width",
                    CHROME.sidebar_width,
                )
            self._file_browser.set_root_path(path)
            self._sync_file_browser_active_file(self._document_model.current_document)

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
                    self._sync_file_browser_active_file(doc)
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
        from .dialogs.chrome import create_dialog_header

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
            layout.setContentsMargins(18, 18, 18, 18)
            layout.setSpacing(14)

            layout.addWidget(
                create_dialog_header(
                    "头长度参数设置",
                    "配置头长度模式使用的字节数，并保持与其他设置弹窗一致的层次和配色。",
                )
            )

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
        main_window = self.window()
        current_hex_view = self._get_current_hex_view()
        file_size = 0
        start_offset = 0
        if current_hex_view is not None:
            model = current_hex_view._model
            file_size = max(0, int(getattr(model, "_file_size", 0)))
            if hasattr(current_hex_view, "get_start_offset"):
                start_offset = current_hex_view.get_start_offset()
            else:
                start_offset = max(0, int(getattr(model, "_start_offset", 0)))

        if mode == "equal_frame":
            length_value = self._data_model.bytes_per_frame
            length_range = (1, 65535)
            self._arrangement_label.setText(
                self._format_arrangement_status("equal_frame", self._data_model.bytes_per_frame)
            )
        else:
            header_len = param_value if param_value is not None else self._data_model.header_length
            length_value = header_len
            length_range = (1, 8)
            self._arrangement_label.setText(self._format_arrangement_status("header_length", header_len))

        if hasattr(main_window, "_sync_arrangement_toolbar"):
            main_window._sync_arrangement_toolbar(
                mode=ArrangementMode.HEADER_LENGTH if mode == "header_length" else ArrangementMode.EQUAL_FRAME,
                length_value=length_value,
                length_range=length_range,
                start_offset=start_offset,
                max_start_offset=max(0, file_size - 1),
            )

    def set_arrangement_length(self, length: int):
        """Set bytes per frame for equal frame mode."""
        self._data_model.bytes_per_frame = length
        # Update hex view
        current_widget = self._tab_widget.currentWidget()
        if hasattr(current_widget, 'hex_view'):
            current_widget.hex_view.set_bytes_per_row(length)
        self._update_toolbar_for_mode("equal_frame", length)
        # Update status bar
        self._arrangement_label.setText(self._format_arrangement_status("equal_frame", length))

    def set_header_length(self, length: int):
        """Set header length for header length mode."""
        self._data_model.header_length = length
        # Update hex view
        self._update_hex_views()
        self._update_toolbar_for_mode("header_length", length)
        # Update status bar
        self._arrangement_label.setText(self._format_arrangement_status("header_length", length))

    def set_arrangement_start_offset(self, offset: int):
        """Set the starting offset used for display and arrangement."""
        current_hex_view = self._get_current_hex_view()
        if current_hex_view is None or not hasattr(current_hex_view, "set_start_offset"):
            return

        current_hex_view.set_start_offset(offset)
        current_mode = getattr(current_hex_view._model, "_arrangement_mode", "equal_frame")
        param_value = (
            getattr(current_hex_view._model, "_header_length", self._data_model.header_length)
            if current_mode == "header_length"
            else getattr(current_hex_view._model, "_bytes_per_row", self._data_model.bytes_per_frame)
        )
        self._update_toolbar_for_mode(current_mode, param_value)
        self._refresh_current_view_state()

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
        from .dialogs.chrome import create_dialog_header
        dialog = QDialog(self)
        dialog.setWindowTitle("Arrangement Settings")
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            create_dialog_header(
                "Arrangement Settings",
                "统一配置每行字节数与头长度参数，避免隐藏在旧式临时对话框里的视觉断层。",
            )
        )

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
            CHROME.sidebar_width,
        )

    def toggle_ai_panel(self):
        """Toggle the AI workspace column from the View menu."""
        self.set_ai_panel_visible(not self.is_ai_panel_visible())

    def focus_ai_panel(self):
        """Ensure the AI workspace column is visible and focus its composer."""
        if not self.is_ai_panel_visible():
            self.set_ai_panel_visible(True)

        self._sync_ai_panel_visibility()

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
        """Enable or disable the AI workspace column."""
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
        panel_host_id = {
            "value": "data",
            "structure": "structure",
        }.get(panel_id)
        if panel_host_id is not None and visible:
            self._active_panel_id = panel_host_id
        elif self._active_panel_id not in active_panel_ids:
            self._active_panel_id = active_panel_ids[0] if active_panel_ids else "data"

        self._refresh_side_panel_layout()
        self._sync_ai_panel_visibility()
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
            if not settings.get("enabled", True):
                self.set_ai_panel_visible(False)
            if hasattr(self, "_ai_panel_widget"):
                self._ai_panel_widget.refresh_provider_status()

    # Tab management
    def _find_tab_index_for_document(self, doc: FileHandle) -> int:
        """Return the first editor tab index for a document, if present."""
        for index in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(index)
            if isinstance(widget, HexEditorTabWidget) and widget.document == doc:
                return index
        return -1

    def _sync_current_view_bytes_per_row(self) -> None:
        """Keep toolbar and status state aligned with the active editor's arrangement."""
        current_widget = self._tab_widget.currentWidget()
        if not hasattr(current_widget, 'hex_view'):
            main_window = self.window()
            if hasattr(main_window, "_sync_arrangement_toolbar"):
                mode = self._data_model.arrangement_mode
                main_window._sync_arrangement_toolbar(
                    mode=mode,
                    length_value=self._data_model.header_length if mode == ArrangementMode.HEADER_LENGTH else self._data_model.bytes_per_frame,
                    length_range=(1, 8) if mode == ArrangementMode.HEADER_LENGTH else (1, 65535),
                    start_offset=0,
                    max_start_offset=0,
                )
            return

        model = current_widget.hex_view._model
        arrangement_mode = getattr(model, "_arrangement_mode", "equal_frame")
        if arrangement_mode == "header_length":
            header_length = getattr(model, "_header_length", None)
            self._data_model.arrangement_mode = ArrangementMode.HEADER_LENGTH
            if isinstance(header_length, int) and header_length > 0:
                self._data_model.header_length = header_length
                self._update_toolbar_for_mode("header_length", header_length)
        else:
            bytes_per_row = getattr(model, "_bytes_per_row", None)
            self._data_model.arrangement_mode = ArrangementMode.EQUAL_FRAME
            if isinstance(bytes_per_row, int) and bytes_per_row > 0:
                self._data_model.bytes_per_frame = bytes_per_row
                self._update_toolbar_for_mode("equal_frame", bytes_per_row)

    def _add_editor_tab(self, doc: FileHandle):
        """Add editor tab for document."""
        existing_index = self._find_tab_index_for_document(doc)
        if existing_index >= 0:
            self._tab_widget.setCurrentIndex(existing_index)
            self._update_tab_name(existing_index, doc)
            self._refresh_current_view_state()
            self._sync_current_view_bytes_per_row()

            current_widget = self._tab_widget.currentWidget()
            if hasattr(current_widget, 'hex_view'):
                current_widget.hex_view.setFocus()

            return existing_index, False

        # Create hex view widget
        hex_view_widget = HexEditorTabWidget(doc, self)
        index = self._tab_widget.addTab(hex_view_widget, doc.file_name)
        self._tab_widget.setCurrentIndex(index)
        self._update_tab_name(index, doc)
        self._refresh_tab_close_buttons()
        self._update_center_empty_state()

        # Connect hex view signals for status bar updates
        hex_view = hex_view_widget.hex_view
        self._connect_hex_view_signals(hex_view)
        hex_view_widget.data_changed.connect(self._refresh_current_view_state)
        self._refresh_current_view_state()
        self._sync_current_view_bytes_per_row()

        return index, True

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
            self._arrangement_label.setText(
                self._format_arrangement_status("equal_frame", self._data_model.bytes_per_frame)
            )
        elif arrangement_mode == ArrangementMode.HEADER_LENGTH:
            self._arrangement_label.setText(
                self._format_arrangement_status("header_length", self._data_model.header_length)
            )
        else:
            self._arrangement_label.setText(
                self._format_arrangement_status("custom", self._data_model.bytes_per_frame)
            )

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
        if index < 0:
            return

        widget = self._tab_widget.widget(index)
        doc = widget.document if isinstance(widget, HexEditorTabWidget) else None

        # Get document before closing to save its settings
        if doc and doc.file_path:
            # Save bytes_per_row setting for this file
            if hasattr(widget, 'hex_view'):
                bytes_per_row = widget.hex_view._model._bytes_per_row
                self._set_file_bytes_per_row(doc.file_path, bytes_per_row)

        if self._document_model.close_document_handle(doc):
            self._tab_widget.removeTab(index)
            self._refresh_tab_close_buttons()
            self._update_center_empty_state()
            self._sync_current_view_bytes_per_row()

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        if index >= 0:
            widget = self._tab_widget.widget(index)
            if isinstance(widget, HexEditorTabWidget):
                self._document_model.set_current_document(widget.document)
        self._selection_label.setText("0 B")
        self._update_center_empty_state()
        self._refresh_current_view_state()
        self._sync_current_view_bytes_per_row()

    def _on_document_changed(self, doc: FileHandle):
        """Handle document change."""
        if doc:
            self._size_label.setText(FormatUtils.format_size(doc.file_size))
        else:
            self._size_label.setText("0 B")
        self._sync_file_browser_active_file(doc)
        self._update_document_status_summary(doc)
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
        self._sync_file_browser_active_file(self._document_model.current_document)
        self._update_document_status_summary(doc)

    def _sync_file_browser_active_file(self, doc: FileHandle | None) -> None:
        """Mirror the current document into the explorer's active-file marker."""
        path = doc.file_path if doc and getattr(doc, "file_path", None) else None
        self._file_browser.set_active_file(path)


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
