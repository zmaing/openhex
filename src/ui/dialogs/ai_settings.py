"""
AI Settings Dialog

Configure AI provider settings.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QComboBox, QGroupBox,
                             QCheckBox, QSpinBox, QTabWidget, QWidget,
                             QFormLayout, QDialogButtonBox, QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal


class AISettingsDialog(QDialog):
    """
    AI Settings Dialog.

    Configure AI provider, API keys, models, etc.
    """

    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self._current_settings = current_settings or {}
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("AI Settings")
        self.resize(550, 450)

        layout = QVBoxLayout()

        # Tab widget
        tabs = QTabWidget()

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

        # Enable AI
        self._enable_ai = QCheckBox("Enable AI features")
        self._enable_ai.setChecked(self._current_settings.get('enabled', True))
        layout.addWidget(self._enable_ai)

        # Provider selection
        form = QFormLayout()

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["Local (Ollama)", "OpenAI", "Anthropic"])
        current_provider = self._current_settings.get('provider', 'local')
        if current_provider == 'openai':
            self._provider_combo.setCurrentIndex(1)
        elif current_provider == 'anthropic':
            self._provider_combo.setCurrentIndex(2)

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
        self._local_temp = QSpinBox()
        self._local_temp.setRange(0, 100)
        self._local_temp.setValue(int(self._current_settings.get('local', {}).get('temperature', 0.7) * 10))
        self._local_temp.setSuffix(" (0.0-1.0)")
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
        layout.addRow("Status:", self._local_test_result)

        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        widget.setLayout(layout)
        return widget

    def _create_cloud_tab(self):
        """Create cloud settings tab."""
        widget = QWidget()
        layout = QFormLayout()

        # Provider selection
        self._cloud_provider = QComboBox()
        self._cloud_provider.addItems(["OpenAI", "Anthropic"])
        current_cloud = self._current_settings.get('cloud', {}).get('provider', 'openai')
        if current_cloud == 'anthropic':
            self._cloud_provider.setCurrentIndex(1)
        layout.addRow("Provider:", self._cloud_provider)

        # API Key
        self._cloud_api_key = QLineEdit()
        self._cloud_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cloud_api_key.setPlaceholderText("sk-...")
        self._cloud_api_key.setText(self._current_settings.get('cloud', {}).get('api_key', ''))
        layout.addRow("API Key:", self._cloud_api_key)

        # Base URL (for proxy)
        self._cloud_base_url = QLineEdit()
        self._cloud_base_url.setPlaceholderText("https://api.openai.com/v1")
        self._cloud_base_url.setText(self._current_settings.get('cloud', {}).get('base_url', ''))
        layout.addRow("Base URL:", self._cloud_base_url)

        # Model
        self._cloud_model = QComboBox()
        self._cloud_model.addItems([
            # OpenAI
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            # Anthropic
            "claude-sonnet-4-20250514",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229"
        ])
        current_model = self._current_settings.get('cloud', {}).get('model', 'gpt-4o')
        index = self._cloud_model.findText(current_model)
        if index >= 0:
            self._cloud_model.setCurrentIndex(index)
        layout.addRow("Model:", self._cloud_model)

        # Temperature
        self._cloud_temp = QSpinBox()
        self._cloud_temp.setRange(0, 100)
        self._cloud_temp.setValue(int(self._current_settings.get('cloud', {}).get('temperature', 0.7) * 10))
        self._cloud_temp.setSuffix(" (0.0-1.0)")
        layout.addRow("Temperature:", self._cloud_temp)

        # Max tokens
        self._cloud_tokens = QSpinBox()
        self._cloud_tokens.setRange(256, 32768)
        self._cloud_tokens.setSingleStep(256)
        self._cloud_tokens.setValue(self._current_settings.get('cloud', {}).get('max_tokens', 4096))
        layout.addRow("Max Tokens:", self._cloud_tokens)

        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        widget.setLayout(layout)
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
                    self._local_test_result.setStyleSheet("color: #4ec9b0;")
                else:
                    self._local_test_result.setText(f"✗ Error: {response.status_code}")
                    self._local_test_result.setStyleSheet("color: #f14c4c;")
        except Exception as e:
            self._local_test_result.setText(f"✗ {str(e)[:30]}")
            self._local_test_result.setStyleSheet("color: #f14c4c;")

    def _on_ok(self):
        """Handle OK button."""
        self.accept()

    def get_settings(self) -> dict:
        """Get current settings."""
        provider_map = {0: "local", 1: "openai", 2: "anthropic"}
        cloud_provider_map = {0: "openai", 1: "anthropic"}

        settings = {
            'enabled': self._enable_ai.isChecked(),
            'provider': provider_map.get(self._provider_combo.currentIndex(), 'local'),
            'local': {
                'endpoint': self._local_endpoint.text(),
                'model': self._local_model.currentText(),
                'temperature': self._local_temp.value() / 10.0,
                'max_tokens': self._local_tokens.value(),
                'timeout': self._local_timeout.value(),
            },
            'cloud': {
                'provider': cloud_provider_map.get(self._cloud_provider.currentIndex(), 'openai'),
                'api_key': self._cloud_api_key.text(),
                'base_url': self._cloud_base_url.text(),
                'model': self._cloud_model.currentText(),
                'temperature': self._cloud_temp.value() / 10.0,
                'max_tokens': self._cloud_tokens.value(),
            }
        }
        return settings
