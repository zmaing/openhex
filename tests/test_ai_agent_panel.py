"""
UI tests for the AI agent sidebar panel.
"""

from __future__ import annotations

import os
import tempfile
import time

from PyQt6.QtTest import QTest

from src.ai.agent import ChatMessage
from src.app import OpenHexApp
from src.main import OpenHexMainWindow


class FakeProvider:
    """Scripted provider used by the AI panel tests."""

    def __init__(self, responses, delay: float = 0.0):
        self._responses = list(responses)
        self._delay = delay
        self.calls = []

    @property
    def provider_name(self):
        return "FakeProvider"

    @property
    def settings(self):
        class _Settings:
            model = "fake-ui-model"

        return _Settings()

    def complete(self, messages):
        self.calls.append(messages)
        if self._delay:
            time.sleep(self._delay)
        if not self._responses:
            raise AssertionError("No scripted responses left.")
        return self._responses.pop(0)

    def cancel(self):
        pass


def _wait_until(predicate, timeout_ms: int = 1000):
    app = OpenHexApp.instance()
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
    return predicate()


def _write_temp_file(payload: bytes) -> str:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    try:
        handle.write(payload)
        return handle.name
    finally:
        handle.close()


def test_ai_agent_panel_updates_running_state_and_messages():
    """Sending a prompt through the panel should update running state and transcript."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        panel = window._hex_editor._ai_panel_widget
        window._hex_editor._ai_manager.set_provider_factory(
            lambda: FakeProvider(
                ['{"type":"assistant","content":"Inspection finished."}'],
                delay=0.15,
            )
        )

        panel._composer.setPlainText("Inspect the active file")
        panel._on_send_clicked()

        assert _wait_until(lambda: panel._stop_button.isEnabled(), timeout_ms=300)
        assert panel._composer.isReadOnly()

        assert _wait_until(
            lambda: any(message.kind == "assistant" for message in panel.session.messages),
            timeout_ms=1200,
        )
        assert _wait_until(lambda: not panel._runner.is_running, timeout_ms=500)
        assert not panel._stop_button.isEnabled()
        assert not panel._composer.isReadOnly()
        assert [message.kind for message in panel.session.messages if message.kind != "thinking"] == [
            "user",
            "assistant",
        ]
    finally:
        window.close()


def test_ai_menu_actions_submit_prompt_into_agent_panel():
    """Legacy AI menu actions should focus the agent panel and create a user turn."""
    app = OpenHexApp.instance()
    file_path = _write_temp_file(bytes([0xAA, 0xBB, 0xCC, 0xDD]))
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        panel = editor._ai_panel_widget
        editor.open_file(file_path)
        editor._get_current_hex_view().select_offset_range(0, 2)
        editor._ai_manager.set_provider_factory(
            lambda: FakeProvider(['{"type":"assistant","content":"Selection inspected."}'])
        )

        window._on_analyze()

        assert _wait_until(
            lambda: any(message.kind == "assistant" for message in panel.session.messages),
            timeout_ms=1000,
        )
        assert _wait_until(lambda: not panel._runner.is_running, timeout_ms=500)
        assert editor.is_ai_panel_visible()
        assert editor._active_panel_id == "ai"
        assert panel.session.messages[0].kind == "user"
        assert "current selection" in panel.session.messages[0].content.lower()
        assert panel.session.messages[-1].kind == "assistant"
    finally:
        window.close()
        os.unlink(file_path)


def test_ai_agent_panel_compose_prompt_adds_continue_style_attachments():
    """Composer attachments should enrich the model prompt without changing the visible user text."""
    app = OpenHexApp.instance()
    file_path = _write_temp_file(bytes([0xAA, 0xBB, 0xCC, 0xDD]))
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        panel = editor._ai_panel_widget
        editor.open_file(file_path)
        editor._get_current_hex_view().select_offset_range(0, 2)

        provider = FakeProvider(['{"type":"assistant","content":"Selection inspected."}'])
        editor._ai_manager.set_provider_factory(lambda: provider)

        panel._attach_builtin_context("selection")
        panel._composer.setPlainText("Analyze payload")
        panel._set_max_steps(12)
        panel._on_send_clicked()

        assert _wait_until(
            lambda: any(message.kind == "assistant" for message in panel.session.messages),
            timeout_ms=1000,
        )
        assert panel.session.messages[0].content == "Analyze payload"
        assert "Attached context:" in provider.calls[0][-1]["content"]
        assert "read_selection" in provider.calls[0][-1]["content"]
        assert "Pinned active file:" in provider.calls[0][-1]["content"]
        assert panel._runner._max_steps == 12
    finally:
        window.close()
        os.unlink(file_path)


def test_ai_agent_panel_disables_navigation_tools_by_default():
    """The Continue-style panel should not expose navigation tools to the runner by default."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        panel = window._hex_editor._ai_panel_widget
        assert not panel._allow_navigation_tools
        assert panel._runner._disabled_tool_names == {"activate_file", "navigate_to_offset", "select_range"}
    finally:
        window.close()


