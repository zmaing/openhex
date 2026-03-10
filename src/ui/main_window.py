"""
HexEditor Main Window

Main hex editor widget with panels and views.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                             QTabWidget, QLabel, QProgressBar, QFrame, QPushButton,
                             QStackedWidget, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from typing import List
from PyQt6.QtGui import QFont

import os
import hashlib

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


class HexEditorMainWindow(QWidget):
    """
    Main hex editor widget.

    Contains the hex view, file tree, and various panels.
    """

    # Signals
    file_opened = pyqtSignal(str)
    file_saved = pyqtSignal(str)
    cursor_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._document_model = DocumentModel()
        self._data_model = DataModel()
        self._ascii_visible = True
        self._undo_stack = UndoStack()
        self._splitter = None
        self._file_tree_width = 250
        self._right_panel_width = 280

        # AI Manager
        self._ai_manager = AIManager(self)

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
        self._load_ai_settings()

        logger.info("HexEditorMainWindow initialized")

    def _load_ai_settings(self):
        """Load AI settings from app settings."""
        app = self.window()
        if hasattr(app, 'settings'):
            s = app.settings()
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
            self._ai_manager.configure(settings)
            self._ai_status.setText(f"Provider: {settings.get('provider', 'local').title()}")

    def _get_file_settings_key(self, file_path: str) -> str:
        """Generate a unique key for file settings based on absolute path."""
        # Use MD5 hash of absolute path for unique identification
        abs_path = os.path.abspath(file_path)
        path_hash = hashlib.md5(abs_path.encode()).hexdigest()[:16]
        return f"file_layout/{path_hash}"

    def _get_file_bytes_per_row(self, file_path: str) -> int:
        """Load bytes_per_row setting for a file from QSettings."""
        app = self.window()
        if hasattr(app, 'settings'):
            s = app.settings()
            key = self._get_file_settings_key(file_path)
            return s.value(key, 32, type=int)
        return 32

    def _set_file_bytes_per_row(self, file_path: str, bytes_per_row: int):
        """Save bytes_per_row setting for a file to QSettings."""
        app = self.window()
        if hasattr(app, 'settings'):
            s = app.settings()
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
        # Clear after 3 seconds
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._msg_label.setText(""))

    def _create_right_panel(self):
        """Create right side info panel."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Tabs for right panel
        self._panel_tabs = QTabWidget()
        self._panel_tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: #252526;
                border: none;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 6px 12px;
            }
            QTabBar::tab:selected {
                background-color: #252526;
                color: #ffffff;
            }
        """)

        # Data Value tab
        self._data_value = self._create_data_value_panel()
        self._panel_tabs.addTab(self._data_value, "Value")

        # AI Panel
        self._ai_panel = self._create_ai_panel()
        self._panel_tabs.addTab(self._ai_panel, "AI")

        layout.addWidget(self._panel_tabs)
        widget.setLayout(layout)
        widget.setMaximumWidth(320)

        return widget

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
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Data Inspector")
        title.setStyleSheet("font-weight: bold; color: #cccccc;")
        layout.addWidget(title)

        # Offset display
        self._value_offset = QLabel("0x00000000")
        self._value_offset.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Offset:"))
        layout.addWidget(self._value_offset)

        # Hex value
        self._value_hex = QLabel("00")
        self._value_hex.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Hex:"))
        layout.addWidget(self._value_hex)

        # Decimal values
        self._value_dec_signed = QLabel("0")
        self._value_dec_signed.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Signed:"))
        layout.addWidget(self._value_dec_signed)

        self._value_dec_unsigned = QLabel("0")
        self._value_dec_unsigned.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Unsigned:"))
        layout.addWidget(self._value_dec_unsigned)

        # Binary
        self._value_bin = QLabel("00000000")
        self._value_bin.setFont(QFont("Monospace", 10))
        layout.addWidget(QLabel("Binary:"))
        layout.addWidget(self._value_bin)

        # ASCII
        self._value_ascii = QLabel(".")
        self._value_ascii.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("ASCII:"))
        layout.addWidget(self._value_ascii)

        # Octal
        self._value_octal = QLabel("0o00")
        self._value_octal.setFont(QFont("Monospace", 11))
        layout.addWidget(QLabel("Octal:"))
        layout.addWidget(self._value_octal)

        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def _create_ai_panel(self):
        """Create AI analysis panel."""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("AI Assistant")
        title.setStyleSheet("font-weight: bold; color: #cccccc;")
        layout.addWidget(title)

        # Status
        self._ai_status = QLabel("Not configured")
        self._ai_status.setStyleSheet("color: #858585;")
        layout.addWidget(self._ai_status)

        # Buttons
        btn_style = """
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: none;
                padding: 8px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #4c4c4c;
            }
        """

        analyze_btn = QPushButton("Analyze Data")
        analyze_btn.setStyleSheet(btn_style)
        analyze_btn.clicked.connect(self.analyze_selection)
        layout.addWidget(analyze_btn)

        detect_btn = QPushButton("Detect Patterns")
        detect_btn.setStyleSheet(btn_style)
        detect_btn.clicked.connect(self.detect_patterns)
        layout.addWidget(detect_btn)

        gen_code_btn = QPushButton("Generate Code")
        gen_code_btn.setStyleSheet(btn_style)
        gen_code_btn.clicked.connect(self.generate_parsing_code)
        layout.addWidget(gen_code_btn)

        # AI output
        self._ai_output = QTextEdit()
        self._ai_output.setReadOnly(True)
        self._ai_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                font-family: 'Menlo', 'Consolas', monospace;
                font-size: 10px;
            }
        """)
        layout.addWidget(self._ai_output)

        layout.addStretch()
        panel.setLayout(layout)
        return panel

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

        if doc.file_state.name == "NEW":
            # New file needs Save As
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
        import os
        log_path = "/Users/zhanghaoli/Documents/WorkFile/Code/myhxd/hex_forge/logs/debug.log"

        with open(log_path, "a") as f:
            f.write(f"[MAIN] _on_find_next: pattern='{pattern}', mode='{mode}', type={type(mode)}\n")
            f.write(f"[MAIN] last: pattern='{self._last_search_pattern}', mode={self._last_search_mode}\n")

        doc = self._document_model.current_document
        if not doc:
            with open(log_path, "a") as f:
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
        import os
        log_path = "/Users/zhanghaoli/Documents/WorkFile/Code/myhxd/hex_forge/logs/debug.log"

        if 0 <= index < len(self._search_results):
            result = self._search_results[index]
            self._current_result_index = index
            with open(log_path, "a") as f:
                f.write(f"[INFO] _go_to_result: offset={result.offset}, index={index}/{len(self._search_results)}\n")

            # Scroll to offset
            current_widget = self._tab_widget.currentWidget()
            with open(log_path, "a") as f:
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
        """Toggle AI panel visibility."""
        self._set_side_panel_visibility(
            self._right_panel,
            2,
            not self._is_side_panel_visible(self._right_panel, 2),
            "_right_panel_width",
            280,
        )

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
        self._ai_output.setPlainText("File compare not yet implemented")

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
            self._ai_output.setPlainText("No file open")
            return

        # Get first 4KB of data for analysis
        data = doc.read(0, min(doc.file_size, 4096))

        self._ai_output.setPlainText("Analyzing data...")
        result = self._ai_manager.analyze(data, "Analyze this binary data and explain its structure")
        self._ai_output.setPlainText(result)

    def detect_patterns(self):
        """Detect data patterns with AI."""
        doc = self._document_model.current_document
        if not doc:
            self._ai_output.setPlainText("No file open")
            return

        # Use built-in pattern detection
        from ..core.parser.auto import AutoParser
        data = doc.read(0, min(doc.file_size, 4096))
        parser = AutoParser()
        patterns = parser.analyze(data)

        result = f"Found {len(patterns)} pattern(s):\n\n"
        for p in patterns[:10]:
            result += f"- {p.pattern_type.name}: {p.description}\n"

        self._ai_output.setPlainText(result)

    def generate_parsing_code(self):
        """Generate parsing code."""
        doc = self._document_model.current_document
        if not doc:
            self._ai_output.setPlainText("No file open")
            return

        # Get data for structure analysis
        data = doc.read(0, min(doc.file_size, 4096))

        # Use built-in structure detection first
        from ..core.parser.auto import AutoParser
        parser = AutoParser()
        patterns = parser.analyze(data)

        # Build structure description
        structure = {"patterns": []}
        for p in patterns[:5]:
            structure["patterns"].append({
                "type": p.pattern_type.name,
                "offset": p.offset,
                "length": p.length,
                "description": p.description
            })

        self._ai_output.setPlainText("Generating parsing code...")

        # Generate C code for the structure
        result = self._ai_manager.generate_code(structure, "c")
        self._ai_output.setPlainText(result)

    def show_ai_settings(self):
        """Show AI settings dialog."""
        from .dialogs.ai_settings import AISettingsDialog

        # Get current settings
        current_settings = {}
        app = self.window()
        if hasattr(app, '_ai_settings'):
            current_settings = app._ai_settings

        dialog = AISettingsDialog(self, current_settings)
        if dialog.exec():
            settings = dialog.get_settings()
            # Save settings
            if hasattr(app, '_ai_settings'):
                app._ai_settings = settings
            # Save to persistent storage
            if hasattr(app, 'settings'):
                s = app.settings()
                s.setValue('ai_enabled', settings.get('enabled', True))
                s.setValue('ai_provider', settings.get('provider', 'local'))
                s.setValue('ai_local_endpoint', settings.get('local', {}).get('endpoint', ''))
                s.setValue('ai_local_model', settings.get('local', {}).get('model', ''))
                s.setValue('ai_cloud_provider', settings.get('cloud', {}).get('provider', ''))
                s.setValue('ai_cloud_api_key', settings.get('cloud', {}).get('api_key', ''))
                s.setValue('ai_cloud_base_url', settings.get('cloud', {}).get('base_url', ''))
                s.setValue('ai_cloud_model', settings.get('cloud', {}).get('model', ''))

            self._ai_status.setText(f"Provider: {settings.get('provider', 'local').title()}")

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
        if hasattr(hex_view, 'edit_mode_changed'):
            hex_view.edit_mode_changed.connect(self._update_edit_mode_display)

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

    def _on_document_changed(self, doc: FileHandle):
        """Handle document change."""
        if doc:
            self._size_label.setText(f"Size: {FormatUtils.format_size(doc.file_size)}")

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
