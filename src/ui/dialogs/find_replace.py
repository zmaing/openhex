"""
Search/Replace Dialog

Find and replace functionality for hex editor.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QComboBox, QCheckBox,
                             QGroupBox, QButtonGroup, QRadioButton, QWidget,
                             QTabWidget, QTextEdit, QProgressBar)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QTextOption
from pathlib import Path

import re

# Import i18n
from ...utils.i18n import tr as _tr
from .chrome import create_dialog_header


DEBUG_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "debug.log"
DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class FindReplaceDialog(QDialog):
    """
    Find and replace dialog.

    Supports hex, text, and regex search modes.
    """

    # Signals
    find_next = pyqtSignal(str, object)  # pattern, search_type
    replace_next = pyqtSignal(str, str, object)  # pattern, replacement, search_type
    replace_all = pyqtSignal(str, str, object)  # pattern, replacement, search_type

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_results = []
        self._current_index = 0
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle(_tr("dialog_find_replace"))
        self.resize(560, 460)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            create_dialog_header(
                _tr("dialog_find_replace"),
                "统一处理查找、替换和结果回看，保持和主工作区一致的专业深色视觉层级。",
            )
        )

        # Search mode tabs
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # Find tab
        find_tab = self._create_find_tab()
        tabs.addTab(find_tab, _tr("tab_find"))

        # Replace tab
        replace_tab = self._create_replace_tab()
        tabs.addTab(replace_tab, _tr("tab_replace"))

        # Results tab
        results_tab = self._create_results_tab()
        tabs.addTab(results_tab, _tr("tab_results"))

        layout.addWidget(tabs)

        # Options
        options = self._create_options()
        layout.addWidget(options)

        # Buttons
        buttons = self._create_buttons()
        layout.addLayout(buttons)

        self.setLayout(layout)

    def _create_find_tab(self):
        """Create find tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search pattern
        layout.addWidget(QLabel(_tr("label_find")))
        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText(_tr("placeholder_find"))
        self._find_input.textChanged.connect(self._on_pattern_changed)
        layout.addWidget(self._find_input)

        # Search direction
        dir_layout = QHBoxLayout()
        self._direction_group = QButtonGroup()

        forward_btn = QRadioButton(_tr("label_forward"))
        forward_btn.setChecked(True)
        self._direction_group.addButton(forward_btn, 0)
        dir_layout.addWidget(forward_btn)

        backward_btn = QRadioButton(_tr("label_backward"))
        self._direction_group.addButton(backward_btn, 1)
        dir_layout.addWidget(backward_btn)

        dir_layout.addStretch()
        layout.addLayout(dir_layout)

        # Case sensitive
        self._case_sensitive = QCheckBox(_tr("label_case_sensitive"))
        layout.addWidget(self._case_sensitive)

        # Whole word
        self._whole_word = QCheckBox(_tr("label_whole_word"))
        layout.addWidget(self._whole_word)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_replace_tab(self):
        """Create replace tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search pattern
        layout.addWidget(QLabel(_tr("label_find")))
        self._replace_find_input = QLineEdit()
        self._replace_find_input.setPlaceholderText(_tr("placeholder_find"))
        layout.addWidget(self._replace_find_input)

        # Replace with
        layout.addWidget(QLabel(_tr("label_replace_with")))
        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText(_tr("placeholder_replace"))
        layout.addWidget(self._replace_input)

        # Options
        layout.addWidget(QLabel(_tr("label_replace_action")))

        replace_layout = QHBoxLayout()

        replace_next_btn = QPushButton(_tr("btn_replace_next"))
        replace_next_btn.clicked.connect(self._on_replace_next)
        replace_layout.addWidget(replace_next_btn)

        replace_all_btn = QPushButton(_tr("btn_replace_all"))
        replace_all_btn.clicked.connect(self._on_replace_all)
        replace_layout.addWidget(replace_all_btn)

        replace_layout.addStretch()
        layout.addLayout(replace_layout)

        # Prompt on replace all
        self._prompt_replace_all = QCheckBox(_tr("label_prompt_replace_all"))
        self._prompt_replace_all.setChecked(True)
        layout.addWidget(self._prompt_replace_all)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_results_tab(self):
        """Create results tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Results count
        self._results_count = QLabel(_tr("no_results"))
        layout.addWidget(self._results_count)

        # Results list
        self._results_list = QTextEdit()
        self._results_list.setReadOnly(True)
        self._results_list.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._results_list)

        widget.setLayout(layout)
        return widget

    def _create_options(self):
        """Create options group."""
        group = QGroupBox(_tr("label_search_mode"))
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        self._search_mode_group = QButtonGroup()

        hex_btn = QRadioButton(_tr("mode_hex"))
        hex_btn.setChecked(True)
        self._search_mode_group.addButton(hex_btn, 0)
        layout.addWidget(hex_btn)

        text_btn = QRadioButton(_tr("mode_text"))
        self._search_mode_group.addButton(text_btn, 1)
        layout.addWidget(text_btn)

        regex_btn = QRadioButton(_tr("mode_regex"))
        self._search_mode_group.addButton(regex_btn, 2)
        layout.addWidget(regex_btn)

        group.setLayout(layout)
        return group

    def _create_buttons(self):
        """Create buttons."""
        layout = QHBoxLayout()

        find_prev_btn = QPushButton(_tr("btn_find_prev"))
        find_prev_btn.clicked.connect(self._on_find_prev)
        layout.addWidget(find_prev_btn)

        find_next_btn = QPushButton(_tr("btn_find_next"))
        find_next_btn.clicked.connect(self._on_find_next)
        layout.addWidget(find_next_btn)

        layout.addStretch()

        close_btn = QPushButton(_tr("btn_close"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        return layout

    def _get_search_mode(self):
        """Get current search mode."""
        mode = self._search_mode_group.checkedId()
        if mode == 0:
            return "hex"
        elif mode == 1:
            return "text"
        else:
            return "regex"

    def _get_find_text(self):
        """Get find text based on active input."""
        if self._find_input.text():
            return self._find_input.text()
        return self._replace_find_input.text()

    def _on_pattern_changed(self, text):
        """Handle pattern change."""
        # Sync with replace tab
        if self._replace_find_input.text() != text:
            self._replace_find_input.setText(text)

    def _on_find_next(self):
        """Handle find next."""
        pattern = self._get_find_text()
        if not pattern:
            return

        mode = self._get_search_mode()
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(f"[DEBUG] find_next: pattern='{pattern}', mode={mode}\n")
        self.find_next.emit(pattern, mode)

    def _on_find_prev(self):
        """Handle find previous."""
        pattern = self._get_find_text()
        if not pattern:
            return

        mode = self._get_search_mode()
        # Emit with reverse direction indicator
        self.find_next.emit(pattern, mode)

    def _on_replace_next(self):
        """Handle replace next."""
        pattern = self._replace_find_input.text()
        replacement = self._replace_input.text()

        if not pattern:
            return

        mode = self._get_search_mode()
        self.replace_next.emit(pattern, replacement, mode)

    def _on_replace_all(self):
        """Handle replace all."""
        pattern = self._replace_find_input.text()
        replacement = self._replace_input.text()

        if not pattern:
            return

        mode = self._get_search_mode()
        self.replace_all.emit(pattern, replacement, mode)

    def set_results(self, results):
        """Set search results."""
        self._last_results = results
        self._current_index = 0

        if not results:
            self._results_count.setText("No results")
            self._results_list.clear()
            return

        self._results_count.setText(f"Found {len(results)} results")

        # Display results
        text = ""
        for i, result in enumerate(results[:1000]):  # Limit display
            text += f"{i+1}. Offset: 0x{result.offset:08X}  Length: {result.length}\n"

        if len(results) > 1000:
            text += f"\n... and {len(results) - 1000} more"

        self._results_list.setPlainText(text)

    def show_progress(self, show):
        """Show/hide progress."""
        self._progress.setVisible(show)
        if show:
            self._progress.setValue(0)

    def update_progress(self, current, total):
        """Update progress."""
        if total > 0:
            self._progress.setValue(int(current * 100 / total))
