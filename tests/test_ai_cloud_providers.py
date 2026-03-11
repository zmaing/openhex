"""
Regression tests for cloud-provider support in the AI manager and settings dialog.
"""

from src.ai.base import AIProvider
from src.ai.cloud import CloudAI
from src.ai.manager import AIManager
from src.app import OpenHexApp
from src.ui.dialogs.ai_settings import AISettingsDialog


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
