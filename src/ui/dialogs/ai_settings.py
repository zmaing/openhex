"""
AI Settings Dialog

Configure AI provider settings.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...utils.i18n import tr
from .chrome import create_dialog_header
from ..design_system import CHROME


class AISettingsDialog(QDialog):
    """
    AI Settings Dialog.

    Configure AI provider, API keys, models, etc.
    """

    settings_changed = pyqtSignal(dict)

    GENERAL_PROVIDER_OPTIONS = [
        ("local", "ai_settings_provider_local"),
        ("openai", "ai_settings_provider_openai"),
        ("anthropic", "ai_settings_provider_anthropic"),
        ("minimax", "ai_settings_provider_minimax"),
        ("glm", "ai_settings_provider_glm5"),
    ]

    CLOUD_PROVIDER_OPTIONS = [
        ("openai", "ai_settings_provider_openai"),
        ("anthropic", "ai_settings_provider_anthropic"),
        ("minimax", "ai_settings_provider_minimax"),
        ("glm", "ai_settings_provider_glm_zhipu"),
    ]

    CLOUD_PROVIDER_DEFAULTS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "models": ["gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com",
            "models": [
                "claude-sonnet-4-20250514",
                "claude-3-7-sonnet-latest",
                "claude-3-5-sonnet-latest",
                "claude-3-opus-20240229",
            ],
        },
        "minimax": {
            "base_url": "https://api.minimaxi.com/v1",
            "models": ["MiniMax-M2.5", "MiniMax-M1"],
        },
        "glm": {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "models": ["glm-5", "glm-4.5", "glm-4.5-air", "glm-4.5-flash"],
        },
    }

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self._current_settings = current_settings or {}
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle(self._tr("ai_settings_title"))
        self.resize(760, 640)
        self.setMinimumSize(700, 580)
        self.setObjectName("aiSettingsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(self._build_stylesheet())

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            create_dialog_header(
                self._tr("ai_settings_title"),
                self._tr("ai_settings_subtitle"),
            )
        )

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setObjectName("aiSettingsTabs")
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setDrawBase(False)
        self._tabs.tabBar().setExpanding(False)
        self._tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)

        # General tab
        general_tab = self._create_general_tab()
        self._tabs.addTab(general_tab, self._tr("ai_settings_tab_general"))

        # Local tab
        local_tab = self._create_local_tab()
        self._tabs.addTab(local_tab, self._tr("ai_settings_tab_local"))

        # Cloud tab
        cloud_tab = self._create_cloud_tab()
        self._tabs.addTab(cloud_tab, self._tr("ai_settings_tab_cloud"))

        layout.addWidget(self._tabs, 1)

        # Buttons
        footer = QFrame()
        footer.setObjectName("aiSettingsFooter")
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 10, 0, 0)
        footer_layout.setSpacing(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setObjectName("aiSettingsActions")
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)

        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText(self._tr("btn_ok"))
            ok_button.setDefault(True)
            ok_button.setAutoDefault(True)

        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText(self._tr("btn_cancel"))

        footer_layout.addWidget(buttons)
        footer.setLayout(footer_layout)
        layout.addWidget(footer)

        self.setLayout(layout)
        self._on_general_provider_changed(self._provider_combo.currentIndex())

    def _create_general_tab(self):
        """Create general settings tab."""
        widget, layout = self._create_page_shell()
        layout.setSpacing(12)

        runtime_card, runtime_layout = self._create_card(
            self._tr("ai_settings_global_routing_title"),
            self._tr("ai_settings_global_routing_subtitle"),
        )

        self._enable_ai = QCheckBox(self._tr("ai_settings_enable_ai"))
        self._enable_ai.setChecked(self._current_settings.get('enabled', True))
        runtime_layout.addWidget(self._enable_ai)

        form = self._create_form_layout()

        self._provider_combo = QComboBox()
        self._provider_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._provider_combo.setMinimumWidth(240)
        self._provider_combo.addItems(self._translated_option_labels(self.GENERAL_PROVIDER_OPTIONS))
        current_provider = self._current_settings.get('provider', 'local')
        self._set_combo_by_value(self._provider_combo, self.GENERAL_PROVIDER_OPTIONS, current_provider)
        self._provider_combo.currentIndexChanged.connect(self._on_general_provider_changed)

        self._add_form_row(form, self._tr("ai_settings_default_provider"), self._provider_combo)
        runtime_layout.addLayout(form)
        runtime_layout.addWidget(
            self._create_callout(
                self._tr("ai_settings_cloud_credentials_callout")
            )
        )
        layout.addWidget(runtime_card)

        overview_row = QHBoxLayout()
        overview_row.setContentsMargins(0, 0, 0, 0)
        overview_row.setSpacing(12)

        capabilities_card, capabilities_layout = self._create_card(
            self._tr("ai_settings_capabilities_title"),
            self._tr("ai_settings_capabilities_subtitle"),
        )
        capabilities_layout.addWidget(
            self._create_info_block(
                self._tr("ai_settings_ai_features_title"),
                [
                    self._tr("ai_settings_feature_analyze"),
                    self._tr("ai_settings_feature_detect"),
                    self._tr("ai_settings_feature_generate"),
                ],
            )
        )
        overview_row.addWidget(capabilities_card, 3)

        provider_card, provider_layout = self._create_card(
            self._tr("ai_settings_provider_notes_title"),
            self._tr("ai_settings_provider_notes_subtitle"),
        )
        provider_layout.addWidget(
            self._create_info_block(
                self._tr("ai_settings_provider_note_local_title"),
                [
                    self._tr("ai_settings_provider_note_local_private"),
                    self._tr("ai_settings_provider_note_local_requirements"),
                ],
            )
        )
        provider_layout.addWidget(
            self._create_info_block(
                self._tr("ai_settings_cloud_api_title"),
                [
                    self._tr("ai_settings_provider_note_cloud_supports"),
                    self._tr("ai_settings_provider_note_cloud_requirements"),
                ],
            )
        )
        overview_row.addWidget(provider_card, 2)

        layout.addLayout(overview_row)

        layout.addStretch()
        return widget

    def _create_local_tab(self):
        """Create local settings tab."""
        widget, layout = self._create_page_shell()

        runtime_card, runtime_layout = self._create_card(
            self._tr("ai_settings_ollama_runtime_title"),
            self._tr("ai_settings_ollama_runtime_subtitle"),
        )
        form = self._create_form_layout()

        # Endpoint
        self._local_endpoint = QLineEdit(
            self._current_settings.get('local', {}).get('endpoint', 'http://localhost:11434')
        )
        self._local_endpoint.setPlaceholderText("http://localhost:11434")
        self._local_endpoint.setClearButtonEnabled(True)
        self._local_endpoint.setMinimumWidth(320)
        self._add_form_row(form, self._tr("ai_settings_api_endpoint"), self._local_endpoint)

        # Model
        self._local_model = QComboBox()
        self._local_model.setMinimumWidth(240)
        self._local_model.addItems([
            "qwen:7b",
            "qwen:14b",
            "llama3:8b",
            "llama3:70b",
            "mistral:7b",
            "codellama:7b",
            "phi3:14b"
        ])
        current_model = self._current_settings.get('local', {}).get('model', 'qwen:7b')
        index = self._local_model.findText(current_model)
        if index >= 0:
            self._local_model.setCurrentIndex(index)
        self._add_form_row(form, self._tr("ai_settings_model"), self._local_model)

        # Temperature
        self._local_temp = QDoubleSpinBox()
        self._local_temp.setRange(0.0, 2.0)
        self._local_temp.setSingleStep(0.1)
        self._local_temp.setDecimals(1)
        self._local_temp.setValue(float(self._current_settings.get('local', {}).get('temperature', 0.7)))
        self._add_form_row(form, self._tr("ai_settings_temperature"), self._local_temp)

        # Max tokens
        self._local_tokens = QSpinBox()
        self._local_tokens.setRange(256, 32768)
        self._local_tokens.setSingleStep(256)
        self._local_tokens.setValue(self._current_settings.get('local', {}).get('max_tokens', 4096))
        self._add_form_row(form, self._tr("ai_settings_max_tokens"), self._local_tokens)

        # Timeout
        self._local_timeout = QSpinBox()
        self._local_timeout.setRange(10, 300)
        self._local_timeout.setSuffix(self._tr("ai_settings_seconds_suffix"))
        self._local_timeout.setValue(self._current_settings.get('local', {}).get('timeout', 60))
        self._add_form_row(form, self._tr("ai_settings_timeout"), self._local_timeout)

        runtime_layout.addLayout(form)
        layout.addWidget(runtime_card)

        lower_row = QHBoxLayout()
        lower_row.setContentsMargins(0, 0, 0, 0)
        lower_row.setSpacing(12)

        # Test button
        connection_card, connection_layout = self._create_card(
            self._tr("ai_settings_connectivity_title"),
            self._tr("ai_settings_connectivity_subtitle"),
        )
        test_btn = QPushButton(self._tr("ai_settings_test_connection"))
        test_btn.setObjectName("aiSettingsSecondaryButton")
        test_btn.clicked.connect(self._on_test_local)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(10)
        status_row.addWidget(test_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self._local_test_result = QLabel(self._tr("ai_settings_not_tested"))
        self._local_test_result.setObjectName("aiSettingsStatusLabel")
        self._set_status_state(self._local_test_result, "idle")
        status_row.addWidget(self._local_test_result, 1, Qt.AlignmentFlag.AlignVCenter)
        status_row.addStretch()
        connection_layout.addLayout(status_row)
        connection_layout.addWidget(
            self._create_callout(self._tr("ai_settings_check_fails_callout"))
        )
        lower_row.addWidget(connection_card, 3)

        guidance_card, guidance_layout = self._create_card(
            self._tr("ai_settings_quick_checks_title"),
            self._tr("ai_settings_quick_checks_subtitle"),
        )
        guidance_layout.addWidget(
            self._create_info_block(
                self._tr("ai_settings_troubleshooting_title"),
                [
                    self._tr("ai_settings_troubleshooting_model"),
                    self._tr("ai_settings_troubleshooting_endpoint"),
                    self._tr("ai_settings_troubleshooting_timeout"),
                ],
            )
        )
        lower_row.addWidget(guidance_card, 2)

        layout.addLayout(lower_row)
        layout.addStretch()
        return widget

    def _create_cloud_tab(self):
        """Create cloud settings tab."""
        widget, layout = self._create_page_shell()

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(12)

        provider_card, provider_layout = self._create_card(
            self._tr("ai_settings_provider_connection_title"),
            self._tr("ai_settings_provider_connection_subtitle"),
        )
        form = self._create_form_layout()

        # Provider selection
        self._cloud_provider = QComboBox()
        self._cloud_provider.setMinimumWidth(220)
        self._cloud_provider.addItems(self._translated_option_labels(self.CLOUD_PROVIDER_OPTIONS))
        current_cloud = self._current_settings.get('cloud', {}).get(
            'provider',
            self._current_settings.get('provider', 'openai'),
        )
        self._set_combo_by_value(self._cloud_provider, self.CLOUD_PROVIDER_OPTIONS, current_cloud)
        self._cloud_provider.currentIndexChanged.connect(self._on_cloud_provider_changed)
        self._add_form_row(form, self._tr("ai_settings_provider"), self._cloud_provider)

        # API Key
        self._cloud_api_key = QLineEdit()
        self._cloud_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cloud_api_key.setPlaceholderText("sk-...")
        self._cloud_api_key.setClearButtonEnabled(True)
        self._cloud_api_key.setText(self._current_settings.get('cloud', {}).get('api_key', ''))
        self._add_form_row(form, self._tr("ai_settings_api_key"), self._cloud_api_key)

        # Base URL (for proxy)
        self._cloud_base_url = QLineEdit()
        self._cloud_base_url.setClearButtonEnabled(True)
        self._cloud_base_url.setMinimumWidth(320)
        self._cloud_base_url.setText(self._current_settings.get('cloud', {}).get('base_url', ''))
        self._add_form_row(form, self._tr("ai_settings_base_url"), self._cloud_base_url)

        # Model
        self._cloud_model = QComboBox()
        self._cloud_model.setEditable(True)
        self._cloud_model.setMinimumWidth(220)
        current_model = self._current_settings.get('cloud', {}).get('model', 'gpt-4o')
        self._populate_cloud_models(current_cloud, current_model)
        self._add_form_row(form, self._tr("ai_settings_model"), self._cloud_model)

        provider_layout.addLayout(form)
        provider_layout.addWidget(
            self._create_callout(
                self._tr("ai_settings_custom_base_url_callout")
            )
        )
        content_row.addWidget(provider_card, 3)

        defaults_card, defaults_layout = self._create_card(
            self._tr("ai_settings_generation_defaults_title"),
            self._tr("ai_settings_generation_defaults_subtitle"),
        )
        defaults_form = self._create_form_layout()

        # Temperature
        self._cloud_temp = QDoubleSpinBox()
        self._cloud_temp.setRange(0.0, 2.0)
        self._cloud_temp.setSingleStep(0.1)
        self._cloud_temp.setDecimals(1)
        self._cloud_temp.setValue(float(self._current_settings.get('cloud', {}).get('temperature', 0.7)))
        self._add_form_row(defaults_form, self._tr("ai_settings_temperature"), self._cloud_temp)

        # Max tokens
        self._cloud_tokens = QSpinBox()
        self._cloud_tokens.setRange(256, 32768)
        self._cloud_tokens.setSingleStep(256)
        self._cloud_tokens.setValue(self._current_settings.get('cloud', {}).get('max_tokens', 4096))
        self._add_form_row(defaults_form, self._tr("ai_settings_max_tokens"), self._cloud_tokens)

        defaults_layout.addLayout(defaults_form)
        defaults_layout.addWidget(
            self._create_info_block(
                self._tr("ai_settings_compatibility_title"),
                [
                    self._tr("ai_settings_compatibility_minimax"),
                    self._tr("ai_settings_compatibility_glm"),
                    self._tr("ai_settings_compatibility_editable_models"),
                ],
            )
        )
        content_row.addWidget(defaults_card, 2)

        layout.addLayout(content_row)
        layout.addStretch()
        self._on_cloud_provider_changed(self._cloud_provider.currentIndex())
        return widget

    def _create_page_shell(self) -> tuple[QWidget, QVBoxLayout]:
        """Create a transparent page container for one tab."""
        widget = QWidget()
        widget.setObjectName("aiSettingsPage")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        widget.setLayout(layout)
        return widget, layout

    def _create_card(self, title: str, subtitle: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a reusable settings card."""
        card = QFrame(self)
        card.setObjectName("aiSettingsSectionCard")

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("aiSettingsCardTitle")
        title_column.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("aiSettingsCardSubtitle")
            subtitle_label.setWordWrap(True)
            title_column.addWidget(subtitle_label)

        layout.addLayout(title_column)
        card.setLayout(layout)
        return card, layout

    def _create_form_layout(self) -> QFormLayout:
        """Create a shared form layout for settings cards."""
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        return form

    def _add_form_row(self, layout: QFormLayout, label_text: str, field: QWidget) -> None:
        """Add a labeled row with dialog-specific label styling."""
        label = QLabel(f"{label_text}:")
        label.setObjectName("aiSettingsFieldLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addRow(label, field)

    def _create_info_block(self, title: str, items: list[str]) -> QFrame:
        """Create a compact read-only guidance block."""
        frame = QFrame(self)
        frame.setObjectName("aiSettingsInfoBlock")

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("aiSettingsInfoTitle")
        layout.addWidget(title_label)

        for item in items:
            item_label = QLabel(f"• {item}")
            item_label.setObjectName("aiSettingsInfoItem")
            item_label.setWordWrap(True)
            layout.addWidget(item_label)

        frame.setLayout(layout)
        return frame

    def _create_callout(self, text: str) -> QLabel:
        """Create a subdued inline hint label."""
        label = QLabel(text)
        label.setObjectName("aiSettingsCallout")
        label.setWordWrap(True)
        return label

    def _tr(self, key: str, *args) -> str:
        """Translate a dialog string using the shared i18n registry."""
        return tr(key, *args)

    def _translated_option_labels(self, options: list[tuple[str, str]]) -> list[str]:
        """Translate the display labels for combo-box options."""
        return [self._tr(label_key) for _, label_key in options]

    def _set_status_state(self, label: QLabel, state: str) -> None:
        """Update the semantic status chrome for inline result labels."""
        label.setProperty("state", state)
        style = label.style()
        if style is not None:
            style.unpolish(label)
            style.polish(label)
        label.update()

    def _build_stylesheet(self) -> str:
        """Return dialog-local QSS aligned with the workspace chrome."""
        return f"""
            QDialog#aiSettingsDialog {{
                background-color: {CHROME.workspace_bg};
                color: {CHROME.text_primary};
            }}
            QDialog#aiSettingsDialog QLabel {{
                background: transparent;
                border: none;
            }}
            QFrame#aiSettingsFooter {{
                border-top: 1px solid {CHROME.border};
            }}
            QTabWidget#aiSettingsTabs::pane {{
                background: transparent;
                border: none;
                margin-top: 8px;
            }}
            QTabWidget#aiSettingsTabs QWidget#aiSettingsPage {{
                background: transparent;
            }}
            QTabWidget#aiSettingsTabs QTabBar::tab {{
                background-color: {CHROME.surface};
                color: {CHROME.text_muted};
                border: 1px solid {CHROME.border};
                border-radius: 11px;
                padding: 8px 14px;
                min-width: 96px;
                margin-right: 6px;
                font-weight: 700;
            }}
            QTabWidget#aiSettingsTabs QTabBar::tab:selected {{
                background-color: {CHROME.accent_surface};
                color: {CHROME.text_primary};
                border-color: {CHROME.accent_surface_strong};
            }}
            QTabWidget#aiSettingsTabs QTabBar::tab:hover:!selected {{
                background-color: {CHROME.surface_hover};
                color: {CHROME.text_primary};
            }}
            QFrame#aiSettingsSectionCard {{
                background-color: {CHROME.surface};
                border: 1px solid {CHROME.border};
                border-radius: 14px;
            }}
            QLabel#aiSettingsCardTitle {{
                color: {CHROME.text_primary};
                font-size: 12px;
                font-weight: 700;
            }}
            QLabel#aiSettingsCardSubtitle {{
                color: {CHROME.text_muted};
                font-size: 10px;
                font-weight: 500;
            }}
            QLabel#aiSettingsFieldLabel {{
                color: {CHROME.text_secondary};
                font-size: 11px;
                font-weight: 600;
                min-width: 118px;
            }}
            QLabel#aiSettingsCallout {{
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_secondary};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
                padding: 8px 10px;
                font-size: 10px;
                font-weight: 500;
            }}
            QFrame#aiSettingsInfoBlock {{
                background-color: {CHROME.surface_alt};
                border: 1px solid {CHROME.border};
                border-radius: 12px;
            }}
            QLabel#aiSettingsInfoTitle {{
                color: {CHROME.text_primary};
                font-size: 11px;
                font-weight: 700;
            }}
            QLabel#aiSettingsInfoItem {{
                color: {CHROME.text_secondary};
                font-size: 10px;
                font-weight: 500;
            }}
            QDialog#aiSettingsDialog QLineEdit,
            QDialog#aiSettingsDialog QComboBox,
            QDialog#aiSettingsDialog QSpinBox,
            QDialog#aiSettingsDialog QDoubleSpinBox {{
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_primary};
                border: 1px solid {CHROME.border};
                border-radius: 10px;
                min-height: 30px;
                padding: 4px 10px;
            }}
            QDialog#aiSettingsDialog QLineEdit:hover,
            QDialog#aiSettingsDialog QComboBox:hover,
            QDialog#aiSettingsDialog QSpinBox:hover,
            QDialog#aiSettingsDialog QDoubleSpinBox:hover {{
                border-color: {CHROME.border_strong};
            }}
            QDialog#aiSettingsDialog QLineEdit:focus,
            QDialog#aiSettingsDialog QComboBox:focus,
            QDialog#aiSettingsDialog QSpinBox:focus,
            QDialog#aiSettingsDialog QDoubleSpinBox:focus {{
                border-color: {CHROME.accent};
            }}
            QDialog#aiSettingsDialog QComboBox {{
                padding-right: 28px;
            }}
            QDialog#aiSettingsDialog QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border: none;
                background: transparent;
            }}
            QDialog#aiSettingsDialog QComboBox::down-arrow {{
                margin-right: 8px;
            }}
            QDialog#aiSettingsDialog QCheckBox {{
                color: {CHROME.text_primary};
                spacing: 10px;
                font-size: 12px;
                font-weight: 700;
            }}
            QDialog#aiSettingsDialog QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 1px solid {CHROME.border_strong};
                background-color: {CHROME.surface_alt};
            }}
            QDialog#aiSettingsDialog QCheckBox::indicator:checked {{
                background-color: {CHROME.accent};
                border-color: {CHROME.accent};
            }}
            QPushButton#aiSettingsSecondaryButton {{
                min-width: 132px;
            }}
            QLabel#aiSettingsStatusLabel {{
                border-radius: 9px;
                border: 1px solid {CHROME.border};
                background-color: {CHROME.surface_alt};
                color: {CHROME.text_muted};
                padding: 6px 10px;
                font-size: 10px;
                font-weight: 700;
            }}
            QLabel#aiSettingsStatusLabel[state="pending"] {{
                color: {CHROME.warning};
                border-color: #6A5630;
                background-color: #302514;
            }}
            QLabel#aiSettingsStatusLabel[state="success"] {{
                color: {CHROME.success};
                border-color: #2E6B5A;
                background-color: #172E28;
            }}
            QLabel#aiSettingsStatusLabel[state="error"] {{
                color: {CHROME.danger};
                border-color: #6F3F39;
                background-color: #2C1716;
            }}
            QDialogButtonBox#aiSettingsActions QPushButton {{
                min-width: 92px;
                min-height: 30px;
            }}
        """

    def _on_test_local(self):
        """Test local connection."""
        self._local_test_result.setText(self._tr("ai_settings_testing_endpoint"))
        self._set_status_state(self._local_test_result, "pending")

        import httpx
        endpoint = self._local_endpoint.text().rstrip('/')

        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{endpoint}/api/tags")
                if response.status_code == 200:
                    self._local_test_result.setText(self._tr("ai_settings_connected"))
                    self._set_status_state(self._local_test_result, "success")
                else:
                    self._local_test_result.setText(f"HTTP {response.status_code}")
                    self._set_status_state(self._local_test_result, "error")
        except Exception as e:
            self._local_test_result.setText(str(e)[:48] or self._tr("ai_settings_connection_failed"))
            self._set_status_state(self._local_test_result, "error")

    def _on_ok(self):
        """Handle OK button."""
        self.accept()

    def _set_combo_by_value(self, combo: QComboBox, options: list[tuple[str, str]], value: str) -> None:
        """Set a combo box index based on its logical value."""
        target_value = str(value or "").strip().lower()
        for index, (option_value, _label) in enumerate(options):
            if option_value == target_value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _combo_value(self, combo: QComboBox, options: list[tuple[str, str]]) -> str:
        """Return the logical value for a combo box."""
        index = combo.currentIndex()
        if 0 <= index < len(options):
            return options[index][0]
        return options[0][0]

    def _on_general_provider_changed(self, index: int) -> None:
        """Keep the cloud-provider form aligned when a cloud route is selected globally."""
        del index
        provider = self._combo_value(self._provider_combo, self.GENERAL_PROVIDER_OPTIONS)
        if provider == "local" or not hasattr(self, "_cloud_provider"):
            return
        self._set_combo_by_value(self._cloud_provider, self.CLOUD_PROVIDER_OPTIONS, provider)

    def _populate_cloud_models(self, provider: str, current_model: str = "") -> None:
        """Refresh the cloud-model list for the selected provider."""
        defaults = self.CLOUD_PROVIDER_DEFAULTS.get(provider, self.CLOUD_PROVIDER_DEFAULTS["openai"])
        models = defaults.get("models", [])
        selected_model = str(current_model or "").strip()

        blocked = self._cloud_model.blockSignals(True)
        self._cloud_model.clear()
        self._cloud_model.addItems(models)
        if selected_model:
            index = self._cloud_model.findText(selected_model)
            if index >= 0:
                self._cloud_model.setCurrentIndex(index)
            else:
                self._cloud_model.setEditText(selected_model)
        elif models:
            self._cloud_model.setCurrentIndex(0)
        self._cloud_model.blockSignals(blocked)

    def _on_cloud_provider_changed(self, index: int) -> None:
        """Update provider-specific cloud defaults when the combo changes."""
        provider = self._combo_value(self._cloud_provider, self.CLOUD_PROVIDER_OPTIONS)
        defaults = self.CLOUD_PROVIDER_DEFAULTS.get(provider, self.CLOUD_PROVIDER_DEFAULTS["openai"])
        known_urls = {entry["base_url"] for entry in self.CLOUD_PROVIDER_DEFAULTS.values()}
        known_models = {
            model
            for entry in self.CLOUD_PROVIDER_DEFAULTS.values()
            for model in entry.get("models", [])
        }

        current_base_url = self._cloud_base_url.text().strip()
        new_base_url = defaults["base_url"]
        self._cloud_base_url.setPlaceholderText(new_base_url)
        if not current_base_url or current_base_url in known_urls:
            self._cloud_base_url.setText(new_base_url)

        current_model = self._cloud_model.currentText().strip()
        selected_model = ""
        if current_model and current_model not in known_models:
            selected_model = current_model
        self._populate_cloud_models(provider, selected_model)
        self._apply_cloud_temperature_constraints(provider)

    def _apply_cloud_temperature_constraints(self, provider: str) -> None:
        """Apply provider-specific temperature limits."""
        if provider == "minimax":
            self._cloud_temp.setRange(0.1, 1.0)
            self._cloud_temp.setToolTip(self._tr("ai_settings_compatibility_minimax"))
        else:
            self._cloud_temp.setRange(0.0, 2.0)
            self._cloud_temp.setToolTip("")

        value = self._cloud_temp.value()
        if value < self._cloud_temp.minimum():
            self._cloud_temp.setValue(self._cloud_temp.minimum())
        elif value > self._cloud_temp.maximum():
            self._cloud_temp.setValue(self._cloud_temp.maximum())

    def get_settings(self) -> dict:
        """Get current settings."""
        selected_provider = self._combo_value(self._provider_combo, self.GENERAL_PROVIDER_OPTIONS)
        selected_cloud_provider = self._combo_value(self._cloud_provider, self.CLOUD_PROVIDER_OPTIONS)
        effective_cloud_provider = selected_provider if selected_provider != "local" else selected_cloud_provider

        settings = {
            'enabled': self._enable_ai.isChecked(),
            'provider': selected_provider,
            'local': {
                'endpoint': self._local_endpoint.text(),
                'model': self._local_model.currentText(),
                'temperature': self._local_temp.value(),
                'max_tokens': self._local_tokens.value(),
                'timeout': self._local_timeout.value(),
            },
            'cloud': {
                'provider': effective_cloud_provider,
                'api_key': self._cloud_api_key.text(),
                'base_url': self._cloud_base_url.text(),
                'model': self._cloud_model.currentText(),
                'temperature': self._cloud_temp.value(),
                'max_tokens': self._cloud_tokens.value(),
            }
        }
        return settings
