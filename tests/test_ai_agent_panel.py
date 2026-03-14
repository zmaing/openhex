"""
UI tests for the AI agent sidebar panel.
"""

from __future__ import annotations

import os
import tempfile
import time

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from src.ai.agent import ChatMessage
from src.app import OpenHexApp
from src.main import OpenHexMainWindow
from src.ui.panels.ai_agent import AIAgentPanel
from src.utils.i18n import get_language, set_language, tr


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


class FakeStatusManager:
    """Minimal AI manager stub for layout-focused panel tests."""

    def __init__(self, provider_name: str = "MiniMax", model_name: str = "claude-sonnet-4-20250514"):
        self.current_provider_name = provider_name
        self.current_model_name = model_name

    def status_text(self):
        return f"{self.current_provider_name}: {self.current_model_name}"


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


def test_ai_agent_panel_compacts_footer_controls_when_visible_sidebar_is_narrow():
    """Visible narrow panels should shorten footer labels instead of squeezing the send button."""
    app = OpenHexApp.instance()
    panel = AIAgentPanel(ai_manager=FakeStatusManager())
    panel.setFixedWidth(280)
    panel.resize(280, 480)
    panel.show()
    app.processEvents()

    try:
        assert _wait_until(
            lambda: panel._send_button.text() == AIAgentPanel.COMPACT_SEND_GLYPH,
            timeout_ms=300,
        )
        assert panel._thinking_button.text() == AIAgentPanel.COMPACT_THINKING_GLYPH
        assert panel._model_button.text() != "claude-sonnet-4-20250514 v"
        assert panel._send_button.width() <= AIAgentPanel.COMPACT_SEND_BUTTON_SIZE + 2
        assert panel._send_button.height() <= AIAgentPanel.COMPACT_SEND_BUTTON_SIZE + 2
        assert abs(panel._send_button.width() - panel._send_button.height()) <= 2

        panel.setFixedWidth(380)
        panel.resize(380, 480)
        app.processEvents()

        assert _wait_until(lambda: panel._send_button.text() == tr("ai_panel_send"), timeout_ms=300)
        assert panel._thinking_button.text() == tr("ai_panel_deep")
        assert panel._model_button.text().endswith(" v")
        assert panel._send_button.width() > AIAgentPanel.COMPACT_SEND_BUTTON_SIZE
    finally:
        panel.close()


def test_ai_agent_panel_deep_thinking_uses_tooltip_instead_of_status_hint():
    """Deep-thinking toggles should update the bulb tooltip without surfacing a status banner."""
    app = OpenHexApp.instance()
    panel = AIAgentPanel(ai_manager=FakeStatusManager())
    panel.setFixedWidth(280)
    panel.resize(280, 480)
    panel.show()
    app.processEvents()

    try:
        assert panel._thinking_button.toolTip() == tr("ai_panel_deep_off")

        panel._set_deep_thinking_enabled(True)
        app.processEvents()

        assert panel._thinking_button.toolTip() == tr("ai_panel_deep_on")
        assert not panel._status_hint.isVisible()
        assert panel._status_hint.text() == ""
    finally:
        panel.close()


def test_ai_agent_panel_uses_styled_hint_bubble_for_composer_icons():
    """Composer icon hints should use the custom anchored bubble instead of a plain tooltip."""
    app = OpenHexApp.instance()
    panel = AIAgentPanel(ai_manager=FakeStatusManager())
    panel.setFixedWidth(320)
    panel.resize(320, 480)
    panel.show()
    app.processEvents()

    try:
        panel._show_composer_hint(panel._mention_button)

        assert panel._hint_bubble is not None
        assert tr("ai_panel_hint_attach_title") == panel._hint_bubble._title_label.text()
        flags = panel._hint_bubble.windowFlags()
        assert panel._hint_bubble.windowType() == Qt.WindowType.Tool
        assert bool(flags & Qt.WindowType.Tool)
        assert bool(flags & Qt.WindowType.NoDropShadowWindowHint)

        panel._hide_composer_hint()
        app.processEvents()

        assert not panel._hint_bubble.isVisible()
    finally:
        panel.close()


