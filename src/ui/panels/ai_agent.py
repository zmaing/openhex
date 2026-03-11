"""
Continue-style chat panel for the AI agent sidebar.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QSettings, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ...ai.agent import AgentRunner, AgentSession, ChatMessage


class _ChatComposer(QPlainTextEdit):
    """Small helper that emits Ctrl+Enter as submit."""

    submit_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if (
            event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.submit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _MessageCard(QFrame):
    """A single transcript card inside the agent message list."""

    COLOR_MAP = {
        "user": ("#2b579a", "#ffffff"),
        "assistant": ("#2d2d30", "#dcdcdc"),
        "thinking": ("#252526", "#9cdcfe"),
        "tool_call": ("#3a3d41", "#f0c674"),
        "tool_result": ("#1f3328", "#b5cea8"),
        "error": ("#4b1d1d", "#f48771"),
    }
    TITLE_MAP = {
        "user": "You",
        "assistant": "Assistant",
        "thinking": "Thinking",
        "tool_call": "Tool Call",
        "tool_result": "Tool Result",
        "error": "Error",
    }

    def __init__(self, message: ChatMessage, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._message = message
        self._expanded = not message.collapsed
        self._build_ui()

    def _build_ui(self) -> None:
        bg_color, fg_color = self.COLOR_MAP.get(self._message.kind, ("#2d2d30", "#dcdcdc"))
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg_color};
                color: {fg_color};
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }}
            QLabel {{
                color: {fg_color};
                background: transparent;
                border: none;
            }}
            QToolButton {{
                color: {fg_color};
                background: transparent;
                border: none;
                padding: 0;
            }}
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title = self.TITLE_MAP.get(self._message.kind, self._message.kind.title())
        if self._message.kind in {"tool_call", "tool_result"}:
            tool_name = str(self._message.metadata.get("tool_name", "")).strip()
            if tool_name:
                title = f"{title}: {tool_name}"

        self._toggle_button = None
        if self._message.collapsed:
            toggle = QToolButton(self)
            toggle.setText("▸" if not self._expanded else "▾")
            toggle.clicked.connect(self._toggle_expanded)
            header_layout.addWidget(toggle)
            self._toggle_button = toggle

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 600;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self._content_label = QLabel(self._message.content)
        self._content_label.setWordWrap(True)
        self._content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_font = QFont("Menlo", 10)
        content_font.setStyleHint(QFont.StyleHint.Monospace)
        self._content_label.setFont(content_font)
        self._content_label.setTextFormat(Qt.TextFormat.PlainText)
        self._content_label.setVisible(self._expanded)
        layout.addWidget(self._content_label)
        self.setLayout(layout)

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self._content_label.setVisible(self._expanded)
        if self._toggle_button is not None:
            self._toggle_button.setText("▾" if self._expanded else "▸")


class _AttachmentChip(QFrame):
    """Compact removable chip used for composer context attachments."""

    remove_requested = pyqtSignal(str)

    def __init__(
        self,
        attachment_id: str,
        label: str,
        *,
        removable: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._attachment_id = attachment_id
        self.setObjectName("agentAttachmentChip")

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 3, 4, 3)
        layout.setSpacing(4)

        label_widget = QLabel(label, self)
        label_widget.setStyleSheet("font-size: 10px; font-weight: 600;")
        layout.addWidget(label_widget)

        if removable:
            close_button = QToolButton(self)
            close_button.setText("x")
            close_button.setAutoRaise(True)
            close_button.clicked.connect(lambda: self.remove_requested.emit(self._attachment_id))
            layout.addWidget(close_button)

        self.setLayout(layout)


class _TraceEventRow(QFrame):
    """Compact row used inside the aggregated thinking trace card."""

    STYLE_MAP = {
        "thinking": ("Thinking", "#89d6ff", "#24303a"),
        "tool_call": ("Tool", "#f0c36d", "#362f22"),
        "tool_result": ("Result", "#9ed6a4", "#213526"),
    }

    def __init__(self, message: ChatMessage, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._message = message
        self._expanded = False
        self._build_ui()

    def _build_ui(self) -> None:
        badge_text, accent_color, background_color = self.STYLE_MAP.get(
            self._message.kind,
            ("Step", "#d0d0d0", "#2b2b30"),
        )
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {background_color};
                border: 1px solid #45454c;
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QToolButton {{
                background: transparent;
                border: none;
                color: #b9b9c0;
                padding: 0;
            }}
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        badge = QLabel(badge_text, self)
        badge.setStyleSheet(
            f"color: {accent_color}; font-size: 10px; font-weight: 700;"
        )
        header_layout.addWidget(badge)

        title = QLabel(self._title_text(), self)
        title.setWordWrap(True)
        title.setStyleSheet("color: #ececef; font-size: 10px; font-weight: 600;")
        header_layout.addWidget(title, 1)

        details_text = self._details_text().strip()
        self._toggle_button = None
        if details_text:
            toggle = QToolButton(self)
            toggle.setText("▸" if not self._expanded else "▾")
            toggle.clicked.connect(self._toggle_details)
            header_layout.addWidget(toggle)
            self._toggle_button = toggle

        layout.addLayout(header_layout)

        self._details_label = QLabel(details_text, self)
        details_font = QFont("Menlo", 9)
        details_font.setStyleHint(QFont.StyleHint.Monospace)
        self._details_label.setFont(details_font)
        self._details_label.setWordWrap(True)
        self._details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._details_label.setTextFormat(Qt.TextFormat.PlainText)
        self._details_label.setStyleSheet("color: #cfd7df; font-size: 9px;")
        self._details_label.setVisible(self._expanded)
        if details_text:
            layout.addWidget(self._details_label)

        self.setLayout(layout)

    def _title_text(self) -> str:
        step = self._message.metadata.get("step")
        if self._message.kind == "thinking":
            if isinstance(step, int):
                return f"Step {step}: {self._message.content}"
            return self._message.content

        tool_name = str(self._message.metadata.get("tool_name", "")).strip() or "tool"
        if self._message.kind == "tool_call":
            arguments = self._message.metadata.get("arguments", {})
            summary = self._summarize_arguments(arguments)
            return f"{tool_name}{summary}"

        if self._message.kind == "tool_result":
            status = "done" if self._message.metadata.get("success", True) else "failed"
            return f"{tool_name} · {status}"

        return self._message.content

    def _details_text(self) -> str:
        if self._message.kind == "thinking":
            return ""
        return str(self._message.content or "")

    def _summarize_arguments(self, arguments: Any) -> str:
        if not isinstance(arguments, dict) or not arguments:
            return ""
        parts: list[str] = []
        for key, value in list(arguments.items())[:2]:
            text = str(value)
            if len(text) > 20:
                text = text[:20] + "..."
            parts.append(f"{key}={text}")
        return f" ({', '.join(parts)})"

    def _toggle_details(self) -> None:
        self._expanded = not self._expanded
        self._details_label.setVisible(self._expanded)
        if self._toggle_button is not None:
            self._toggle_button.setText("▾" if self._expanded else "▸")


class _ThinkingTraceCard(QFrame):
    """Aggregates one assistant turn's reasoning steps inside a single transcript card."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._event_rows: list[_TraceEventRow] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QFrame {
                background-color: #242428;
                border: 1px solid #3f4047;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title = QLabel("Thinking Process", self)
        title.setStyleSheet("color: #9cdcfe; font-weight: 700; font-size: 11px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._count_label = QLabel("0 steps", self)
        self._count_label.setStyleSheet("color: #8c8c94; font-size: 10px;")
        header_layout.addWidget(self._count_label)

        layout.addLayout(header_layout)

        self._events_layout = QVBoxLayout()
        self._events_layout.setContentsMargins(0, 0, 0, 0)
        self._events_layout.setSpacing(6)
        layout.addLayout(self._events_layout)
        self.setLayout(layout)

    def add_message(self, message: ChatMessage) -> None:
        row = _TraceEventRow(message, self)
        self._events_layout.addWidget(row)
        self._event_rows.append(row)
        self._count_label.setText(f"{len(self._event_rows)} steps")


class AIAgentPanel(QWidget):
    """Chat-first AI panel that uses the agent runtime and editor tools."""

    open_settings_requested = pyqtSignal()
    NAVIGATION_TOOL_NAMES = {"activate_file", "navigate_to_offset", "select_range"}
    MODE_LABELS = {
        "chat": "Chat",
        "agent": "Agent",
    }
    MAX_STEPS_OPTIONS = (4, 8, 12)
    LOCAL_MODEL_OPTIONS = [
        "qwen:7b",
        "qwen:14b",
        "llama3:8b",
        "llama3:70b",
        "mistral:7b",
        "codellama:7b",
        "phi3:14b",
    ]
    CLOUD_MODEL_OPTIONS = {
        "openai": ["gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
        "anthropic": [
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-latest",
            "claude-3-5-sonnet-latest",
            "claude-3-opus-20240229",
        ],
        "minimax": ["MiniMax-M2.5", "MiniMax-M1"],
        "glm": ["glm-5", "glm-4.5", "glm-4.5-air", "glm-4.5-flash"],
    }
    PROVIDER_CONFIG_LABELS = {
        "local": "Local Config",
        "openai": "OpenAI Config",
        "anthropic": "Anthropic Config",
        "minimax": "MiniMax Config",
        "glm": "GLM Config",
    }
    PROMPT_SUGGESTIONS = {
        "Analyze Current File": "Analyze the active file structure and likely record layout.",
        "Analyze Selection": "Analyze the selected bytes and explain what they represent.",
        "Inspect Current Row": "Explain the current row and note any field boundaries or checksums.",
        "Find Payload Pattern": "Focus on the payload region and summarize recurring packet structure.",
    }

    def __init__(self, parent=None, ai_manager=None, tool_host=None):
        super().__init__(parent)
        self._ai_manager = ai_manager
        self._tool_host = tool_host
        self._runner: Optional[AgentRunner] = None
        self._session = AgentSession()
        self._message_cards: list[QWidget] = []
        self._active_trace_card: Optional[_ThinkingTraceCard] = None
        self._attachment_chips: list[_AttachmentChip] = []
        self._manual_attachments: list[dict[str, str]] = []
        self._interaction_mode = "chat"
        self._pin_active_file = True
        self._allow_navigation_tools = False
        self._max_steps = 8
        self._deep_thinking_enabled = False
        self._attachment_menu: Optional[QMenu] = None
        self._model_menu: Optional[QMenu] = None
        self._build_ui()
        self._set_runner(AgentRunner(ai_manager, tool_host, self) if ai_manager and tool_host else None)
        self.refresh_provider_status()
        self._refresh_context_controls()

    @property
    def session(self) -> AgentSession:
        """Return the in-memory transcript."""
        return self._session

    def set_ai_manager(self, ai_manager) -> None:
        """Update the AI manager used by the panel."""
        self._ai_manager = ai_manager
        if self._tool_host is not None:
            self._set_runner(AgentRunner(ai_manager, self._tool_host, self))
        self.refresh_provider_status()

    def set_tool_host(self, tool_host) -> None:
        """Update the agent tool host."""
        self._tool_host = tool_host
        if self._runner is not None:
            self._runner.set_tool_host(tool_host)
        elif self._ai_manager is not None:
            self._set_runner(AgentRunner(self._ai_manager, tool_host, self))
        self._refresh_context_controls()

    def set_runner(self, runner: Optional[AgentRunner]) -> None:
        """Override the runner. Intended for tests."""
        self._set_runner(runner)

    def shutdown(self) -> None:
        """Stop any in-flight worker before the panel is destroyed."""
        if self._runner is not None:
            self._runner.shutdown()

    def focus_input(self) -> None:
        """Focus the chat composer."""
        self._refresh_context_controls()
        self._composer.setFocus()

    def refresh_provider_status(self) -> None:
        """Refresh the top status line with the current provider/model."""
        if self._ai_manager is None:
            self._status_label.setText("Not configured")
            self._model_button.setText("Model v")
            return
        status_text = self._ai_manager.status_text()
        provider_name = getattr(self._ai_manager, "current_provider_name", "AI")
        model_name = getattr(self._ai_manager, "current_model_name", "") or provider_name
        self._status_label.setText(provider_name)
        self._status_label.setToolTip(status_text)
        self._model_button.setText(f"{model_name} v")
        self._model_button.setToolTip(status_text)

    def clear_session(self) -> None:
        """Reset the transcript."""
        self._session.clear()
        self._manual_attachments.clear()
        self._refresh_manual_attachment_chips()
        for card in self._message_cards:
            self._message_layout.removeWidget(card)
            card.deleteLater()
        self._message_cards.clear()
        self._active_trace_card = None
        self._placeholder.setVisible(True)
        self._set_status_hint("Session cleared")

    def submit_prompt(self, prompt: str, *, display_prompt: Optional[str] = None) -> bool:
        """Submit a prompt directly to the agent runner."""
        prompt = str(prompt or "").strip()
        if not prompt:
            return False
        if self._runner is None:
            self._append_message(ChatMessage(kind="error", role="system", content="AI runner is not configured."))
            return False
        if self._runner.is_running:
            return False
        started = self._runner.start_turn(self._session, prompt, display_prompt=display_prompt or prompt)
        if started:
            self._set_status_hint("Running")
        return started

    def send_preset_prompt(self, prompt: str) -> bool:
        """Submit a pre-filled prompt without touching the composer text."""
        model_prompt, display_prompt = self._compose_prompt(prompt)
        return self.submit_prompt(model_prompt, display_prompt=display_prompt)

    def _set_status_hint(self, text: str = "") -> None:
        """Show a lightweight transient hint only when there is something useful to say."""
        value = str(text or "").strip()
        self._status_hint.setText(value)
        self._status_hint.setVisible(bool(value))

    def _build_ui(self) -> None:
        self.setObjectName("aiAgentPanel")
        self.setStyleSheet(
            """
            QWidget#aiAgentPanel {
                background-color: #1f1f21;
                color: #e2e2e2;
            }
            QWidget#aiAgentPanel QLabel {
                background: transparent;
                border: none;
            }
            QWidget#aiAgentPanel QPlainTextEdit {
                background-color: transparent;
                color: #ececec;
                border: none;
                border-radius: 0;
                padding: 4px;
                selection-background-color: #1d5e99;
            }
            QWidget#aiAgentPanel QPushButton {
                background-color: #3a3a40;
                color: #ececec;
                border: 1px solid #4b4b53;
                border-radius: 8px;
                padding: 3px 9px;
                min-height: 24px;
                font-size: 11px;
            }
            QWidget#aiAgentPanel QPushButton:hover {
                background-color: #44444c;
            }
            QWidget#aiAgentPanel QToolButton {
                background-color: transparent;
                color: #ececec;
                border: none;
                padding: 1px 5px;
                border-radius: 6px;
                font-size: 11px;
            }
            QWidget#aiAgentPanel QToolButton:hover {
                background-color: #3a3a40;
            }
            QLabel#agentSectionTitle {
                color: #f2f2f4;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#agentPanelSubtitle {
                color: #7f7f87;
                font-size: 10px;
                padding-left: 1px;
            }
            QMenu {
                background-color: #2f2f33;
                color: #ececec;
                border: 1px solid #505057;
                border-radius: 14px;
                padding: 8px;
            }
            QMenu::item {
                border-radius: 8px;
                padding: 8px 12px;
                margin: 1px 0;
            }
            QMenu::item:selected {
                background-color: #424249;
            }
            QMenu::separator {
                height: 1px;
                background-color: #4a4a52;
                margin: 6px 2px;
            }
            QFrame#agentComposerCard {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #313136,
                    stop: 1 #2a2a2f
                );
                border: 1px solid #51515a;
                border-radius: 14px;
            }
            QPlainTextEdit#agentComposerEditor {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 1px 2px 3px 2px;
                min-height: 42px;
                max-height: 64px;
                font-size: 12px;
            }
            QToolButton#agentModeButton,
            QToolButton#agentModelButton,
            QToolButton#agentMentionButton,
            QToolButton#agentThinkingButton {
                min-height: 22px;
            }
            QToolButton#agentModeButton {
                background-color: #354051;
                border: 1px solid #46607d;
                border-radius: 11px;
                font-weight: 600;
                padding: 1px 9px;
            }
            QToolButton#agentModeButton:hover {
                background-color: #3f4d62;
            }
            QToolButton#agentModeButton::menu-indicator,
            QToolButton#agentModelButton::menu-indicator,
            QToolButton#agentMentionButton::menu-indicator {
                image: none;
                width: 0px;
            }
            QToolButton#agentModelButton {
                background-color: #313138;
                border: 1px solid #414149;
                border-radius: 8px;
                padding: 1px 8px;
                color: #d8d8dd;
                text-align: left;
            }
            QToolButton#agentModelButton:hover {
                background-color: #383840;
            }
            QToolButton#agentMentionButton,
            QToolButton#agentThinkingButton {
                background-color: #313138;
                border: 1px solid #414149;
                border-radius: 7px;
                padding: 1px 5px;
                min-width: 22px;
            }
            QToolButton#agentMentionButton:hover,
            QToolButton#agentThinkingButton:hover {
                background-color: #383840;
            }
            QToolButton#agentThinkingButton:checked {
                color: #f3d97a;
                background-color: #4b4324;
                border-color: #625933;
            }
            QWidget#agentMenuHeader {
                background: transparent;
            }
            QToolButton#agentMenuHeaderButton {
                background-color: #3f3f45;
                border: 1px solid #56565d;
                border-radius: 7px;
                padding: 2px 8px;
            }
            QFrame#agentAttachmentChip {
                background-color: #36363c;
                border: 1px solid #4f4f57;
                border-radius: 11px;
            }
            QPushButton#agentPrimaryButton {
                background-color: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1a87eb,
                    stop: 1 #0f78d9
                );
                border-color: #2389e7;
                color: #ffffff;
                font-weight: 600;
                min-width: 30px;
                max-width: 30px;
                min-height: 24px;
                max-height: 24px;
                padding: 0;
                border-radius: 7px;
            }
            QPushButton#agentPrimaryButton:hover {
                background-color: #2392f3;
            }
            QPushButton#agentStopButton {
                background-color: #5b2b2b;
                border-color: #7a3838;
                color: #ffffff;
                min-width: 46px;
            }
            QLabel#agentStatusLabel {
                color: #8fd4ff;
                background-color: #253545;
                border: 1px solid #334b62;
                border-radius: 9px;
                padding: 1px 7px;
                font-size: 10px;
                font-weight: 600;
            }
            QLabel#agentStatusHint {
                color: #8f8f94;
                font-size: 10px;
                padding-left: 2px;
            }
            QLabel#agentEmptyState {
                color: #b1b1b8;
                background-color: #25252a;
                border: 1px solid #34343b;
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 10px;
            }
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title = QLabel("AI Assistant")
        title.setObjectName("agentSectionTitle")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._status_label = QLabel("Not configured")
        self._status_label.setObjectName("agentStatusLabel")
        header_layout.addWidget(self._status_label)

        layout.addLayout(header_layout)

        subtitle = QLabel("Inspect the active file, selection, or structure from one place.")
        subtitle.setObjectName("agentPanelSubtitle")
        layout.addWidget(subtitle)

        self._status_hint = QLabel("")
        self._status_hint.setObjectName("agentStatusHint")
        self._status_hint.setVisible(False)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        message_container = QWidget()
        message_container.setObjectName("aiAgentMessageContainer")
        self._message_layout = QVBoxLayout()
        self._message_layout.setContentsMargins(0, 0, 0, 0)
        self._message_layout.setSpacing(8)

        self._placeholder = QLabel(
            "No conversation yet.\nAsk about the active file, current selection, or structure."
        )
        self._placeholder.setObjectName("agentEmptyState")
        self._placeholder.setWordWrap(True)
        self._message_layout.addWidget(self._placeholder)
        self._message_layout.addStretch()
        message_container.setLayout(self._message_layout)
        scroll_area.setWidget(message_container)
        self._scroll_area = scroll_area
        layout.addWidget(scroll_area, 1)

        layout.addWidget(self._status_hint)

        composer_card = QFrame(self)
        composer_card.setObjectName("agentComposerCard")
        composer_layout = QVBoxLayout()
        composer_layout.setContentsMargins(6, 6, 6, 6)
        composer_layout.setSpacing(4)

        self._attachment_bar = QWidget(composer_card)
        self._attachment_layout = QHBoxLayout()
        self._attachment_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_layout.setSpacing(3)
        self._attachment_bar.setLayout(self._attachment_layout)
        self._attachment_bar.setVisible(False)
        composer_layout.addWidget(self._attachment_bar)

        self._composer = _ChatComposer(composer_card)
        self._composer.setObjectName("agentComposerEditor")
        self._composer.setPlaceholderText("Ask a follow-up")
        self._composer.submit_requested.connect(self._on_send_clicked)
        composer_layout.addWidget(self._composer)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(3)

        self._mode_button = QToolButton(composer_card)
        self._mode_button.setObjectName("agentModeButton")
        self._mode_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        footer_row.addWidget(self._mode_button)

        self._model_button = QToolButton(composer_card)
        self._model_button.setObjectName("agentModelButton")
        self._model_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._model_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        footer_row.addWidget(self._model_button, 1)

        self._mention_button = QToolButton(composer_card)
        self._mention_button.setObjectName("agentMentionButton")
        self._mention_button.setText("@")
        self._mention_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._mention_button.setToolTip("Attach file, folder, or editor context")
        footer_row.addWidget(self._mention_button)

        self._thinking_button = QToolButton(composer_card)
        self._thinking_button.setObjectName("agentThinkingButton")
        self._thinking_button.setText("💡")
        self._thinking_button.setCheckable(True)
        self._thinking_button.setToolTip("Enable deeper reasoning before answering")
        self._thinking_button.toggled.connect(self._set_deep_thinking_enabled)
        footer_row.addWidget(self._thinking_button)
        footer_row.addStretch()

        self._send_button = QPushButton("↩", composer_card)
        self._send_button.setObjectName("agentPrimaryButton")
        self._send_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._send_button.clicked.connect(self._on_send_clicked)
        footer_row.addWidget(self._send_button)

        self._stop_button = QPushButton("Stop", composer_card)
        self._stop_button.setObjectName("agentStopButton")
        self._stop_button.clicked.connect(self._on_stop_clicked)
        self._stop_button.setEnabled(False)
        self._stop_button.setVisible(False)
        self._stop_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        footer_row.addWidget(self._stop_button)

        composer_layout.addLayout(footer_row)
        composer_card.setLayout(composer_layout)
        layout.addWidget(composer_card)

        self.setLayout(layout)

        self._build_mode_menu()
        self._build_model_menu()
        self._build_attachment_menu()
        self._refresh_manual_attachment_chips()

    def _build_mode_menu(self) -> None:
        """Create the Chat/Agent selector used by the composer."""
        menu = QMenu(self)
        self._add_menu_header(menu, "Mode")
        menu.addSeparator()
        group = QActionGroup(menu)
        group.setExclusive(True)

        for mode_key, label in self.MODE_LABELS.items():
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(mode_key == self._interaction_mode)
            action.triggered.connect(lambda checked=False, key=mode_key: self._set_interaction_mode(key))
            group.addAction(action)
            menu.addAction(action)

        self._mode_button.setMenu(menu)
        self._mode_button.setText(f"{self.MODE_LABELS[self._interaction_mode]} v")

    def _build_model_menu(self) -> None:
        """Create the model selector menu with an embedded config shortcut."""
        menu = QMenu(self)
        menu.aboutToShow.connect(self._populate_model_menu)
        self._model_menu = menu
        self._model_button.setMenu(menu)

    def _populate_model_menu(self) -> None:
        """Refresh the model selector using the current provider settings."""
        if self._model_menu is None:
            return

        provider_key, current_model, model_options = self._available_model_options()
        menu = self._model_menu
        menu.clear()
        self._add_menu_header(
            menu,
            self._config_badge_text(provider_key),
            button_text="Config",
            button_callback=self._emit_open_settings,
        )
        menu.addSeparator()

        if not model_options:
            empty_action = menu.addAction("Open settings to configure models")
            empty_action.setEnabled(False)
            return

        group = QActionGroup(menu)
        group.setExclusive(True)
        for model_name in model_options:
            action = QAction(model_name, menu)
            action.setCheckable(True)
            action.setChecked(model_name == current_model)
            action.triggered.connect(
                lambda checked=False, value=model_name: self._select_model(value)
            )
            group.addAction(action)
            menu.addAction(action)

    def _build_attachment_menu(self) -> None:
        """Create the attachment menu shared by the @ button."""
        menu = QMenu(self)
        menu.aboutToShow.connect(self._populate_attachment_menu)
        self._attachment_menu = menu
        self._mention_button.setMenu(menu)

    def _add_menu_header(
        self,
        menu: QMenu,
        title: str,
        *,
        button_text: str = "",
        button_callback=None,
    ) -> None:
        """Insert a compact menu header row with an optional action button."""
        header = QWidget(menu)
        header.setObjectName("agentMenuHeader")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(4, 2, 4, 6)
        header_layout.setSpacing(6)

        title_label = QLabel(title, header)
        title_label.setStyleSheet("font-weight: 700; color: #f3f3f4;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        if button_text and button_callback is not None:
            button = QToolButton(header)
            button.setObjectName("agentMenuHeaderButton")
            button.setText(button_text)
            button.clicked.connect(menu.close)
            button.clicked.connect(button_callback)
            header_layout.addWidget(button)

        header.setLayout(header_layout)
        header_action = QWidgetAction(menu)
        header_action.setDefaultWidget(header)
        menu.addAction(header_action)

    def _emit_open_settings(self) -> None:
        """Open the full settings dialog from embedded composer controls."""
        self.open_settings_requested.emit()

    def _set_interaction_mode(self, mode_key: str) -> None:
        """Update the composer mode shown in the Continue-style footer."""
        if mode_key not in self.MODE_LABELS:
            return
        self._interaction_mode = mode_key
        self._mode_button.setText(f"{self.MODE_LABELS[mode_key]} v")
        if mode_key == "agent":
            self._set_status_hint("Agent mode uses tools proactively.")
        else:
            self._set_status_hint("Chat mode answers directly unless tools are needed.")

    def _set_pin_active_file(self, checked: bool) -> None:
        """Toggle persistent active-file pinning for each turn."""
        self._pin_active_file = bool(checked)
        self._refresh_context_controls()

    def _set_allow_navigation_tools(self, checked: bool) -> None:
        """Enable or disable navigation-oriented tools for new turns."""
        self._allow_navigation_tools = bool(checked)
        self._sync_runner_tool_policy()
        self._set_status_hint(
            "Navigation tools enabled." if self._allow_navigation_tools else "Navigation tools limited to explicit user requests."
        )

    def _set_max_steps(self, max_steps: int) -> None:
        """Change the agent loop budget from the composer config menu."""
        self._max_steps = int(max_steps)
        if self._runner is not None:
            self._runner.set_max_steps(self._max_steps)
        self._set_status_hint(f"Max steps: {self._max_steps}")

    def _set_deep_thinking_enabled(self, checked: bool) -> None:
        """Toggle the composer-level deep-thinking hint."""
        enabled = bool(checked)
        self._deep_thinking_enabled = enabled
        self._thinking_button.blockSignals(True)
        self._thinking_button.setChecked(enabled)
        self._thinking_button.blockSignals(False)
        if enabled:
            self._set_status_hint("Deep thinking enabled.")
        elif not (self._runner and self._runner.is_running):
            self._set_status_hint("")

    def _get_app_settings(self) -> QSettings:
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

    def _current_ai_settings(self) -> dict[str, Any]:
        """Return the latest persisted AI settings snapshot."""
        app = QApplication.instance()
        current = getattr(app, "_ai_settings", None)
        if isinstance(current, dict) and current:
            return deepcopy(current)

        configured = getattr(self._ai_manager, "_configured_settings", None)
        if isinstance(configured, dict) and configured:
            return deepcopy(configured)

        return {
            "enabled": True,
            "provider": "local",
            "local": {
                "endpoint": "http://localhost:11434",
                "model": self.LOCAL_MODEL_OPTIONS[0],
                "temperature": 0.7,
                "max_tokens": 4096,
                "timeout": 60,
            },
            "cloud": {
                "provider": "openai",
                "api_key": "",
                "base_url": "",
                "model": self.CLOUD_MODEL_OPTIONS["openai"][0],
                "temperature": 0.7,
                "max_tokens": 4096,
                "timeout": 60,
            },
        }

    def _persist_ai_settings(self, settings: dict[str, Any]) -> None:
        """Persist AI settings after quick model changes from the composer."""
        snapshot = deepcopy(settings)
        app = QApplication.instance()
        if app is not None:
            app._ai_settings = snapshot

        app_settings = self._get_app_settings()
        app_settings.setValue("ai_enabled", snapshot.get("enabled", True))
        app_settings.setValue("ai_provider", snapshot.get("provider", "local"))
        app_settings.setValue("ai_local_endpoint", snapshot.get("local", {}).get("endpoint", ""))
        app_settings.setValue("ai_local_model", snapshot.get("local", {}).get("model", ""))
        app_settings.setValue("ai_cloud_provider", snapshot.get("cloud", {}).get("provider", ""))
        app_settings.setValue("ai_cloud_api_key", snapshot.get("cloud", {}).get("api_key", ""))
        app_settings.setValue("ai_cloud_base_url", snapshot.get("cloud", {}).get("base_url", ""))
        app_settings.setValue("ai_cloud_model", snapshot.get("cloud", {}).get("model", ""))

        if self._ai_manager is not None:
            self._ai_manager.configure(snapshot)

        self.refresh_provider_status()

    def _effective_provider_key(self, settings: Optional[dict[str, Any]] = None) -> str:
        """Return the logical provider key backing the current model selector."""
        snapshot = settings or self._current_ai_settings()
        provider_key = str(snapshot.get("provider", "local") or "local").strip().lower()
        if provider_key == "local":
            return "local"
        cloud_provider = str(
            snapshot.get("cloud", {}).get("provider", provider_key) or provider_key
        ).strip().lower()
        return cloud_provider or "openai"

    def _available_model_options(self) -> tuple[str, str, list[str]]:
        """Return provider, current model, and model candidates for the selector."""
        settings = self._current_ai_settings()
        provider_key = self._effective_provider_key(settings)
        if provider_key == "local":
            current_model = str(settings.get("local", {}).get("model", "")).strip()
            model_options = list(self.LOCAL_MODEL_OPTIONS)
        else:
            current_model = str(settings.get("cloud", {}).get("model", "")).strip()
            model_options = list(
                self.CLOUD_MODEL_OPTIONS.get(provider_key, self.CLOUD_MODEL_OPTIONS["openai"])
            )

        if current_model and current_model not in model_options:
            model_options.insert(0, current_model)

        return provider_key, current_model, model_options

    def _config_badge_text(self, provider_key: str = "") -> str:
        """Return the short config badge text shown at the top of the composer."""
        effective_provider = provider_key or self._effective_provider_key()
        return self.PROVIDER_CONFIG_LABELS.get(effective_provider, "AI Config")

    def _select_model(self, model_name: str) -> None:
        """Apply a model picked from the inline dropdown."""
        value = str(model_name or "").strip()
        if not value:
            return

        settings = self._current_ai_settings()
        provider_key = self._effective_provider_key(settings)
        if provider_key == "local":
            settings.setdefault("local", {})["model"] = value
        else:
            settings.setdefault("cloud", {})["provider"] = provider_key
            settings.setdefault("cloud", {})["model"] = value
        self._persist_ai_settings(settings)
        self._set_status_hint(f"Using {value}")

    def _current_context_snapshot(self) -> dict[str, Any]:
        """Collect a fresh context snapshot from the tool host when available."""
        if self._tool_host is None:
            return {}
        builder = getattr(self._tool_host, "build_default_context", None)
        if not callable(builder):
            return {}
        try:
            payload = builder()
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _populate_attachment_menu(self) -> None:
        """Refresh the dynamic attachment menu with file, folder, and editor context entries."""
        if self._attachment_menu is None:
            return

        snapshot = self._current_context_snapshot()
        active_file = snapshot.get("active_file")
        selection = snapshot.get("selection")
        current_row = snapshot.get("current_row")
        structure_configs = snapshot.get("structure_configs") or {}
        open_files = snapshot.get("open_files") or []

        menu = self._attachment_menu
        menu.clear()

        self._add_menu_header(menu, "Attach")
        menu.addSeparator()

        add_file_action = menu.addAction("Add File...")
        add_file_action.triggered.connect(self._choose_file_attachment)

        add_folder_action = menu.addAction("Add Folder...")
        add_folder_action.triggered.connect(self._choose_folder_attachment)

        has_editor_context = any(
            [
                active_file is not None,
                selection is not None,
                current_row is not None,
                bool(structure_configs.get("count", 0)),
                bool(open_files),
            ]
        )
        if has_editor_context:
            menu.addSeparator()

            current_file_action = menu.addAction("Current File")
            current_file_action.setEnabled(active_file is not None)
            current_file_action.triggered.connect(
                lambda: self._attach_builtin_context("current_file")
            )

            selection_action = menu.addAction("Selection")
            selection_action.setEnabled(selection is not None)
            selection_action.triggered.connect(
                lambda: self._attach_builtin_context("selection")
            )

            row_action = menu.addAction("Current Row")
            row_action.setEnabled(current_row is not None)
            row_action.triggered.connect(
                lambda: self._attach_builtin_context("current_row")
            )

            structure_action = menu.addAction("Structure")
            structure_action.setEnabled(bool(structure_configs.get("count", 0)))
            structure_action.triggered.connect(
                lambda: self._attach_builtin_context("structure")
            )

            open_files_action = menu.addAction("Open Files Summary")
            open_files_action.setEnabled(bool(open_files))
            open_files_action.triggered.connect(
                lambda: self._attach_builtin_context("open_files")
            )

        if open_files:
            files_menu = menu.addMenu("Attach Open File")
            for file_info in open_files:
                label = str(file_info.get("file_name") or file_info.get("target") or "Untitled")
                action = files_menu.addAction(label)
                target = str(file_info.get("target") or "")
                action.triggered.connect(
                    lambda checked=False, info=dict(file_info): self._add_manual_attachment(
                        self._file_attachment_descriptor(info)
                    )
                )
                if target:
                    action.setToolTip(target)

    def _apply_prompt_template(self, prompt_text: str) -> None:
        """Replace or seed the composer with a suggested analysis prompt."""
        self._composer.setPlainText(str(prompt_text).strip())
        self.focus_input()

    def _refresh_context_controls(self) -> None:
        """Update chip states and quick-attach availability from the current editor context."""
        snapshot = self._current_context_snapshot()
        active_file = snapshot.get("active_file")
        selection = snapshot.get("selection")
        current_row = snapshot.get("current_row")
        structure_configs = snapshot.get("structure_configs") or {}
        open_files = snapshot.get("open_files") or []

        has_context = (
            bool(active_file)
            or bool(selection)
            or bool(current_row)
            or bool(structure_configs.get("count", 0))
            or bool(open_files)
        )
        self._mention_button.setEnabled(True)
        tooltip = "Attach file or folder"
        if has_context:
            tooltip += ", or reuse active editor context"
        self._mention_button.setToolTip(tooltip)

    def _attach_builtin_context(self, kind: str) -> None:
        """Attach one of the built-in editor-context presets."""
        descriptor = self._builtin_attachment_descriptor(kind)
        if descriptor is None:
            self._set_status_hint("That context is not available right now.")
            return
        self._add_manual_attachment(descriptor)

    def _builtin_attachment_descriptor(self, kind: str) -> Optional[dict[str, str]]:
        """Create a descriptor for a built-in context attachment."""
        snapshot = self._current_context_snapshot()
        active_file = snapshot.get("active_file")
        selection = snapshot.get("selection")
        current_row = snapshot.get("current_row")
        structure_configs = snapshot.get("structure_configs") or {}
        open_files = snapshot.get("open_files") or []

        if kind == "current_file":
            if not isinstance(active_file, dict):
                return None
            target = str(active_file.get("target") or "")
            name = str(active_file.get("file_name") or target or "Active file")
            return {
                "id": f"current_file:{target or name}",
                "label": f"File: {name}",
                "prompt": (
                    f'Use the active file "{name}" as attached context. '
                    "Start with get_file_metadata, then read_bytes only if needed."
                ),
            }

        if kind == "selection":
            if not isinstance(selection, dict):
                return None
            return {
                "id": "selection",
                "label": "Selection",
                "prompt": "The current selection is attached. Start with read_selection.",
            }

        if kind == "current_row":
            if not isinstance(current_row, dict):
                return None
            return {
                "id": "current_row",
                "label": "Current Row",
                "prompt": "The current row around the cursor is attached. Start with read_current_row.",
            }

        if kind == "structure":
            if not structure_configs.get("count", 0):
                return None
            return {
                "id": "structure",
                "label": "Structure",
                "prompt": (
                    "Saved structure configs are attached. Start with list_structure_configs and"
                    " decode_structure when appropriate."
                ),
            }

        if kind == "open_files":
            if not open_files:
                return None
            return {
                "id": "open_files",
                "label": "Open Files",
                "prompt": "The open file list is attached. Start with list_open_files.",
            }

        return None

    def _file_attachment_descriptor(self, file_info: dict[str, Any]) -> dict[str, str]:
        """Create a descriptor for a specific open file."""
        target = str(file_info.get("target") or "")
        label = str(file_info.get("file_name") or Path(target).name or target or "Open file")
        prompt = (
            f'Use the attached file "{label}" as context. '
            f'If needed, activate it with target "{target}" before reading bytes or metadata.'
        )
        return {
            "id": f"file:{target or label}",
            "label": label,
            "prompt": prompt,
        }

    def _choose_file_attachment(self) -> None:
        """Open a file picker and add the selected path as an attachment chip."""
        file_path, _filter_value = QFileDialog.getOpenFileName(self, "Attach File")
        if not file_path:
            return
        descriptor = self._path_attachment_descriptor(file_path)
        if descriptor is not None:
            self._add_manual_attachment(descriptor)

    def _choose_folder_attachment(self) -> None:
        """Open a directory picker and add the selected folder as an attachment chip."""
        folder_path = QFileDialog.getExistingDirectory(self, "Attach Folder")
        if not folder_path:
            return
        descriptor = self._folder_attachment_descriptor(folder_path)
        if descriptor is not None:
            self._add_manual_attachment(descriptor)

    def _path_attachment_descriptor(self, path_value: str) -> Optional[dict[str, str]]:
        """Create an attachment descriptor for a local file path."""
        path = Path(path_value).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path

        if not resolved.is_file():
            return None

        snapshot = self._current_context_snapshot()
        open_files = snapshot.get("open_files") or []
        for file_info in open_files:
            target = str(file_info.get("target") or "").strip()
            if target and target == str(resolved):
                return self._file_attachment_descriptor(file_info)

        try:
            file_size = resolved.stat().st_size
        except OSError:
            file_size = 0

        label = resolved.name or str(resolved)
        return {
            "id": f"local-file:{resolved}",
            "label": label,
            "prompt": (
                f'Attached local file path: "{resolved}" ({file_size} bytes). '
                "If detailed byte inspection is needed and the file is not already open, ask the user to open it in the editor first."
            ),
        }

    def _folder_attachment_descriptor(self, path_value: str) -> Optional[dict[str, str]]:
        """Create an attachment descriptor for a local folder path."""
        path = Path(path_value).expanduser()
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path

        if not resolved.is_dir():
            return None

        try:
            entries = sorted(resolved.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            entries = []

        entry_labels = [
            f"{item.name}/" if item.is_dir() else item.name
            for item in entries[:8]
        ]
        preview = ", ".join(entry_labels) if entry_labels else "empty"
        if len(entries) > 8:
            preview += ", ..."

        label = f"{resolved.name or resolved}/"
        return {
            "id": f"local-folder:{resolved}",
            "label": label,
            "prompt": (
                f'Attached local folder: "{resolved}". '
                f"Visible entries: {preview}. "
                "Use this as path context. If a specific file needs byte-level inspection, ask the user to open it in the editor."
            ),
        }

    def _add_manual_attachment(self, descriptor: dict[str, str]) -> None:
        """Add a context attachment chip unless it is already present."""
        attachment_id = str(descriptor.get("id", "")).strip()
        if not attachment_id:
            return
        for existing in self._manual_attachments:
            if existing.get("id") == attachment_id:
                self.focus_input()
                return
        self._manual_attachments.append(descriptor)
        self._refresh_manual_attachment_chips()
        self._set_status_hint(f'Attached "{descriptor.get("label", attachment_id)}"')
        self.focus_input()

    def _remove_manual_attachment(self, attachment_id: str) -> None:
        """Remove one attachment chip from the composer."""
        self._manual_attachments = [
            descriptor
            for descriptor in self._manual_attachments
            if descriptor.get("id") != attachment_id
        ]
        self._refresh_manual_attachment_chips()

    def _refresh_manual_attachment_chips(self) -> None:
        """Rebuild the attachment chip row shown above the composer."""
        while self._attachment_layout.count():
            item = self._attachment_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._attachment_chips.clear()
        self._attachment_bar.setVisible(bool(self._manual_attachments))
        for descriptor in self._manual_attachments:
            chip = _AttachmentChip(
                str(descriptor.get("id", "")),
                str(descriptor.get("label", "")),
                parent=self._attachment_bar,
            )
            chip.remove_requested.connect(self._remove_manual_attachment)
            self._attachment_layout.addWidget(chip)
            self._attachment_chips.append(chip)

        self._attachment_layout.addStretch()

    def _compose_prompt(self, prompt: str) -> tuple[str, str]:
        """Build the model-visible prompt while keeping the transcript text clean."""
        prompt = str(prompt or "").strip()
        display_prompt = prompt
        snapshot = self._current_context_snapshot()
        context_lines: list[str] = []
        control_lines: list[str] = []

        if self._pin_active_file:
            active_file = snapshot.get("active_file")
            if isinstance(active_file, dict):
                active_name = str(active_file.get("file_name") or active_file.get("target") or "active file")
                context_lines.append(
                    f'Pinned active file: "{active_name}". Start with get_file_metadata for the active file.'
                )

        context_lines.extend(
            str(descriptor.get("prompt", "")).strip()
            for descriptor in self._manual_attachments
            if str(descriptor.get("prompt", "")).strip()
        )

        if self._interaction_mode == "chat":
            control_lines.append("Prefer a direct answer when enough context already exists. Use tools only when needed.")
        else:
            control_lines.append("Use tools proactively when they will improve the analysis.")

        if self._deep_thinking_enabled:
            control_lines.append(
                "Deep thinking is enabled. Reason through multiple plausible interpretations before finalizing the answer."
            )

        if not self._allow_navigation_tools:
            control_lines.append(
                "Do not call activate_file, navigate_to_offset, or select_range unless the user explicitly asks to navigate."
            )

        sections: list[str] = []
        if context_lines:
            sections.append("Attached context:\n- " + "\n- ".join(context_lines))
        if control_lines:
            sections.append("Composer controls:\n- " + "\n- ".join(control_lines))
        sections.append(f"User request:\n{prompt}")
        return "\n\n".join(section for section in sections if section), display_prompt

    def _set_runner(self, runner: Optional[AgentRunner]) -> None:
        if self._runner is not None:
            self._runner.shutdown()
            try:
                self._runner.message_emitted.disconnect(self._on_runner_message)
            except TypeError:
                pass
            try:
                self._runner.running_changed.disconnect(self._on_running_changed)
            except TypeError:
                pass
            try:
                self._runner.turn_finished.disconnect(self._on_turn_finished)
            except TypeError:
                pass
            try:
                self._runner.turn_failed.disconnect(self._on_turn_failed)
            except TypeError:
                pass

        self._runner = runner
        if self._runner is None:
            return

        self._runner.message_emitted.connect(self._on_runner_message)
        self._runner.running_changed.connect(self._on_running_changed)
        self._runner.turn_finished.connect(self._on_turn_finished)
        self._runner.turn_failed.connect(self._on_turn_failed)
        self._runner.set_max_steps(self._max_steps)
        self._sync_runner_tool_policy()

    def _sync_runner_tool_policy(self) -> None:
        """Apply the current navigation-tool policy to the active runner."""
        if self._runner is None:
            return
        disabled = set() if self._allow_navigation_tools else set(self.NAVIGATION_TOOL_NAMES)
        self._runner.set_disabled_tools(disabled)

    def closeEvent(self, event) -> None:
        """Ensure worker shutdown when the parent window closes."""
        self.shutdown()
        super().closeEvent(event)

    def _on_pin_active_file_toggled(self, checked: bool) -> None:
        self._set_pin_active_file(checked)

    def _on_send_clicked(self) -> None:
        prompt = self._composer.toPlainText().strip()
        if not prompt:
            return
        model_prompt, display_prompt = self._compose_prompt(prompt)
        if self.submit_prompt(model_prompt, display_prompt=display_prompt):
            self._composer.clear()
            self._manual_attachments.clear()
            self._refresh_manual_attachment_chips()
            self._refresh_context_controls()

    def _on_stop_clicked(self) -> None:
        if self._runner is None:
            return
        self._runner.cancel()

    def _on_runner_message(self, message: ChatMessage) -> None:
        self._session.append(message)
        self._append_message(message)

    def _on_running_changed(self, running: bool) -> None:
        self._composer.setReadOnly(running)
        self._send_button.setEnabled(not running)
        self._send_button.setVisible(not running)
        self._stop_button.setEnabled(running)
        self._stop_button.setVisible(running)
        self._mode_button.setEnabled(not running)
        self._model_button.setEnabled(not running)
        self._mention_button.setEnabled(not running)
        self._thinking_button.setEnabled(not running)
        self._attachment_bar.setEnabled(not running)
        self._set_status_hint("Running" if running else "")
        if not running:
            self._refresh_context_controls()

    def _on_turn_finished(self, _result: str) -> None:
        self._set_status_hint("")
        self._refresh_context_controls()

    def _on_turn_failed(self, error_text: str) -> None:
        if error_text == "Agent turn cancelled.":
            self._set_status_hint("Cancelled")
        else:
            self._set_status_hint("Failed")
        self._refresh_context_controls()

    def _append_message(self, message: ChatMessage) -> None:
        self._placeholder.setVisible(False)
        if message.kind in {"thinking", "tool_call", "tool_result"}:
            if self._active_trace_card is None:
                trace_card = _ThinkingTraceCard(self)
                trace_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
                self._message_layout.insertWidget(
                    max(0, self._message_layout.count() - 1),
                    trace_card,
                )
                self._message_cards.append(trace_card)
                self._active_trace_card = trace_card
            self._active_trace_card.add_message(message)
            QTimer.singleShot(0, self._scroll_to_bottom)
            return

        self._active_trace_card = None
        card = _MessageCard(message, self)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._message_layout.insertWidget(max(0, self._message_layout.count() - 1), card)
        self._message_cards.append(card)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scroll_bar = self._scroll_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
