"""
Regression tests for cloud-provider support in the AI manager and settings dialog.
"""

from PyQt6.QtWidgets import QDialogButtonBox, QTextEdit

from src.ai.base import AIProvider
from src.ai.cloud import CloudAI
from src.ai.manager import AIManager
from src.app import OpenHexApp
from src.ui.dialogs.ai_settings import AISettingsDialog
from src.utils.i18n import set_language


def test_ai_manager_creates_minimax_completion_provider_with_defaults():
    """MiniMax should be created as an OpenAI-compatible cloud provider with the right defaults."""
    manager = AIManager()
    manager.configure(
        {
            "enabled": True,
            "provider": "minimax",
            "local": {},
            "cloud": {
                "provider": "minimax",
                "api_key": "test-key",
                "base_url": "",
                "model": "",
                "temperature": 0.4,
                "max_tokens": 1024,
                "timeout": 45,
            },
        }
    )

    provider = manager.create_completion_provider()

    assert provider.provider == AIProvider.CLOUD_MINIMAX
    assert provider.provider_name == "MiniMax"
    assert provider.settings.base_url == "https://api.minimaxi.com/v1"
    assert provider.settings.model == "MiniMax-M2.5"


def test_ai_manager_creates_glm_completion_provider_with_defaults():
    """GLM should use the Zhipu OpenAI-compatible endpoint and glm-5 by default."""
    manager = AIManager()
    manager.configure(
        {
            "enabled": True,
            "provider": "glm",
            "local": {},
            "cloud": {
                "provider": "glm",
                "api_key": "test-key",
                "base_url": "",
                "model": "",
                "temperature": 0.5,
                "max_tokens": 2048,
                "timeout": 30,
            },
        }
    )

    provider = manager.create_completion_provider()

    assert provider.provider == AIProvider.CLOUD_GLM
    assert provider.provider_name == "GLM"
    assert provider.settings.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert provider.settings.model == "glm-5"


def test_minimax_payload_merges_system_messages_and_normalizes_parameters():
    """MiniMax payloads should use one system message and provider-safe params."""
    provider = CloudAI(provider=AIProvider.CLOUD_MINIMAX)
    provider.configure(
        model="",
        temperature=0.0,
        max_tokens=2048,
    )

    payload = provider._build_payload(
        [
            {"role": "system", "content": "System A"},
            {"role": "system", "content": "System B"},
            {"role": "user", "content": "Analyze this."},
        ]
    )

    assert payload["model"] == "MiniMax-M2.5"
    assert payload["temperature"] == 0.01
    assert payload["max_completion_tokens"] == 2048
    assert payload["reasoning_split"] is True
    assert "max_tokens" not in payload
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "System A\n\nSystem B"


def test_ai_settings_dialog_surfaces_minimax_and_glm_options():
    """The settings dialog should expose and persist MiniMax/GLM selections."""
    OpenHexApp.instance()
    dialog = AISettingsDialog(
        current_settings={
            "enabled": True,
            "provider": "minimax",
            "local": {},
            "cloud": {
                "provider": "minimax",
                "api_key": "",
                "base_url": "",
                "model": "",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        }
    )

    try:
        assert dialog._provider_combo.currentText() == "MiniMax (China)"
        assert dialog._cloud_provider.currentText() == "MiniMax (China)"
        assert dialog._cloud_base_url.text() == "https://api.minimaxi.com/v1"
        assert dialog._cloud_model.currentText() == "MiniMax-M2.5"
        assert dialog._cloud_temp.minimum() == 0.1
        assert dialog._cloud_temp.maximum() == 1.0

        dialog._provider_combo.setCurrentIndex(4)
        dialog._cloud_provider.setCurrentIndex(3)
        dialog._on_cloud_provider_changed(dialog._cloud_provider.currentIndex())

        settings = dialog.get_settings()

        assert settings["provider"] == "glm"
        assert settings["cloud"]["provider"] == "glm"
        assert settings["cloud"]["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
        assert settings["cloud"]["model"] == "glm-5"
        assert dialog._cloud_temp.minimum() == 0.0
        assert dialog._cloud_temp.maximum() == 2.0
    finally:
        dialog.close()


def test_ai_settings_dialog_uses_custom_tab_shell_without_scrollable_intro_copy():
    """The redesigned settings surface should avoid the native tab base and read-only text editor."""
    OpenHexApp.instance()
    dialog = AISettingsDialog(current_settings={"enabled": True, "provider": "local", "local": {}, "cloud": {}})

    try:
        assert dialog._tabs.tabBar().drawBase() is False
        assert dialog.minimumWidth() >= 700
        assert not dialog._tabs.widget(0).findChildren(QTextEdit)
    finally:
        dialog.close()


def test_ai_settings_dialog_syncs_cloud_fields_from_general_provider_selection():
    """Choosing a cloud provider globally should keep the cloud form fields in sync."""
    OpenHexApp.instance()
    dialog = AISettingsDialog(
        current_settings={
            "enabled": True,
            "provider": "local",
            "local": {},
            "cloud": {
                "provider": "anthropic",
                "api_key": "",
                "base_url": "",
                "model": "",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        }
    )

    try:
        dialog._provider_combo.setCurrentIndex(4)

        assert dialog._cloud_provider.currentText() == "GLM (Zhipu)"
        assert dialog._cloud_base_url.text() == "https://open.bigmodel.cn/api/paas/v4"
        assert dialog._cloud_model.currentText() == "glm-5"
    finally:
        dialog.close()


def test_ai_settings_dialog_localizes_strings_when_language_is_chinese():
    """The AI settings dialog should render translated labels when Chinese is active."""
    OpenHexApp.instance()
    set_language("zh")
    dialog = AISettingsDialog(current_settings={"enabled": True, "provider": "local", "local": {}, "cloud": {}})

    try:
        buttons = dialog.findChild(QDialogButtonBox, "aiSettingsActions")

        assert dialog.windowTitle() == "AI 设置"
        assert dialog._tabs.tabText(0) == "通用"
        assert dialog._tabs.tabText(1) == "本地 (Ollama)"
        assert dialog._tabs.tabText(2) == "云端 API"
        assert dialog._enable_ai.text() == "启用 AI 功能"
        assert dialog._provider_combo.currentText() == "本地 (Ollama)"
        assert dialog._cloud_provider.itemText(2) == "MiniMax (中国)"
        assert dialog._local_timeout.suffix() == " 秒"
        assert dialog._local_test_result.text() == "未测试"
        assert buttons is not None
        assert buttons.button(QDialogButtonBox.StandardButton.Ok).text() == "确定"
        assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "取消"
    finally:
        dialog.close()
