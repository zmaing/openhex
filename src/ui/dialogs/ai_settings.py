"""
AI Settings Dialog

Configure AI provider settings.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QComboBox, QGroupBox,
                             QCheckBox, QSpinBox, QDoubleSpinBox, QTabWidget, QWidget,
                             QFormLayout, QDialogButtonBox, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal

from .chrome import create_dialog_header
from ..design_system import CHROME, status_label_qss


class AISettingsDialog(QDialog):
    """
    AI Settings Dialog.

    Configure AI provider, API keys, models, etc.
    """

    settings_changed = pyqtSignal(dict)

    GENERAL_PROVIDER_OPTIONS = [
        ("local", "Local (Ollama)"),
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("minimax", "MiniMax (China)"),
        ("glm", "GLM-5"),
    ]

    CLOUD_PROVIDER_OPTIONS = [
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("minimax", "MiniMax (China)"),
        ("glm", "GLM (Zhipu)"),
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
        self.setWindowTitle("AI Settings")
        self.resize(620, 520)
        self.setObjectName("aiSettingsDialog")

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            create_dialog_header(
                "AI Settings",
                "统一管理本地模型、云端提供商和默认推理参数，让 AI 面板与菜单动作共用同一套配置。",
            )
        )

        # Tab widget
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # General tab
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")

        # Local tab
        local_tab = self._create_local_tab()
        tabs.addTab(local_tab, "Local (Ollama)")

        # Cloud tab
        cloud_tab = self._create_cloud_tab()
        tabs.addTab(cloud_tab, "Cloud API")

        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _create_general_tab(self):
        """Create general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Enable AI
        self._enable_ai = QCheckBox("Enable AI features")
        self._enable_ai.setChecked(self._current_settings.get('enabled', True))
        layout.addWidget(self._enable_ai)

        # Provider selection
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self._provider_combo = QComboBox()
        self._provider_combo.addItems([label for _, label in self.GENERAL_PROVIDER_OPTIONS])
        current_provider = self._current_settings.get('provider', 'local')
        self._set_combo_by_value(self._provider_combo, self.GENERAL_PROVIDER_OPTIONS, current_provider)

        form.addRow("Default Provider:", self._provider_combo)
        layout.addLayout(form)

        # Info text
        info = QTextEdit()
        info.setReadOnly(True)
        info.setPlainText("""
AI Features:
• Analyze Data - Understand binary data structures
• Detect Patterns - Find common patterns in data
• Generate Code - Create parsing code in C/Python/Rust

Local AI (Ollama):
• Runs on your machine - privacy friendly
• No internet required
• Download models from ollama.ai

Cloud API:
• OpenAI GPT-4 - Powerful reasoning
• Anthropic Claude - Excellent analysis
• MiniMax (China) - OpenAI-compatible endpoint
• GLM-5 / Zhipu - OpenAI-compatible endpoint
• Requires API key
        """)
        layout.addWidget(info)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_local_tab(self):
        """Create local settings tab."""
        widget = QWidget()
        layout = QFormLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        # Endpoint
        self._local_endpoint = QLineEdit(
            self._current_settings.get('local', {}).get('endpoint', 'http://localhost:11434')
        )
        self._local_endpoint.setPlaceholderText("http://localhost:11434")
        layout.addRow("API Endpoint:", self._local_endpoint)

        # Model
        self._local_model = QComboBox()
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
        layout.addRow("Model:", self._local_model)

        # Temperature
        self._local_temp = QDoubleSpinBox()
        self._local_temp.setRange(0.0, 2.0)
        self._local_temp.setSingleStep(0.1)
        self._local_temp.setDecimals(1)
        self._local_temp.setValue(float(self._current_settings.get('local', {}).get('temperature', 0.7)))
        layout.addRow("Temperature:", self._local_temp)

        # Max tokens
        self._local_tokens = QSpinBox()
        self._local_tokens.setRange(256, 32768)
        self._local_tokens.setSingleStep(256)
        self._local_tokens.setValue(self._current_settings.get('local', {}).get('max_tokens', 4096))
        layout.addRow("Max Tokens:", self._local_tokens)

        # Timeout
        self._local_timeout = QSpinBox()
        self._local_timeout.setRange(10, 300)
        self._local_timeout.setSuffix(" seconds")
        self._local_timeout.setValue(self._current_settings.get('local', {}).get('timeout', 60))
        layout.addRow("Timeout:", self._local_timeout)

        # Test button
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._on_test_local)
        layout.addRow("", test_btn)

        # Result label
        self._local_test_result = QLabel("")
        self._local_test_result.setStyleSheet(f"color: {CHROME.text_muted}; font-weight: 600;")
        layout.addRow("Status:", self._local_test_result)

        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        widget.setLayout(layout)
        return widget

    def _create_cloud_tab(self):
        """Create cloud settings tab."""
        widget = QWidget()
        layout = QFormLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)

        # Provider selection
        self._cloud_provider = QComboBox()
        self._cloud_provider.addItems([label for _, label in self.CLOUD_PROVIDER_OPTIONS])
        current_cloud = self._current_settings.get('cloud', {}).get(
            'provider',
            self._current_settings.get('provider', 'openai'),
        )
        self._set_combo_by_value(self._cloud_provider, self.CLOUD_PROVIDER_OPTIONS, current_cloud)
        self._cloud_provider.currentIndexChanged.connect(self._on_cloud_provider_changed)
        layout.addRow("Provider:", self._cloud_provider)

        # API Key
        self._cloud_api_key = QLineEdit()
        self._cloud_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cloud_api_key.setPlaceholderText("sk-...")
        self._cloud_api_key.setText(self._current_settings.get('cloud', {}).get('api_key', ''))
        layout.addRow("API Key:", self._cloud_api_key)

        # Base URL (for proxy)
        self._cloud_base_url = QLineEdit()
        self._cloud_base_url.setText(self._current_settings.get('cloud', {}).get('base_url', ''))
        layout.addRow("Base URL:", self._cloud_base_url)

        # Model
        self._cloud_model = QComboBox()
        self._cloud_model.setEditable(True)
        current_model = self._current_settings.get('cloud', {}).get('model', 'gpt-4o')
        self._populate_cloud_models(current_cloud, current_model)
        layout.addRow("Model:", self._cloud_model)

        # Temperature
        self._cloud_temp = QDoubleSpinBox()
        self._cloud_temp.setRange(0.0, 2.0)
        self._cloud_temp.setSingleStep(0.1)
        self._cloud_temp.setDecimals(1)
        self._cloud_temp.setValue(float(self._current_settings.get('cloud', {}).get('temperature', 0.7)))
        layout.addRow("Temperature:", self._cloud_temp)

        # Max tokens
        self._cloud_tokens = QSpinBox()
        self._cloud_tokens.setRange(256, 32768)
        self._cloud_tokens.setSingleStep(256)
        self._cloud_tokens.setValue(self._current_settings.get('cloud', {}).get('max_tokens', 4096))
        layout.addRow("Max Tokens:", self._cloud_tokens)

        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        widget.setLayout(layout)
        self._on_cloud_provider_changed(self._cloud_provider.currentIndex())
        return widget

    def _on_test_local(self):
        """Test local connection."""
        self._local_test_result.setText("Testing...")

        import httpx
        endpoint = self._local_endpoint.text().rstrip('/')

        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{endpoint}/api/tags")
                if response.status_code == 200:
                    self._local_test_result.setText("✓ Connected!")
                    self._local_test_result.setStyleSheet(status_label_qss(CHROME.success))
                else:
                    self._local_test_result.setText(f"✗ Error: {response.status_code}")
                    self._local_test_result.setStyleSheet(status_label_qss(CHROME.danger))
        except Exception as e:
            self._local_test_result.setText(f"✗ {str(e)[:30]}")
            self._local_test_result.setStyleSheet(status_label_qss(CHROME.danger))

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
            self._cloud_temp.setToolTip("MiniMax accepts temperature values in the range (0, 1].")
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