def test_ai_agent_panel_inline_model_selector_updates_active_settings():
    """Selecting a model from the inline dropdown should update the active manager settings."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        panel = editor._ai_panel_widget
        app._ai_settings = {
            "enabled": True,
            "provider": "local",
            "local": {
                "endpoint": "http://localhost:11434",
                "model": "qwen:7b",
                "temperature": 0.7,
                "max_tokens": 4096,
                "timeout": 60,
            },
            "cloud": {
                "provider": "openai",
                "api_key": "",
                "base_url": "",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 4096,
                "timeout": 60,
            },
        }
        editor._ai_manager.configure(app._ai_settings)
        panel.refresh_provider_status()

        panel._select_model("llama3:8b")

        assert editor._ai_manager.current_model_name == "llama3:8b"
        assert app._ai_settings["local"]["model"] == "llama3:8b"
        assert panel._model_button.text() == "llama3:8b v"
    finally:
        window.close()


def test_ai_agent_panel_compose_prompt_supports_path_attachments_and_deep_thinking():
    """Path attachments and the deep-thinking toggle should be reflected in the composed model prompt."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "sample.bin")
        with open(file_path, "wb") as handle:
            handle.write(b"\x01\x02\x03\x04")

        try:
            panel = window._hex_editor._ai_panel_widget
            file_descriptor = panel._path_attachment_descriptor(file_path)
            folder_descriptor = panel._folder_attachment_descriptor(temp_dir)

            assert file_descriptor is not None
            assert folder_descriptor is not None

            panel._add_manual_attachment(file_descriptor)
            panel._add_manual_attachment(folder_descriptor)
            panel._set_deep_thinking_enabled(True)

            model_prompt, display_prompt = panel._compose_prompt("Compare the attached paths")

            assert display_prompt == "Compare the attached paths"
            assert "Deep thinking is enabled." in model_prompt
            assert file_path in model_prompt
            assert temp_dir in model_prompt
        finally:
            window.close()


def test_ai_agent_panel_groups_reasoning_messages_into_single_trace_card():
    """Thinking, tool calls, and tool results should be grouped into one reasoning card."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        panel = window._hex_editor._ai_panel_widget

        panel._append_message(ChatMessage(kind="user", role="user", content="Analyze"))
        panel._append_message(
            ChatMessage(
                kind="thinking",
                role="system",
                content="Thinking (step 1/8)",
                metadata={"step": 1},
            )
        )
        panel._append_message(
            ChatMessage(
                kind="tool_call",
                role="assistant",
                content='{"tool_name":"get_file_metadata","arguments":{"target":"sample.bin"}}',
                metadata={
                    "tool_name": "get_file_metadata",
                    "arguments": {"target": "sample.bin"},
                    "step": 1,
                },
            )
        )
        panel._append_message(
            ChatMessage(
                kind="tool_result",
                role="tool",
                content='{"success": true, "size": 4}',
                metadata={
                    "tool_name": "get_file_metadata",
                    "success": True,
                    "data": {"size": 4},
                    "step": 1,
                },
                collapsed=True,
            )
        )
        panel._append_message(ChatMessage(kind="assistant", role="assistant", content="Done"))

        assert len(panel._message_cards) == 3
        trace_card = panel._message_cards[1]
        assert hasattr(trace_card, "_event_rows")
        assert len(trace_card._event_rows) == 3
        assert trace_card._count_label.text() == "3 steps"
    finally:
        window.close()