def test_ai_agent_panel_opens_custom_model_picker_without_hover_tooltip():
    """The model button should open the custom picker and avoid a separate hover tooltip."""
    app = OpenHexApp.instance()
    panel = AIAgentPanel(ai_manager=FakeStatusManager("Local LLM", "qwen:7b"))
    panel.setFixedWidth(320)
    panel.resize(320, 480)
    panel.show()
    app.processEvents()

    try:
        assert panel._model_button.toolTip() == ""

        panel._toggle_model_menu()
        app.processEvents()

        assert panel._model_menu is not None
        assert panel._model_menu._title_label.text() == tr("ai_panel_model_picker_title")
        assert panel._model_menu.width() <= 272
        assert panel._model_menu.width() < panel.width() - 24
        assert panel._model_menu.height() < 340
        assert len(panel._model_menu._option_rows) >= 1
        assert panel._model_menu._option_rows[0]._label.text() == "qwen:7b"
    finally:
        panel.close()


def test_ai_agent_panel_opens_custom_mode_picker_and_applies_selection():
    """The mode button should reuse the model picker's popup chrome and behavior."""
    app = OpenHexApp.instance()
    panel = AIAgentPanel(ai_manager=FakeStatusManager("Local LLM", "qwen:7b"))
    panel.setFixedWidth(320)
    panel.resize(320, 480)
    panel.show()
    app.processEvents()

    try:
        assert panel._mode_button.text().startswith(tr("ai_panel_mode_chat"))

        panel._toggle_mode_menu()
        app.processEvents()

        assert panel._mode_menu is not None
        assert panel._mode_menu._title_label.text() == tr("ai_panel_mode_picker_title")
        assert panel._mode_menu.width() <= 172
        assert panel._mode_menu.width() < panel.width() - 120
        assert panel._mode_menu.height() < 340
        assert len(panel._mode_menu._mode_rows) == 2
        assert panel._mode_menu._mode_rows[0]._label.text() == tr("ai_panel_mode_chat")
        assert panel._mode_menu._mode_rows[0].height() == 34
        assert bool(
            panel._mode_menu._mode_rows[0]._check_label.alignment()
            & Qt.AlignmentFlag.AlignRight
        )
        assert panel._mode_menu._mode_rows[0]._checked is True
        assert panel._mode_menu._mode_rows[1]._checked is False

        panel._mode_menu._on_option_clicked("agent")
        app.processEvents()

        assert panel._interaction_mode == "agent"
        assert panel._mode_button.text().startswith(tr("ai_panel_mode_agent"))
    finally:
        panel.close()


def test_ai_agent_panel_command_bar_seeds_context_aware_prompts():
    """The top command bar should fill the composer with the matching quick prompt."""
    app = OpenHexApp.instance()
    file_path = _write_temp_file(bytes([0xAA, 0xBB, 0xCC, 0xDD]))
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        panel = editor._ai_panel_widget
        editor.open_file(file_path)
        editor._get_current_hex_view().select_offset_range(0, 2)
        panel._refresh_context_controls()
        app.processEvents()

        assert not panel._command_bar.isHidden()
        assert panel._config_button.text() == f"{tr('ai_panel_config')} v"
        assert panel._command_buttons["current_file"].isEnabled()
        assert panel._command_buttons["selection"].isEnabled()

        QTest.mouseClick(panel._command_buttons["selection"], Qt.MouseButton.LeftButton)
        app.processEvents()

        assert panel._composer.toPlainText() == panel._prompt_suggestion("Analyze Selection")
    finally:
        window.close()
        os.unlink(file_path)


