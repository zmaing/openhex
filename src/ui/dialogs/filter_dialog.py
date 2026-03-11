"""
Row filter dialog.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)

from ...core.filter_engine import FilterSyntaxError, compile_row_filter
from ...utils.i18n import tr


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
        self.resize(780, 560)
        self._init_ui()

        self._set_active_filters(list(active_filters or []))
        self._refresh_history_list()
        self._refresh_saved_group_combo()

    def _init_ui(self) -> None:
        """Build the dialog layout."""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
            QGroupBox {
                border: 1px solid #2f2f2f;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QListWidget, QComboBox, QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 4px 8px;
            }
            QListWidget::item:selected {
                background-color: #094771;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2d2d30;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 6px 12px;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: #37373d;
            }
            QPushButton:pressed {
                background-color: #094771;
                color: #ffffff;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        description = QLabel(tr("filter_description"))
        description.setWordWrap(True)
        description.setStyleSheet("color: #c5c5c5;")
        layout.addWidget(description)

        input_group = QGroupBox(tr("filter_create_group"))
        input_layout = QVBoxLayout()
        input_layout.setSpacing(8)

        self._filter_input = QPlainTextEdit()
        self._filter_input.setPlaceholderText(tr("filter_input_placeholder"))
        self._filter_input.setFixedHeight(80)
        self._filter_input.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        input_layout.addWidget(self._filter_input)

        input_actions = QHBoxLayout()
        input_actions.setSpacing(8)

        add_button = QPushButton(tr("filter_add_condition"))
        add_button.clicked.connect(self._on_add_condition_clicked)
        input_actions.addWidget(add_button)

        input_actions.addWidget(QLabel(tr("filter_saved_group")))

        self._saved_group_combo = QComboBox()
        self._saved_group_combo.currentIndexChanged.connect(self._on_saved_group_changed)
        input_actions.addWidget(self._saved_group_combo, 1)

        input_layout.addLayout(input_actions)
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        lists_layout = QHBoxLayout()
        lists_layout.setSpacing(12)

        active_group = QGroupBox(tr("filter_active_group"))
        active_layout = QVBoxLayout()
        active_layout.setSpacing(8)

        active_hint = QLabel(tr("filter_active_hint"))
        active_hint.setWordWrap(True)
        active_hint.setStyleSheet("color: #8f8f8f; font-weight: 400;")
        active_layout.addWidget(active_hint)

        self._active_filters_list = QListWidget()
        self._active_filters_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._active_filters_list.setMinimumHeight(280)
        active_layout.addWidget(self._active_filters_list, 1)

        active_actions = QHBoxLayout()
        active_actions.setSpacing(8)
        remove_button = QPushButton(tr("filter_remove_selected"))
        remove_button.clicked.connect(self._remove_selected_active_filters)
        active_actions.addWidget(remove_button, 1)

        clear_button = QPushButton(tr("filter_clear_active"))
        clear_button.clicked.connect(self._clear_active_filters)
        active_actions.addWidget(clear_button, 1)

        active_layout.addLayout(active_actions)
        active_group.setLayout(active_layout)
        lists_layout.addWidget(active_group, 1)

        center_actions = QVBoxLayout()
        center_actions.setSpacing(8)
        center_actions.addStretch()
        import_button = QPushButton(tr("filter_import_condition"))
        import_button.clicked.connect(self._import_selected_history_conditions)
        import_button.setMinimumWidth(110)
        center_actions.addWidget(import_button)
        center_actions.addStretch()
        lists_layout.addLayout(center_actions)

        history_group = QGroupBox(tr("filter_history_group"))
        history_layout = QVBoxLayout()
        history_layout.setSpacing(8)

        history_hint = QLabel(tr("filter_history_hint"))
        history_hint.setWordWrap(True)
        history_hint.setStyleSheet("color: #8f8f8f;")
        history_layout.addWidget(history_hint)

        self._history_list = QListWidget()
        self._history_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._history_list.itemDoubleClicked.connect(lambda _item: self._import_selected_history_conditions())
        self._history_list.setMinimumHeight(280)
        history_layout.addWidget(self._history_list, 1)

        history_footer = QLabel("")
        history_footer.setFixedHeight(remove_button.sizeHint().height() + 2)
        history_layout.addWidget(history_footer)

        history_group.setLayout(history_layout)
        lists_layout.addWidget(history_group, 1)

        layout.addLayout(lists_layout)

        footer = QHBoxLayout()
        footer.addStretch()

        save_combo_button = QPushButton(tr("filter_save_combo"))
        save_combo_button.clicked.connect(self._save_current_group)
        footer.addWidget(save_combo_button)

        apply_button = QPushButton(tr("filter_apply"))
        apply_button.setDefault(True)
        apply_button.clicked.connect(self._on_apply_clicked)
        footer.addWidget(apply_button)

        layout.addLayout(footer)
        self.setLayout(layout)

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

    def _refresh_history_list(self) -> None:
        """Reload the history list widget."""
        self._history_list.clear()
        for expression in self._condition_history:
            self._history_list.addItem(expression)

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
        return True

    def _on_add_condition_clicked(self) -> None:
        """Handle adding a single filter condition."""
        self._add_pending_expression()

    def _remove_selected_active_filters(self) -> None:
        """Remove selected active filters."""
        rows = sorted({item.row() for item in self._active_filters_list.selectedIndexes()}, reverse=True)
        for row in rows:
            self._active_filters_list.takeItem(row)

    def _clear_active_filters(self) -> None:
        """Clear all active filters."""
        self._active_filters_list.clear()

    def _import_selected_history_conditions(self) -> None:
        """Import selected history conditions into the active list."""
        active = set(self.get_active_filters())
        for item in self._history_list.selectedItems():
            expression = item.text().strip()
            if expression and expression not in active:
                self._active_filters_list.addItem(expression)
                active.add(expression)

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
