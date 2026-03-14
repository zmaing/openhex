"""
Structure parsing side panel driven by user-defined C structs.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.parser.c_struct import CStructDefinition, decode_c_struct, parse_c_struct_definition
from ...utils.i18n import tr
from ..design_system import CHROME, MONO_FONT_FAMILY, build_mono_font, input_surface_qss, panel_surface_qss, table_surface_qss


STRUCTURE_DIALOG_BUTTON_HEIGHT = 28
STRUCTURE_DIALOG_ACTION_WIDTH = 96
STRUCTURE_DIALOG_PRIMARY_WIDTH = 102


def _build_structure_dialog_stylesheet(dialog_selector: str) -> str:
    """Return dialog-local chrome for structure config management surfaces."""
    return f"""
        {dialog_selector} {{
            background-color: {CHROME.workspace_bg};
            color: {CHROME.text_primary};
        }}
        {dialog_selector} QLabel {{
            background: transparent;
            border: none;
        }}
        {dialog_selector} QFrame#structureDialogCard {{
            background-color: {CHROME.surface};
            border: 1px solid {CHROME.border};
            border-radius: 13px;
        }}
        {dialog_selector} QFrame#structureListFrame {{
            background-color: {CHROME.surface_alt};
            border: 1px solid {CHROME.border};
            border-radius: 10px;
        }}
        {dialog_selector} QLabel#structureDialogSectionLabel {{
            color: {CHROME.text_secondary};
            font-size: 10px;
            font-weight: 700;
        }}
        {dialog_selector} QLabel#structureDialogSectionTitle {{
            color: {CHROME.text_primary};
            font-size: 11px;
            font-weight: 700;
        }}
        {dialog_selector} QLabel#structureCountBadge {{
            background-color: {CHROME.surface_raised};
            color: {CHROME.text_primary};
            border: 1px solid {CHROME.border_strong};
            border-radius: 6px;
            padding: 0 5px;
            min-width: 10px;
            min-height: 16px;
            font-size: 8px;
            font-weight: 700;
        }}
        {dialog_selector} QLineEdit#structureNameEdit,
        {dialog_selector} QPlainTextEdit#structureDefinitionEdit {{
            background-color: {CHROME.surface_alt};
            color: {CHROME.text_primary};
            border: 1px solid {CHROME.border};
            border-radius: 10px;
            padding: 6px 10px;
        }}
        {dialog_selector} QPlainTextEdit#structureDefinitionEdit {{
            padding: 9px 10px;
            selection-background-color: {CHROME.accent};
            font-family: {MONO_FONT_FAMILY};
        }}
        {dialog_selector} QLineEdit#structureNameEdit:hover,
        {dialog_selector} QPlainTextEdit#structureDefinitionEdit:hover {{
            border-color: {CHROME.border_strong};
        }}
        {dialog_selector} QLineEdit#structureNameEdit:focus,
        {dialog_selector} QPlainTextEdit#structureDefinitionEdit:focus {{
            border-color: {CHROME.accent};
        }}
        {dialog_selector} QListWidget#structureConfigList {{
            background: transparent;
            color: {CHROME.text_primary};
            border: none;
            padding: 0;
            outline: 0;
        }}
        {dialog_selector} QListWidget#structureConfigList::item {{
            border-radius: 8px;
            padding: 8px 10px;
            margin: 2px 0;
        }}
        {dialog_selector} QListWidget#structureConfigList::item:hover {{
            background-color: {CHROME.surface_hover};
        }}
        {dialog_selector} QListWidget#structureConfigList::item:selected {{
            background-color: {CHROME.accent_surface};
            color: {CHROME.text_primary};
            border: 1px solid {CHROME.accent_surface_strong};
        }}
        {dialog_selector} QPushButton#structureSecondaryButton,
        {dialog_selector} QPushButton#structureDangerButton,
        {dialog_selector} QPushButton#structurePrimaryButton {{
            border-radius: 8px;
            padding: 4px 12px;
            min-height: {STRUCTURE_DIALOG_BUTTON_HEIGHT}px;
            font-size: 10px;
            font-weight: 600;
        }}
        {dialog_selector} QPushButton#structureSecondaryButton {{
            background-color: {CHROME.surface_raised};
            color: {CHROME.text_primary};
            border: 1px solid {CHROME.border_strong};
        }}
        {dialog_selector} QPushButton#structureSecondaryButton:hover {{
            background-color: {CHROME.surface_hover};
        }}
        {dialog_selector} QPushButton#structureSecondaryButton:disabled {{
            background-color: {CHROME.surface};
            color: {CHROME.text_muted};
            border-color: {CHROME.border};
        }}
        {dialog_selector} QPushButton#structureDangerButton {{
            background-color: #3C2428;
            color: {CHROME.text_primary};
            border: 1px solid #6A434A;
        }}
        {dialog_selector} QPushButton#structureDangerButton:hover {{
            background-color: #4A2B30;
            border-color: #83515A;
        }}
        {dialog_selector} QPushButton#structureDangerButton:disabled {{
            background-color: {CHROME.surface};
            color: {CHROME.text_muted};
            border-color: {CHROME.border};
        }}
        {dialog_selector} QPushButton#structurePrimaryButton {{
            background-color: {CHROME.accent_surface};
            color: {CHROME.text_primary};
            border: 1px solid {CHROME.accent_surface_strong};
            font-weight: 700;
        }}
        {dialog_selector} QPushButton#structurePrimaryButton:hover {{
            background-color: {CHROME.accent_surface_strong};
            border-color: {CHROME.accent_hover};
        }}
        {dialog_selector} QPushButton#structurePrimaryButton:disabled {{
            background-color: {CHROME.surface_raised};
            color: {CHROME.text_muted};
            border-color: {CHROME.border};
        }}
    """


class NewStructureConfigDialog(QDialog):
    """Dialog for creating a new structure parsing config."""

    def __init__(
        self,
        parent=None,
        title: str | None = None,
        initial_name: str = "",
        initial_definition: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle(title or tr("panel_structure_new_title"))
        self.setObjectName("structureConfigEditDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_build_structure_dialog_stylesheet("QDialog#structureConfigEditDialog"))
        self.resize(520, 360)
        self.setMinimumSize(480, 320)
        self._initial_name = initial_name
        self._initial_definition = initial_definition
        self._init_ui()

    def _init_ui(self):
        """Build the dialog layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        form_card = QFrame(self)
        form_card.setObjectName("structureDialogCard")
        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.setSpacing(10)

        name_label = QLabel(tr("panel_structure_name"))
        name_label.setObjectName("structureDialogSectionLabel")
        form_layout.addWidget(name_label)

        self._name_edit = QLineEdit()
        self._name_edit.setObjectName("structureNameEdit")
        self._name_edit.setPlaceholderText(tr("panel_structure_name_placeholder"))
        self._name_edit.setText(self._initial_name)
        form_layout.addWidget(self._name_edit)

        definition_label = QLabel(tr("panel_structure_definition"))
        definition_label.setObjectName("structureDialogSectionLabel")
        form_layout.addWidget(definition_label)

        self._definition_edit = QPlainTextEdit()
        self._definition_edit.setObjectName("structureDefinitionEdit")
        self._definition_edit.setPlaceholderText(tr("panel_structure_definition_placeholder"))
        self._definition_edit.setPlainText(self._initial_definition)
        self._definition_edit.setFont(build_mono_font(11))
        form_layout.addWidget(self._definition_edit, 1)

        form_card.setLayout(form_layout)
        layout.addWidget(form_card, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch()

        self._cancel_button = QPushButton(tr("panel_structure_cancel"))
        self._cancel_button.setObjectName("structureSecondaryButton")
        self._cancel_button.setMinimumWidth(STRUCTURE_DIALOG_ACTION_WIDTH)
        self._cancel_button.setMinimumHeight(STRUCTURE_DIALOG_BUTTON_HEIGHT)
        self._cancel_button.clicked.connect(self.reject)
        footer.addWidget(self._cancel_button)

        self._confirm_button = QPushButton(tr("panel_structure_confirm"))
        self._confirm_button.setObjectName("structurePrimaryButton")
        self._confirm_button.setMinimumWidth(STRUCTURE_DIALOG_PRIMARY_WIDTH)
        self._confirm_button.setMinimumHeight(STRUCTURE_DIALOG_BUTTON_HEIGHT)
        self._confirm_button.setDefault(True)
        self._confirm_button.clicked.connect(self.accept)
        footer.addWidget(self._confirm_button)

        layout.addLayout(footer)

        self.setLayout(layout)

    def config_name(self) -> str:
        """Return the entered config name."""
        return self._name_edit.text().strip()

    def definition_text(self) -> str:
        """Return the entered C struct definition."""
        return self._definition_edit.toPlainText().strip()


class StructureConfigManagerDialog(QDialog):
    """Dialog for editing and deleting saved structure configs."""

    def __init__(self, panel: "StructureViewPanel", parent=None):
        super().__init__(parent or panel)
        self._panel = panel
        self.setWindowTitle(tr("panel_structure_manage_title"))
        self.setObjectName("structureConfigManagerDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_build_structure_dialog_stylesheet("QDialog#structureConfigManagerDialog"))
        self.resize(520, 372)
        self.setMinimumSize(480, 332)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        """Build the manager dialog layout."""
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        card = QFrame(self)
        card.setObjectName("structureDialogCard")
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        section_label = QLabel(tr("panel_structure_manage_saved"))
        section_label.setObjectName("structureDialogSectionTitle")
        title_row.addWidget(section_label)
        title_row.addStretch()

        self._count_badge = QLabel("0")
        self._count_badge.setObjectName("structureCountBadge")
        title_row.addWidget(self._count_badge)
        card_layout.addLayout(title_row)

        list_frame = QFrame(self)
        list_frame.setObjectName("structureListFrame")
        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(7, 7, 7, 7)
        list_layout.setSpacing(0)

        self._config_list = QListWidget()
        self._config_list.setObjectName("structureConfigList")
        self._config_list.itemDoubleClicked.connect(self._on_edit_clicked)
        self._config_list.currentItemChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self._config_list)
        list_frame.setLayout(list_layout)
        card_layout.addWidget(list_frame, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)

        self._edit_button = QPushButton(tr("panel_structure_edit"))
        self._edit_button.setObjectName("structureSecondaryButton")
        self._edit_button.setMinimumWidth(STRUCTURE_DIALOG_ACTION_WIDTH)
        self._edit_button.setMinimumHeight(STRUCTURE_DIALOG_BUTTON_HEIGHT)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        button_row.addWidget(self._edit_button)

        self._delete_button = QPushButton(tr("panel_structure_delete"))
        self._delete_button.setObjectName("structureDangerButton")
        self._delete_button.setMinimumWidth(STRUCTURE_DIALOG_ACTION_WIDTH)
        self._delete_button.setMinimumHeight(STRUCTURE_DIALOG_BUTTON_HEIGHT)
        self._delete_button.clicked.connect(self._on_delete_clicked)
        button_row.addWidget(self._delete_button)
        button_row.addStretch()
        card_layout.addLayout(button_row)

        card.setLayout(card_layout)
        layout.addWidget(card, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch()

        self._close_button = QPushButton(tr("btn_close"))
        self._close_button.setObjectName("structurePrimaryButton")
        self._close_button.setMinimumWidth(STRUCTURE_DIALOG_PRIMARY_WIDTH)
        self._close_button.setMinimumHeight(STRUCTURE_DIALOG_BUTTON_HEIGHT)
        self._close_button.clicked.connect(self.reject)
        footer.addWidget(self._close_button)

        layout.addLayout(footer)

        self.setLayout(layout)

    def refresh(self):
        """Refresh the list of saved configs."""
        selected_name = None
        current_item = self._config_list.currentItem()
        if current_item is not None:
            selected_name = current_item.data(Qt.ItemDataRole.UserRole)

        self._config_list.clear()
        for config in self._panel.configs():
            item = QListWidgetItem(str(config["name"]))
            item.setData(Qt.ItemDataRole.UserRole, str(config["name"]))
            self._config_list.addItem(item)
        self._count_badge.setText(str(self._config_list.count()))

        if self._config_list.count():
            target_name = selected_name or self._panel.selected_config_name()
            for row in range(self._config_list.count()):
                item = self._config_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == target_name:
                    self._config_list.setCurrentRow(row)
                    break
            if self._config_list.currentRow() < 0:
                self._config_list.setCurrentRow(0)

        self._on_selection_changed(self._config_list.currentItem(), None)

    def _selected_name(self) -> str:
        """Return the currently selected config name."""
        item = self._config_list.currentItem()
        if item is None:
            return ""
        data = item.data(Qt.ItemDataRole.UserRole)
        return str(data) if data else ""

    def _on_selection_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None):
        """Enable or disable action buttons based on selection."""
        has_selection = current is not None
        self._edit_button.setEnabled(has_selection)
        self._delete_button.setEnabled(has_selection)

    def _on_edit_clicked(self, item: QListWidgetItem | None = None):
        """Edit the currently selected config."""
        name = self._selected_name()
        if not name:
            return

        while True:
            config = self._panel.get_config(name)
            if config is None:
                self.refresh()
                return

            dialog = NewStructureConfigDialog(
                self,
                title=tr("panel_structure_edit_title"),
                initial_name=str(config["name"]),
                initial_definition=str(config["definition"]),
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            try:
                updated_name = self._panel.update_config(
                    name,
                    dialog.config_name(),
                    dialog.definition_text(),
                )
                self.refresh()
                for row in range(self._config_list.count()):
                    list_item = self._config_list.item(row)
                    if list_item.data(Qt.ItemDataRole.UserRole) == updated_name:
                        self._config_list.setCurrentRow(row)
                        break
                return
            except ValueError as exc:
                QMessageBox.warning(self, tr("panel_structure_edit_title"), str(exc))

    def _on_delete_clicked(self):
        """Delete the currently selected config after confirmation."""
        name = self._selected_name()
        if not name:
            return

        result = QMessageBox.question(
            self,
            tr("panel_structure_manage_title"),
            tr("panel_structure_delete_confirm", name),
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        self._panel.delete_config(name)
        self.refresh()


class StructureViewPanel(QWidget):
    """Parse the current row using a saved C struct definition."""

    CONFIGS_KEY = "structure_parser/configs"
    SELECTED_KEY = "structure_parser/selected_config"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._configs: list[dict[str, object]] = []
        self._current_config_name = ""
        self._current_definition: CStructDefinition | None = None
        self._current_row_offset = 0
        self._current_row_data = b""
        self._display_base = "hex"
        self._value_font = build_mono_font(10)
        self._init_ui()
        self._load_configs()
        self._refresh_config_combo()
        self.clear_values()

    def _init_ui(self):
        """Initialize panel UI."""
        self.setObjectName("structureViewPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            panel_surface_qss("QWidget#structureViewPanel")
            + input_surface_qss("QWidget#structureViewPanel")
            + table_surface_qss("QWidget#structureViewPanel")
            + f"""
            QWidget#structureViewPanel {{
                background: transparent;
                border: none;
            }}
            QLabel#structureSectionLabel {{
                color: {CHROME.text_muted};
                font-size: 9px;
                font-weight: 700;
            }}
            QLabel#structureMetricValue {{
                color: {CHROME.text_primary};
                background: transparent;
                border: none;
                padding: 0;
            }}
            QFrame#structureSummaryCard {{
                background-color: {CHROME.surface_alt};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
            }}
            QFrame#structureMetricBlock {{
                background: transparent;
                border: none;
            }}
            QWidget#structureViewPanel QRadioButton {{
                color: {CHROME.text_secondary};
                spacing: 6px;
                font-weight: 600;
            }}
            QWidget#structureViewPanel QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1px solid {CHROME.border_strong};
                background-color: {CHROME.surface};
            }}
            QWidget#structureViewPanel QRadioButton::indicator:checked {{
                background-color: {CHROME.accent};
                border-color: {CHROME.accent};
            }}
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        summary_card = QFrame(self)
        summary_card.setObjectName("structureSummaryCard")
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(12, 10, 12, 10)
        summary_layout.setSpacing(16)

        offset_block = QFrame(summary_card)
        offset_block.setObjectName("structureMetricBlock")
        offset_layout = QVBoxLayout(offset_block)
        offset_layout.setContentsMargins(0, 0, 0, 0)
        offset_layout.setSpacing(4)
        offset_label = QLabel(tr("panel_structure_offset"))
        offset_label.setObjectName("structureSectionLabel")
        offset_layout.addWidget(offset_label)
        self._offset_value = QLabel("0x00000000")
        self._offset_value.setObjectName("structureMetricValue")
        self._offset_value.setFont(self._value_font)
        offset_layout.addWidget(self._offset_value)
        summary_layout.addWidget(offset_block, 0, Qt.AlignmentFlag.AlignTop)

        display_block = QFrame(summary_card)
        display_block.setObjectName("structureMetricBlock")
        display_layout = QVBoxLayout(display_block)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(4)
        display_label = QLabel(tr("panel_structure_display"))
        display_label.setObjectName("structureSectionLabel")
        display_layout.addWidget(display_label)
        display_row = QHBoxLayout()
        display_row.setContentsMargins(0, 0, 0, 0)
        display_row.setSpacing(8)
        self._hex_radio = QRadioButton(tr("panel_structure_hex"))
        self._decimal_radio = QRadioButton(tr("panel_structure_decimal"))
        self._display_group = QButtonGroup(self)
        self._display_group.setExclusive(True)
        self._display_group.addButton(self._hex_radio)
        self._display_group.addButton(self._decimal_radio)
        self._hex_radio.setChecked(True)
        self._hex_radio.toggled.connect(self._on_display_mode_changed)
        self._decimal_radio.toggled.connect(self._on_display_mode_changed)
        display_row.addWidget(self._hex_radio)
        display_row.addWidget(self._decimal_radio)
        display_row.addStretch()
        display_layout.addLayout(display_row)
        summary_layout.addWidget(display_block, 1, Qt.AlignmentFlag.AlignTop)

        summary_card.setLayout(summary_layout)
        layout.addWidget(summary_card)

        config_row = QHBoxLayout()
        config_row.setContentsMargins(2, 0, 2, 0)
        config_row.setSpacing(8)
        self._config_combo = QComboBox()
        self._config_combo.activated.connect(self._on_config_activated)
        config_row.addWidget(self._config_combo, 1)
        layout.addLayout(config_row)

        self._table = QTableWidget(0, 2, self)
        self._table.setHorizontalHeaderLabels(
            [tr("panel_structure_field"), tr("panel_structure_value")]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table, 1)

        self.setLayout(layout)

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

    def _load_configs(self):
        """Load saved structure configs from settings."""
        settings = self._get_settings()
        raw_value = settings.value(self.CONFIGS_KEY, "[]")
        if isinstance(raw_value, str):
            try:
                serialized = json.loads(raw_value)
            except json.JSONDecodeError:
                serialized = []
        elif isinstance(raw_value, list):
            serialized = raw_value
        else:
            serialized = []

        configs = []
        for item in serialized:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            definition = str(item.get("definition", "")).strip()
            if not name or not definition:
                continue
            try:
                parsed = parse_c_struct_definition(definition)
            except ValueError:
                continue
            configs.append({"name": name, "definition": definition, "parsed": parsed})

        self._configs = configs
        self._current_config_name = str(settings.value(self.SELECTED_KEY, "", type=str) or "")

    def _save_configs(self):
        """Persist current config list to settings."""
        settings = self._get_settings()
        payload = [
            {"name": str(config["name"]), "definition": str(config["definition"])}
            for config in self._configs
        ]
        settings.setValue(self.CONFIGS_KEY, json.dumps(payload, ensure_ascii=False))
        settings.setValue(self.SELECTED_KEY, self._current_config_name)

    def _refresh_config_combo(self, selected_name: str | None = None):
        """Rebuild the config dropdown contents."""
        blocked = self._config_combo.blockSignals(True)
        self._config_combo.clear()
        self._config_combo.addItem(tr("panel_structure_new_config"), "__new__")
        self._config_combo.addItem(tr("panel_structure_manage_config"), "__manage__")
        if self._configs:
            self._config_combo.insertSeparator(2)
            for config in self._configs:
                self._config_combo.addItem(str(config["name"]), str(config["name"]))

        target_name = selected_name
        if target_name is None:
            if self._current_config_name:
                target_name = self._current_config_name
            elif self._configs:
                target_name = str(self._configs[0]["name"])

        if target_name:
            index = self._config_combo.findData(target_name)
            if index >= 0:
                self._config_combo.setCurrentIndex(index)
                self._apply_selected_config(target_name)
            else:
                self._config_combo.setCurrentIndex(0)
                self._apply_selected_config("")
        else:
            self._config_combo.setCurrentIndex(0)
            self._apply_selected_config("")

        self._config_combo.blockSignals(blocked)

    def _find_config(self, name: str) -> dict[str, object] | None:
        """Return a config record by name."""
        for config in self._configs:
            if config["name"] == name:
                return config
        return None

    def _apply_selected_config(self, name: str):
        """Activate a config and refresh the decoded table."""
        config = self._find_config(name)
        self._current_config_name = name if config else ""
        self._current_definition = config["parsed"] if config else None
        self._save_configs()
        self._render_table()

    def _on_config_activated(self, index: int):
        """Handle user selection from the config dropdown."""
        if index == 0:
            self._open_new_config_dialog()
            return
        if index == 1:
            self._open_manage_config_dialog()
            return

        name = self._config_combo.itemData(index)
        if isinstance(name, str):
            self._apply_selected_config(name)

    def _open_new_config_dialog(self):
        """Show the new-config dialog and save on success."""
        dialog = NewStructureConfigDialog(self)
        while dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.add_config(dialog.config_name(), dialog.definition_text())
                return
            except ValueError as exc:
                QMessageBox.warning(self, tr("panel_structure_new_title"), str(exc))

        self._refresh_config_combo(selected_name=self._current_config_name)

    def _open_manage_config_dialog(self):
        """Show the manager dialog for existing configs."""
        dialog = StructureConfigManagerDialog(self, self)
        dialog.exec()
        self._refresh_config_combo(selected_name=self._current_config_name)

    def _on_display_mode_changed(self, checked: bool):
        """Switch between hex and decimal display."""
        if not checked:
            return
        self._display_base = "hex" if self._hex_radio.isChecked() else "decimal"
        self._render_table()

    def _set_table_item(self, row: int, column: int, text: str):
        """Create or update a table item."""
        item = self._table.item(row, column)
        if item is None:
            item = QTableWidgetItem()
            item.setFont(self._value_font)
            item.setTextAlignment(
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            )
            self._table.setItem(row, column, item)
        item.setText(text)
        item.setToolTip(text)

    def _render_table(self):
        """Render the active config against the cached current-row bytes."""
        if self._current_row_data:
            self._offset_value.setText(f"0x{self._current_row_offset:08X}")
        else:
            self._offset_value.setText("0x00000000")

        if self._current_definition is None:
            self._table.setRowCount(0)
            return

        rows = decode_c_struct(
            self._current_definition,
            self._current_row_data,
            display_base=self._display_base,
        )
        self._table.setRowCount(len(rows))
        for row, (field, value) in enumerate(rows):
            self._set_table_item(row, 0, field.display_name)
            self._set_table_item(row, 1, value)
            self._table.setRowHeight(row, CHROME.row_height)

    def add_config(self, name: str, definition: str):
        """Add a new parsing config and make it active."""
        normalized_name = (name or "").strip()
        normalized_definition = (definition or "").strip()
        if not normalized_name:
            raise ValueError(tr("panel_structure_invalid_name"))
        if not normalized_definition:
            raise ValueError(tr("panel_structure_invalid_definition"))
        if self._find_config(normalized_name) is not None:
            raise ValueError(tr("panel_structure_duplicate_name"))

        try:
            parsed = parse_c_struct_definition(normalized_definition)
        except ValueError as exc:
            raise ValueError(tr("panel_structure_parse_error", str(exc))) from exc

        self._configs.append(
            {
                "name": normalized_name,
                "definition": normalized_definition,
                "parsed": parsed,
            }
        )
        self._current_config_name = normalized_name
        self._current_definition = parsed
        self._save_configs()
        self._refresh_config_combo(selected_name=normalized_name)

    def update_config(self, old_name: str, new_name: str, definition: str) -> str:
        """Update an existing config and return its effective name."""
        config = self._find_config(old_name)
        if config is None:
            raise ValueError(f"Unknown config: {old_name}")

        normalized_name = (new_name or "").strip()
        normalized_definition = (definition or "").strip()
        if not normalized_name:
            raise ValueError(tr("panel_structure_invalid_name"))
        if not normalized_definition:
            raise ValueError(tr("panel_structure_invalid_definition"))
        if normalized_name != old_name and self._find_config(normalized_name) is not None:
            raise ValueError(tr("panel_structure_duplicate_name"))

        try:
            parsed = parse_c_struct_definition(normalized_definition)
        except ValueError as exc:
            raise ValueError(tr("panel_structure_parse_error", str(exc))) from exc

        config["name"] = normalized_name
        config["definition"] = normalized_definition
        config["parsed"] = parsed

        if self._current_config_name == old_name:
            self._current_config_name = normalized_name
            self._current_definition = parsed

        self._save_configs()
        self._refresh_config_combo(selected_name=normalized_name)
        return normalized_name

    def delete_config(self, name: str):
        """Delete a saved config."""
        self._configs = [config for config in self._configs if config["name"] != name]

        if self._current_config_name == name:
            self._current_config_name = str(self._configs[0]["name"]) if self._configs else ""
            config = self._find_config(self._current_config_name)
            self._current_definition = config["parsed"] if config else None

        self._save_configs()
        self._refresh_config_combo(selected_name=self._current_config_name)

    def set_selected_config(self, name: str):
        """Programmatically select an existing config."""
        if self._find_config(name) is None:
            raise ValueError(f"Unknown config: {name}")
        self._refresh_config_combo(selected_name=name)

    def get_config(self, name: str) -> dict[str, object] | None:
        """Return a copy-friendly reference to a config."""
        return self._find_config(name)

    def configs(self) -> list[dict[str, object]]:
        """Return the current config list."""
        return list(self._configs)

    def selected_config_name(self) -> str:
        """Return the current selected config name."""
        return self._current_config_name

    def update_row_data(self, row_offset: int, data: bytes):
        """Update the currently displayed row bytes."""
        self._current_row_offset = max(0, int(row_offset))
        self._current_row_data = bytes(data or b"")
        self._render_table()

    def clear_values(self):
        """Clear the cached row data while preserving the selected config."""
        self._current_row_offset = 0
        self._current_row_data = b""
        self._render_table()