def test_ai_agent_panel_config_menu_updates_inline_settings_and_opens_dialog():
    """The command-bar config menu should expose composer settings and the dialog entrypoint."""
    app = OpenHexApp.instance()
    panel = AIAgentPanel(ai_manager=FakeStatusManager())
    panel.show()
    app.processEvents()

    opened_settings = []
    panel.open_settings_requested.connect(lambda: opened_settings.append(True))

    try:
        panel._populate_config_menu()
        actions = panel._config_menu.actions()

        pin_action = next(action for action in actions if action.text() == tr("ai_panel_pin_active_file"))
        deep_action = next(action for action in actions if action.text() == tr("ai_panel_deep_thinking"))
        settings_action = next(action for action in actions if action.text() == tr("ai_panel_settings"))
        steps_action = next(action for action in actions if action.text() == tr("ai_panel_max_steps"))
        step_12_action = next(
            action for action in steps_action.menu().actions() if action.text() == tr("ai_panel_steps_label", 12)
        )

        assert pin_action.isChecked()
        assert not deep_action.isChecked()

        pin_action.trigger()
        deep_action.trigger()
        step_12_action.trigger()
        settings_action.trigger()
        app.processEvents()

        assert not panel._pin_active_file
        assert panel._deep_thinking_enabled
        assert panel._thinking_button.isChecked()
        assert panel._max_steps == 12
        assert opened_settings == [True]
    finally:
        panel.close()


def test_ai_agent_panel_workspace_tabs_follow_primary_and_subagent_topology():
    """Workspace tabs should default to the primary agent and expand when subagents are enabled."""
    app = OpenHexApp.instance()
    panel = AIAgentPanel(ai_manager=FakeStatusManager())
    panel.show()
    app.processEvents()

    try:
        default_tabs = [
            panel._workspace_view_bar.tabText(index)
            for index in range(panel._workspace_view_bar.count())
        ]
        assert default_tabs == [tr("ai_panel_consensus"), tr("ai_panel_main_agent"), tr("ai_panel_evidence")]
        assert panel._agent_topology_label.text() == tr("ai_panel_topology", 0)

        panel._set_subagent_enabled("subagent_a", True)
        app.processEvents()

        expanded_tabs = [
            panel._workspace_view_bar.tabText(index)
            for index in range(panel._workspace_view_bar.count())
        ]
        assert expanded_tabs == [
            tr("ai_panel_consensus"),
            tr("ai_panel_main_agent"),
            tr("ai_panel_subagent_a"),
            tr("ai_panel_evidence"),
        ]
        assert panel._agent_topology_label.text() == tr("ai_panel_topology", 1)
    finally:
        panel.close()


def test_ai_agent_panel_uses_chinese_labels_when_language_is_zh():
    """The AI workspace should use translated Chinese chrome when the app language is Chinese."""
    app = OpenHexApp.instance()
    previous_language = get_language()
    set_language("zh")
    panel = AIAgentPanel(ai_manager=FakeStatusManager())
    panel.show()
    app.processEvents()

    try:
        assert panel._status_label.text() == "MiniMax"
        assert panel.layout().itemAt(0).widget().text() == tr("ai_panel_eyebrow")
        assert panel._task_combo.currentText() == tr("ai_panel_task_profile_packets")
        assert panel._lens_combo.currentText() == tr("ai_panel_lens_generic")
        assert panel._config_button.text() == f"{tr('ai_panel_config')} v"
        assert panel._send_button.text() == tr("ai_panel_send")
    finally:
        panel.close()
        set_language(previous_language)


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
        assert not editor._ai_panel_shell.isHidden()
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
    """Selecting a model from the inline dropdown should update settings silently."""
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
        panel._set_status_hint("Using qwen:14b")

        panel._select_model("llama3:8b")

        assert editor._ai_manager.current_model_name == "llama3:8b"
        assert app._ai_settings["local"]["model"] == "llama3:8b"
        assert panel._model_button.text() == "llama3:8b v"
        assert not panel._status_hint.isVisible()
        assert panel._status_hint.text() == ""
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
