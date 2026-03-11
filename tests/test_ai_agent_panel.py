"""
UI tests for the AI agent sidebar panel.
"""

from __future__ import annotations

import os
import tempfile
import time

from PyQt6.QtTest import QTest

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
