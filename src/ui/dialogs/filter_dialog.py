"""
Row filter dialog.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
)

from ...core.filter_engine import FilterSyntaxError, compile_row_filter
from ...ui.design_system import CHROME, build_mono_font
from ...utils.i18n import tr
from .chrome import create_dialog_header, set_invalid_state


class FilterDialog(QDialog):
    """Configure row-based filters for the active hex view."""

    def __init__(
        self,
        active_filters: Iterable[str] | None = None,
        condition_history: Iterable[str] | None = None,
        saved_groups: Dict[str, List[str]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._condition_history = self._dedupe(condition_history or [])
        self._saved_groups = {
            str(name): self._dedupe(filters)
            for name, filters in (saved_groups or {}).items()
            if str(name).strip()
        }

        self.setWindowTitle(tr("dialog_filter"))
        self.resize(940, 620)
        self.setMinimumSize(840, 560)
        self._init_ui()

        self._set_active_filters(list(active_filters or []))
        self._refresh_history_list()
        self._refresh_saved_group_combo()

    def _init_ui(self) -> None:
        """Build the dialog layout."""
        self.setObjectName("filterDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(self._build_stylesheet())

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(
            create_dialog_header(
                tr("dialog_filter"),
                "用条件组合快速收缩可见行，并复用到当前视图分析流程中。",
            )
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        editor_card, editor_layout = self._create_card(
            "filterEditorCard",
            tr("filter_create_group"),
            "支持类 C 语法，使用 data[x] 读取当前行字节。",
        )
        syntax_hint = self._create_inline_hint("data[0] > 1    |    (data[63] & 0x0F) == 0x08")
        editor_layout.addWidget(syntax_hint)

        self._filter_input = QPlainTextEdit()
        self._filter_input.setObjectName("filterExpressionEditor")
        self._filter_input.setPlaceholderText(tr("filter_input_placeholder"))
        self._filter_input.setAccessibleName(tr("filter_create_group"))
        self._filter_input.setFont(build_mono_font(11))
        self._filter_input.setFixedHeight(90)
        self._filter_input.textChanged.connect(self._on_filter_input_changed)
        editor_layout.addWidget(self._filter_input)

        editor_footer = QHBoxLayout()
        editor_footer.setContentsMargins(0, 0, 0, 0)
        editor_footer.setSpacing(10)

        self._add_button = QPushButton(tr("filter_add_condition"))
        self._add_button.setObjectName("filterSecondaryButton")
        self._add_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._add_button.clicked.connect(self._on_add_condition_clicked)
        editor_footer.addWidget(self._add_button)
        editor_footer.addStretch()
        editor_layout.addLayout(editor_footer)
        top_row.addWidget(editor_card, 3)

        self._active_count_badge = self._create_count_badge()
        self._saved_group_count_badge = self._create_count_badge()
        saved_group_title = tr("filter_saved_group").rstrip(":：")
        saved_card, saved_layout = self._create_card(
            "filterSavedGroupCard",
            saved_group_title,
            "快速载入或覆盖常用条件组合。",
            self._saved_group_count_badge,
        )
        self._saved_group_combo = QComboBox()
        self._saved_group_combo.setObjectName("filterSavedGroupCombo")
        self._saved_group_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._saved_group_combo.currentIndexChanged.connect(self._on_saved_group_changed)
        saved_layout.addWidget(self._saved_group_combo)

        self._save_combo_button = QPushButton(tr("filter_save_combo"))
        self._save_combo_button.setObjectName("filterSecondaryButton")
        self._save_combo_button.clicked.connect(self._save_current_group)
        saved_layout.addWidget(self._save_combo_button)
        top_row.addWidget(saved_card, 2)

        layout.addLayout(top_row)

        self._history_count_badge = self._create_count_badge()
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        active_card, active_layout = self._create_card(
            "filterActiveCard",
            tr("filter_active_group"),
            tr("filter_active_hint"),
            self._active_count_badge,
        )
        active_list_frame = self._create_list_frame()
        active_list_layout = QVBoxLayout()
        active_list_layout.setContentsMargins(8, 8, 8, 8)
        active_list_layout.setSpacing(0)

        self._active_filters_list = QListWidget()
        self._active_filters_list.setObjectName("filterActiveList")
        self._active_filters_list.setFont(build_mono_font(10))
        self._active_filters_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._active_filters_list.setMinimumHeight(176)
        self._active_filters_list.itemSelectionChanged.connect(self._refresh_ui_state)
        active_list_layout.addWidget(self._active_filters_list)
        active_list_frame.setLayout(active_list_layout)
        active_layout.addWidget(active_list_frame, 1)

        active_actions = QHBoxLayout()
        active_actions.setContentsMargins(0, 2, 0, 0)
        active_actions.setSpacing(10)
        self._remove_button = QPushButton(tr("filter_remove_selected"))
        self._remove_button.setObjectName("filterSecondaryButton")
        self._remove_button.clicked.connect(self._remove_selected_active_filters)
        active_actions.addWidget(self._remove_button, 1)

        self._clear_button = QPushButton(tr("filter_clear_active"))
        self._clear_button.setObjectName("filterDangerButton")
        self._clear_button.clicked.connect(self._clear_active_filters)
        active_actions.addWidget(self._clear_button, 1)
        active_layout.addLayout(active_actions)
        bottom_row.addWidget(active_card, 1)

        history_card, history_layout = self._create_card(
            "filterHistoryCard",
            tr("filter_history_group"),
            tr("filter_history_hint"),
            self._history_count_badge,
        )
        history_list_frame = self._create_list_frame()
        history_list_layout = QVBoxLayout()
        history_list_layout.setContentsMargins(8, 8, 8, 8)
        history_list_layout.setSpacing(0)

        self._history_list = QListWidget()
        self._history_list.setObjectName("filterHistoryList")
        self._history_list.setFont(build_mono_font(10))
        self._history_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._history_list.itemSelectionChanged.connect(self._refresh_ui_state)
        self._history_list.itemDoubleClicked.connect(lambda _item: self._import_selected_history_conditions())
        self._history_list.setMinimumHeight(176)
        history_list_layout.addWidget(self._history_list)
        history_list_frame.setLayout(history_list_layout)
        history_layout.addWidget(history_list_frame, 1)

        self._import_button = QPushButton(tr("filter_import_condition"))
        self._import_button.setObjectName("filterSecondaryButton")
        self._import_button.clicked.connect(self._import_selected_history_conditions)
        history_layout.addWidget(self._import_button)
        bottom_row.addWidget(history_card, 1)

        layout.addLayout(bottom_row, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(10)
        footer.addStretch()

        self._apply_button = QPushButton(tr("filter_apply"))
        self._apply_button.setObjectName("filterPrimaryButton")
        self._apply_button.setDefault(True)
        self._apply_button.clicked.connect(self._on_apply_clicked)
        footer.addWidget(self._apply_button)

        layout.addLayout(footer)
        self.setLayout(layout)
        self._refresh_ui_state()
        self._filter_input.setFocus()

    def _build_stylesheet(self) -> str:
        """Return dialog-local styles that keep the window aligned with the app theme."""
        return f"""
            QDialog#filterDialog {{
                background-color: {CHROME.workspace_bg};
                color: {CHROME.text_primary};
            }}
            QDialog#filterDialog QLabel {{
                background: transparent;
                border: none;
            }}
            QDialog#filterDialog QFrame#filterEditorCard,
            QDialog#filterDialog QFrame#filterActiveCard,
            QDialog#filterDialog QFrame#filterSavedGroupCard,
            QDialog#filterDialog QFrame#filterHistoryCard {{
                background-color: {CHROME.surface};
                border: 1px solid {CHROME.border};
                border-radius: 14px;
            }}
            QLabel#filterCardTitle {{
                color: {CHROME.text_primary};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#filterCardSubtitle {{
                color: {CHROME.text_muted};
                font-size: 10px;
                font-weight: 500;
            }}
            QLabel#filterCountBadge {{
                background-color: {CHROME.surface_raised};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.border_strong};
                border-radius: 7px;
                padding: 1px 6px;
                min-width: 12px;
                font-size: 9px;
                font-weight: 700;
            }}
            QLabel#filterInstructionText {{
                color: {CHROME.text_secondary};
                font-size: 11px;
            }}
            QFrame#filterInlineHint {{
                background-color: {CHROME.surface_alt};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
            }}
            QLabel#filterInlineHintLabel {{
                color: {CHROME.text_primary};
                font-size: 10px;
                font-weight: 600;
                padding: 0;
            }}
            QPlainTextEdit#filterExpressionEditor {{
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
                padding: 8px 10px;
                selection-background-color: {CHROME.accent};
            }}
            QPlainTextEdit#filterExpressionEditor[invalid="true"] {{
                background-color: #2A171C;
                border-color: {CHROME.danger};
            }}
            QPlainTextEdit#filterExpressionEditor:hover,
            QComboBox#filterSavedGroupCombo:hover,
            QListWidget#filterActiveList:hover,
            QListWidget#filterHistoryList:hover {{
                border-color: {CHROME.border_strong};
            }}
            QPlainTextEdit#filterExpressionEditor:focus,
            QComboBox#filterSavedGroupCombo:focus {{
                border-color: {CHROME.accent};
            }}
            QComboBox#filterSavedGroupCombo,
            QFrame#filterListFrame {{
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
            }}
            QComboBox#filterSavedGroupCombo {{
                min-height: 28px;
                padding: 4px 26px 4px 10px;
            }}
            QComboBox#filterSavedGroupCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border: none;
                background: transparent;
            }}
            QComboBox#filterSavedGroupCombo::down-arrow {{
                width: 7px;
                height: 7px;
                margin-right: 8px;
            }}
            QListWidget#filterActiveList,
            QListWidget#filterHistoryList {{
                background: transparent;
                color: {CHROME.text_primary};
                border: none;
                padding: 0;
                outline: 0;
            }}
            QListWidget#filterActiveList::item,
            QListWidget#filterHistoryList::item {{
                border-radius: 8px;
                padding: 6px 10px;
                margin: 2px 0;
            }}
            QListWidget#filterActiveList::item:hover,
            QListWidget#filterHistoryList::item:hover {{
                background-color: {CHROME.surface_hover};
            }}
            QListWidget#filterActiveList::item:selected,
            QListWidget#filterHistoryList::item:selected {{
                background-color: {CHROME.accent_surface};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.accent_surface_strong};
            }}
            QPushButton#filterSecondaryButton {{
                background-color: {CHROME.surface_raised};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.border_strong};
                border-radius: 8px;
                padding: 4px 11px;
                min-height: 26px;
                font-weight: 600;
                font-size: 10px;
            }}
            QPushButton#filterSecondaryButton:hover {{
                background-color: {CHROME.surface_hover};
            }}
            QPushButton#filterDangerButton {{
                background-color: #3C2428;
                color: {CHROME.text_primary};
                border: 1px solid #6A434A;
                border-radius: 8px;
                padding: 4px 11px;
                min-height: 26px;
                font-weight: 600;
                font-size: 10px;
            }}
            QPushButton#filterDangerButton:hover {{
                background-color: #4A2B30;
                border-color: #83515A;
            }}
            QPushButton#filterPrimaryButton {{
                background-color: {CHROME.accent_surface};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.accent_surface_strong};
                border-radius: 9px;
                padding: 5px 14px;
                min-width: 96px;
                min-height: 30px;
                font-weight: 700;
                font-size: 10px;
            }}
            QPushButton#filterPrimaryButton:hover {{
                background-color: {CHROME.accent_surface_strong};
                border-color: {CHROME.accent_hover};
            }}
        """

    def _create_inline_hint(self, text: str) -> QFrame:
        """Create a compact inline syntax hint instead of a full-width help card."""
        card = QFrame(self)
        card.setObjectName("filterInlineHint")

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)

        label = QLabel(text)
        label.setObjectName("filterInlineHintLabel")
        label.setFont(build_mono_font(10))
        layout.addWidget(label)

        card.setLayout(layout)
        return card

    def _create_list_frame(self) -> QFrame:
        """Create a single bordered surface for list content."""
        frame = QFrame(self)
        frame.setObjectName("filterListFrame")
        return frame

    def _build_instruction_card(self) -> QFrame:
        """Create the syntax guidance strip shown below the dialog header."""
        card = QFrame(self)
        card.setObjectName("filterInstructionCard")

        layout = QHBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        description = QLabel(tr("filter_description"))
        description.setObjectName("filterInstructionText")
        description.setWordWrap(True)
        description.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(description, 5)

        syntax_example = QLabel("data[0] > 1\n(data[63] & 0x0F) == 0x08")
        syntax_example.setObjectName("filterSyntaxExample")
        syntax_example.setFont(build_mono_font(10))
        syntax_example.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        syntax_example.setMinimumWidth(290)
        syntax_example.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(syntax_example, 4)

        card.setLayout(layout)
        return card

    def _create_card(
        self,
        object_name: str,
        title: str,
        subtitle: str,
        badge: QLabel | None = None,
    ) -> tuple[QFrame, QVBoxLayout]:
        """Create a reusable card shell with title, hint and optional count badge."""
        card = QFrame(self)
        card.setObjectName(object_name)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("filterCardTitle")
        title_column.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("filterCardSubtitle")
            subtitle_label.setWordWrap(True)
            title_column.addWidget(subtitle_label)

        title_row.addLayout(title_column, 1)

        if badge is not None:
            title_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(title_row)
        card.setLayout(layout)
        return card, layout

    def _create_count_badge(self) -> QLabel:
        """Create a compact numeric badge used for section counts."""
        badge = QLabel("0")
        badge.setObjectName("filterCountBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return badge

    def _on_filter_input_changed(self) -> None:
        """Clear the invalid editor state as soon as the user edits the expression."""
        set_invalid_state(self._filter_input, False)

    def _refresh_ui_state(self) -> None:
        """Refresh count badges and enablement for action buttons."""
        active_count = self._active_filters_list.count()
        history_count = self._history_list.count()

        self._active_count_badge.setText(str(active_count))
        self._history_count_badge.setText(str(history_count))
        self._saved_group_count_badge.setText(str(len(self._saved_groups)))

        active_selection = bool(self._active_filters_list.selectedIndexes())
        history_selection = bool(self._history_list.selectedIndexes())

        self._remove_button.setEnabled(active_selection)
        self._clear_button.setEnabled(active_count > 0)
        self._save_combo_button.setEnabled(active_count > 0)
        self._import_button.setEnabled(history_selection)

    def get_active_filters(self) -> List[str]:
        """Return currently active row filters."""
        return [
            self._active_filters_list.item(index).text()
            for index in range(self._active_filters_list.count())
        ]

    def get_condition_history(self) -> List[str]:
        """Return historical row filters."""
        return list(self._condition_history)

    def get_saved_groups(self) -> Dict[str, List[str]]:
        """Return saved filter groups."""
        return {name: list(filters) for name, filters in self._saved_groups.items()}

    def _set_active_filters(self, filters: Iterable[str]) -> None:
        """Replace the active filter list."""
        self._active_filters_list.clear()
        for expression in self._dedupe(filters):
            self._active_filters_list.addItem(expression)
            self._add_condition_to_history(expression)
        self._refresh_ui_state()

    def _refresh_history_list(self) -> None:
        """Reload the history list widget."""
        self._history_list.clear()
        for expression in self._condition_history:
            self._history_list.addItem(expression)
        self._refresh_ui_state()

    def _refresh_saved_group_combo(self) -> None:
        """Reload the saved group combo box."""
        current_name = self._saved_group_combo.currentData()
        self._saved_group_combo.blockSignals(True)
        self._saved_group_combo.clear()
        self._saved_group_combo.addItem(tr("filter_saved_group_placeholder"), None)
        for group_name in sorted(self._saved_groups):
            self._saved_group_combo.addItem(group_name, group_name)

        if current_name in self._saved_groups:
            index = self._saved_group_combo.findData(current_name)
            if index >= 0:
                self._saved_group_combo.setCurrentIndex(index)
        self._saved_group_combo.blockSignals(False)
        self._refresh_ui_state()

    def _dedupe(self, filters: Iterable[str]) -> List[str]:
        """Keep insertion order while removing blanks and duplicates."""
        seen = set()
        result: List[str] = []
        for expression in filters:
            value = str(expression).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _add_condition_to_history(self, expression: str) -> None:
        """Add a condition to history if needed."""
        value = expression.strip()
        if not value or value in self._condition_history:
            return
        self._condition_history.append(value)
        self._refresh_history_list()

    def _validate_expression(self, expression: str) -> str:
        """Validate and normalize a row filter expression."""
        text = expression.strip()
        if not text:
            raise FilterSyntaxError(tr("filter_empty_error"))
        compile_row_filter(text)
        return text

    def _show_validation_error(self, message: str) -> None:
        """Show a validation error dialog."""
        set_invalid_state(self._filter_input, True)
        self._filter_input.setFocus()
        QMessageBox.warning(self, tr("dialog_filter"), message)

    def _add_pending_expression(self) -> bool:
        """Add the expression currently in the editor to active filters."""
        expression = self._filter_input.toPlainText().strip()
        if not expression:
            return True

        try:
            expression = self._validate_expression(expression)
        except FilterSyntaxError as exc:
            self._show_validation_error(tr("filter_invalid_error", str(exc)))
            return False

        if expression not in self.get_active_filters():
            self._active_filters_list.addItem(expression)
        self._add_condition_to_history(expression)
        self._filter_input.clear()
        self._refresh_ui_state()
        return True

    def _on_add_condition_clicked(self) -> None:
        """Handle adding a single filter condition."""
        self._add_pending_expression()

    def _remove_selected_active_filters(self) -> None:
        """Remove selected active filters."""
        rows = sorted({item.row() for item in self._active_filters_list.selectedIndexes()}, reverse=True)
        for row in rows:
            self._active_filters_list.takeItem(row)
        self._refresh_ui_state()

    def _clear_active_filters(self) -> None:
        """Clear all active filters."""
        self._active_filters_list.clear()
        self._refresh_ui_state()

    def _import_selected_history_conditions(self) -> None:
        """Import selected history conditions into the active list."""
        active = set(self.get_active_filters())
        for item in self._history_list.selectedItems():
            expression = item.text().strip()
            if expression and expression not in active:
                self._active_filters_list.addItem(expression)
                active.add(expression)
        self._refresh_ui_state()

    def _on_saved_group_changed(self, _index: int) -> None:
        """Load the selected saved filter group into the active list."""
        group_name = self._saved_group_combo.currentData()
        if not group_name:
            return
        filters = self._saved_groups.get(group_name, [])
        self._set_active_filters(filters)

    def _save_current_group(self) -> None:
        """Save the current active filter list as a named group."""
        if not self._add_pending_expression():
            return

        filters = self.get_active_filters()
        if not filters:
            self._show_validation_error(tr("filter_save_empty_error"))
            return

        name, accepted = QInputDialog.getText(
            self,
            tr("filter_save_combo"),
            tr("filter_group_name"),
        )
        if not accepted:
            return

        group_name = name.strip()
        if not group_name:
            self._show_validation_error(tr("filter_group_name_empty_error"))
            return

        if group_name in self._saved_groups:
            reply = QMessageBox.question(
                self,
                tr("filter_save_combo"),
                tr("filter_overwrite_group", group_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._saved_groups[group_name] = self._dedupe(filters)
        for expression in filters:
            self._add_condition_to_history(expression)

        self._refresh_saved_group_combo()
        index = self._saved_group_combo.findData(group_name)
        if index >= 0:
            self._saved_group_combo.setCurrentIndex(index)

    def _on_apply_clicked(self) -> None:
        """Validate any pending condition and apply the active filters."""
        if not self._add_pending_expression():
            return
        self.accept()
