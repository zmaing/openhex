"""
Continue-style chat panel for the AI agent sidebar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from PyQt6.QtCore import QSize, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
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
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(6)

        label_widget = QLabel(label, self)
        label_widget.setStyleSheet("font-size: 11px; font-weight: 600;")
        layout.addWidget(label_widget)

        if removable:
            close_button = QToolButton(self)
            close_button.setText("x")
            close_button.setAutoRaise(True)
            close_button.clicked.connect(lambda: self.remove_requested.emit(self._attachment_id))
            layout.addWidget(close_button)

        self.setLayout(layout)


class AIAgentPanel(QWidget):
    """Chat-first AI panel that uses the agent runtime and editor tools."""

    open_settings_requested = pyqtSignal()
    NAVIGATION_TOOL_NAMES = {"activate_file", "navigate_to_offset", "select_range"}
    MODE_LABELS = {
        "chat": "Chat",
        "agent": "Agent",
    }
    MAX_STEPS_OPTIONS = (4, 8, 12)
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
        self._message_cards: list[_MessageCard] = []
        self._attachment_chips: list[_AttachmentChip] = []
        self._manual_attachments: list[dict[str, str]] = []
        self._interaction_mode = "chat"
        self._pin_active_file = True
        self._allow_navigation_tools = False
        self._max_steps = 8
        self._attachment_menu: Optional[QMenu] = None
        self._context_menu: Optional[QMenu] = None
        self._prompt_menu: Optional[QMenu] = None
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
            self._model_button.setText("Model")
            self._config_button.setText("Config")
            return
        status_text = self._ai_manager.status_text()
        provider_name = getattr(self._ai_manager, "current_provider_name", "AI")
        model_name = getattr(self._ai_manager, "current_model_name", "") or provider_name
        self._status_label.setText(status_text)
        self._model_button.setText(model_name)
        self._model_button.setToolTip(status_text)
        self._config_button.setText("Config")
        self._config_button.setToolTip(f"{provider_name} settings")

    def clear_session(self) -> None:
        """Reset the transcript."""
        self._session.clear()
        self._manual_attachments.clear()
        self._refresh_manual_attachment_chips()
        for card in self._message_cards:
            self._message_layout.removeWidget(card)
            card.deleteLater()
        self._message_cards.clear()
        self._placeholder.setVisible(True)
        self._status_hint.setText("Session cleared")

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
            self._status_hint.setText("Running")
        return started

    def send_preset_prompt(self, prompt: str) -> bool:
        """Submit a pre-filled prompt without touching the composer text."""
        model_prompt, display_prompt = self._compose_prompt(prompt)
        return self.submit_prompt(model_prompt, display_prompt=display_prompt)

    def _build_ui(self) -> None:
        self.setObjectName("aiAgentPanel")
        self.setStyleSheet(
            """
            QWidget#aiAgentPanel {
                background-color: #252526;
                color: #d4d4d4;
            }
            QWidget#aiAgentPanel QLabel {
                background: transparent;
                border: none;
            }
            QWidget#aiAgentPanel QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #094771;
            }
            QWidget#aiAgentPanel QPushButton {
                background-color: #2d2d30;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                padding: 5px 10px;
                min-height: 28px;
            }
            QWidget#aiAgentPanel QPushButton:hover {
                background-color: #37373d;
            }
            QWidget#aiAgentPanel QToolButton {
                background-color: transparent;
                color: #d4d4d4;
                border: none;
                padding: 4px 6px;
                border-radius: 4px;
            }
            QWidget#aiAgentPanel QToolButton:hover {
                background-color: #37373d;
            }
            QFrame#agentComposerCard {
                background-color: #2b2b2d;
                border: 1px solid #45454a;
                border-radius: 12px;
            }
            QFrame#agentComposerToolbar {
                background-color: #323236;
                border: 1px solid #45454a;
                border-radius: 9px;
            }
            QPlainTextEdit#agentComposerEditor {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 2px 0 6px 0;
                min-height: 92px;
            }
            QToolButton#agentFlatControl {
                background-color: transparent;
                border: 1px solid #4a4a4f;
                border-radius: 9px;
                padding: 4px 10px;
                min-height: 28px;
            }
            QToolButton#agentFlatControl:hover {
                background-color: #3a3a3f;
            }
            QToolButton#agentFlatControl::menu-indicator,
            QToolButton#agentIconButton::menu-indicator,
            QToolButton#agentFooterButton::menu-indicator,
            QToolButton#agentToolbarButton::menu-indicator {
                image: none;
                width: 0px;
            }
            QToolButton#agentIconButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
            }
            QToolButton#agentIconButton:hover {
                background-color: #3a3a3f;
            }
            QToolButton#agentFooterButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
                min-height: 28px;
            }
            QToolButton#agentFooterButton:hover {
                background-color: #3a3a3f;
            }
            QToolButton#agentToolbarButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QToolButton#agentToolbarButton:hover {
                background-color: #3a3a3f;
            }
            QFrame#agentAttachmentChip {
                background-color: #343438;
                border: 1px solid #4f4f54;
                border-radius: 12px;
            }
            QPushButton#agentPrimaryButton {
                background-color: #0e639c;
                border-color: #1177bb;
                color: #ffffff;
                font-weight: 600;
                min-width: 84px;
            }
            QPushButton#agentPrimaryButton:hover {
                background-color: #1177bb;
            }
            QPushButton#agentToggleChip {
                border-radius: 12px;
                padding: 4px 12px;
            }
            QPushButton#agentToggleChip:checked {
                background-color: #1f4a7a;
                border-color: #3a77d2;
                color: #ffffff;
            }
            QPushButton#agentInlineToggle {
                background-color: transparent;
                border: 1px solid transparent;
                color: #d4d4d4;
                padding: 4px 8px;
                min-height: 28px;
            }
            QPushButton#agentInlineToggle:checked {
                background-color: #2d2d30;
                border-color: #4a4a4f;
            }
            """
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title = QLabel("AI Agent")
        title.setStyleSheet("font-weight: 700; font-size: 13px;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        clear_button = QToolButton(self)
        clear_button.setText("Clear")
        clear_button.clicked.connect(self.clear_session)
        self._clear_button = clear_button
        header_layout.addWidget(clear_button)

        settings_button = QToolButton(self)
        settings_button.setText("Settings")
        settings_button.clicked.connect(self.open_settings_requested.emit)
        header_layout.addWidget(settings_button)

        layout.addLayout(header_layout)

        self._status_label = QLabel("Not configured")
        self._status_label.setStyleSheet("color: #9cdcfe;")
        layout.addWidget(self._status_label)

        self._status_hint = QLabel("Ask the assistant to inspect the active binary.")
        self._status_hint.setStyleSheet("color: #858585;")
        layout.addWidget(self._status_hint)

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

        self._placeholder = QLabel("No conversation yet. Describe what you want to inspect.")
        self._placeholder.setWordWrap(True)
        self._placeholder.setStyleSheet("color: #858585; padding: 12px 8px;")
        self._message_layout.addWidget(self._placeholder)
        self._message_layout.addStretch()
        message_container.setLayout(self._message_layout)
        scroll_area.setWidget(message_container)
        self._scroll_area = scroll_area
        layout.addWidget(scroll_area, 1)

        toolbar_strip = QFrame(self)
        toolbar_strip.setObjectName("agentComposerToolbar")
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(4)

        self._attach_button = QToolButton(toolbar_strip)
        self._attach_button.setObjectName("agentIconButton")
        self._attach_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self._attach_button.setIconSize(QSize(16, 16))
        self._attach_button.setToolTip("Attach files and editor context")
        toolbar_layout.addWidget(self._attach_button)

        self._context_button = QToolButton(toolbar_strip)
        self._context_button.setObjectName("agentIconButton")
        self._context_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        self._context_button.setIconSize(QSize(16, 16))
        self._context_button.setToolTip("Attach current selection, row, or structure context")
        toolbar_layout.addWidget(self._context_button)

        self._preset_button = QToolButton(toolbar_strip)
        self._preset_button.setObjectName("agentIconButton")
        self._preset_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self._preset_button.setIconSize(QSize(16, 16))
        self._preset_button.setToolTip("Insert prompt suggestions")
        toolbar_layout.addWidget(self._preset_button)

        toolbar_layout.addStretch()

        self._config_button = QToolButton(toolbar_strip)
        self._config_button.setObjectName("agentFlatControl")
        self._config_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar_layout.addWidget(self._config_button)
        toolbar_strip.setLayout(toolbar_layout)
        layout.addWidget(toolbar_strip)

        composer_card = QFrame(self)
        composer_card.setObjectName("agentComposerCard")
        composer_layout = QVBoxLayout()
        composer_layout.setContentsMargins(10, 8, 10, 8)
        composer_layout.setSpacing(6)

        self._attachment_bar = QWidget(composer_card)
        self._attachment_layout = QHBoxLayout()
        self._attachment_layout.setContentsMargins(0, 0, 0, 0)
        self._attachment_layout.setSpacing(6)
        self._attachment_bar.setLayout(self._attachment_layout)
        self._attachment_bar.setVisible(False)
        composer_layout.addWidget(self._attachment_bar)

        self._composer = _ChatComposer(composer_card)
        self._composer.setObjectName("agentComposerEditor")
        self._composer.setPlaceholderText("Ask a follow-up about the active binary. Ctrl+Enter to send.")
        self._composer.submit_requested.connect(self._on_send_clicked)
        composer_layout.addWidget(self._composer)

        footer_meta_row = QHBoxLayout()
        footer_meta_row.setContentsMargins(0, 0, 0, 0)
        footer_meta_row.setSpacing(6)

        self._mode_button = QToolButton(composer_card)
        self._mode_button.setObjectName("agentFlatControl")
        self._mode_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        footer_meta_row.addWidget(self._mode_button)

        self._model_button = QToolButton(composer_card)
        self._model_button.setObjectName("agentFlatControl")
        self._model_button.clicked.connect(self.open_settings_requested.emit)
        self._model_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        footer_meta_row.addWidget(self._model_button, 1)

        self._mention_button = QToolButton(composer_card)
        self._mention_button.setObjectName("agentFooterButton")
        self._mention_button.setText("@")
        self._mention_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        footer_meta_row.addWidget(self._mention_button)

        self._prompt_button = QToolButton(composer_card)
        self._prompt_button.setObjectName("agentFooterButton")
        self._prompt_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        self._prompt_button.setIconSize(QSize(16, 16))
        self._prompt_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        footer_meta_row.addWidget(self._prompt_button)
        composer_layout.addLayout(footer_meta_row)

        footer_action_row = QHBoxLayout()
        footer_action_row.setContentsMargins(0, 0, 0, 0)
        footer_action_row.setSpacing(6)

        self._active_file_button = QPushButton("Active file", composer_card)
        self._active_file_button.setObjectName("agentInlineToggle")
        self._active_file_button.setCheckable(True)
        self._active_file_button.setChecked(True)
        self._active_file_button.toggled.connect(self._on_pin_active_file_toggled)
        footer_action_row.addWidget(self._active_file_button)
        footer_action_row.addStretch()

        self._send_button = QPushButton("Enter", composer_card)
        self._send_button.setObjectName("agentPrimaryButton")
        self._send_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._send_button.clicked.connect(self._on_send_clicked)
        footer_action_row.addWidget(self._send_button)

        self._stop_button = QPushButton("Stop", composer_card)
        self._stop_button.clicked.connect(self._on_stop_clicked)
        self._stop_button.setEnabled(False)
        self._stop_button.setVisible(False)
        self._stop_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        footer_action_row.addWidget(self._stop_button)

        composer_layout.addLayout(footer_action_row)
        composer_card.setLayout(composer_layout)
        layout.addWidget(composer_card)

        self.setLayout(layout)

        self._build_mode_menu()
        self._build_attachment_menu()
        self._build_context_menu()
        self._build_prompt_menu()
        self._build_config_menu()
        self._refresh_manual_attachment_chips()

    def _build_mode_menu(self) -> None:
        """Create the Chat/Agent selector used by the composer."""
        menu = QMenu(self)
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
        self._mode_button.setText(self.MODE_LABELS[self._interaction_mode])

    def _build_attachment_menu(self) -> None:
        """Create the Continue-style attachment menu shared by the file buttons."""
        menu = QMenu(self)
        menu.aboutToShow.connect(self._populate_attachment_menu)
        self._attachment_menu = menu

        for button in (self._attach_button, self._mention_button):
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def _build_context_menu(self) -> None:
        """Create the menu for quick built-in editor contexts."""
        menu = QMenu(self)
        menu.aboutToShow.connect(self._populate_context_menu)
        self._context_menu = menu
        self._context_button.setMenu(menu)
        self._context_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def _build_prompt_menu(self) -> None:
        """Create the prompt suggestion menu used by the footer and toolbar."""
        menu = QMenu(self)
        for label, prompt in self.PROMPT_SUGGESTIONS.items():
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, text=prompt: self._apply_prompt_template(text))
        self._prompt_menu = menu
        for button in (self._preset_button, self._prompt_button):
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

    def _build_config_menu(self) -> None:
        """Create the composer configuration dropdown."""
        menu = QMenu(self)

        settings_action = menu.addAction("Open Settings...")
        settings_action.triggered.connect(self.open_settings_requested.emit)
        menu.addSeparator()

        self._pin_active_file_action = menu.addAction("Pin Active File")
        self._pin_active_file_action.setCheckable(True)
        self._pin_active_file_action.setChecked(self._pin_active_file)
        self._pin_active_file_action.toggled.connect(self._set_pin_active_file)

        self._allow_navigation_action = menu.addAction("Allow Navigation Tools")
        self._allow_navigation_action.setCheckable(True)
        self._allow_navigation_action.setChecked(self._allow_navigation_tools)
        self._allow_navigation_action.toggled.connect(self._set_allow_navigation_tools)

        menu.addSeparator()
        steps_menu = menu.addMenu("Max Steps")
        steps_group = QActionGroup(steps_menu)
        steps_group.setExclusive(True)
        for value in self.MAX_STEPS_OPTIONS:
            action = QAction(str(value), steps_menu)
            action.setCheckable(True)
            action.setChecked(value == self._max_steps)
            action.triggered.connect(lambda checked=False, step_count=value: self._set_max_steps(step_count))
            steps_group.addAction(action)
            steps_menu.addAction(action)

        self._config_button.setMenu(menu)

    def _set_interaction_mode(self, mode_key: str) -> None:
        """Update the composer mode shown in the Continue-style footer."""
        if mode_key not in self.MODE_LABELS:
            return
        self._interaction_mode = mode_key
        self._mode_button.setText(self.MODE_LABELS[mode_key])
        if mode_key == "agent":
            self._status_hint.setText("Agent mode uses tools proactively.")
        else:
            self._status_hint.setText("Chat mode answers directly unless tools are needed.")

    def _set_pin_active_file(self, checked: bool) -> None:
        """Toggle persistent active-file pinning for each turn."""
        self._pin_active_file = bool(checked)
        self._active_file_button.blockSignals(True)
        self._active_file_button.setChecked(self._pin_active_file)
        self._active_file_button.blockSignals(False)
        self._pin_active_file_action.blockSignals(True)
        self._pin_active_file_action.setChecked(self._pin_active_file)
        self._pin_active_file_action.blockSignals(False)
        self._refresh_context_controls()

    def _set_allow_navigation_tools(self, checked: bool) -> None:
        """Enable or disable navigation-oriented tools for new turns."""
        self._allow_navigation_tools = bool(checked)
        self._sync_runner_tool_policy()
        self._status_hint.setText(
            "Navigation tools enabled." if self._allow_navigation_tools else "Navigation tools limited to explicit user requests."
        )

    def _set_max_steps(self, max_steps: int) -> None:
        """Change the agent loop budget from the composer config menu."""
        self._max_steps = int(max_steps)
        if self._runner is not None:
            self._runner.set_max_steps(self._max_steps)
        self._status_hint.setText(f"Ready · max {self._max_steps} steps")

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
        """Refresh the dynamic attachment menu with open-file and context entries."""
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

        current_file_action = menu.addAction("Current File")
        current_file_action.setEnabled(active_file is not None)
        current_file_action.triggered.connect(lambda: self._attach_builtin_context("current_file"))

        selection_action = menu.addAction("Selection")
        selection_action.setEnabled(selection is not None)
        selection_action.triggered.connect(lambda: self._attach_builtin_context("selection"))

        row_action = menu.addAction("Current Row")
        row_action.setEnabled(current_row is not None)
        row_action.triggered.connect(lambda: self._attach_builtin_context("current_row"))

        structure_action = menu.addAction("Structure")
        structure_action.setEnabled(bool(structure_configs.get("count", 0)))
        structure_action.triggered.connect(lambda: self._attach_builtin_context("structure"))

        open_files_action = menu.addAction("Open Files Summary")
        open_files_action.setEnabled(bool(open_files))
        open_files_action.triggered.connect(lambda: self._attach_builtin_context("open_files"))

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

    def _populate_context_menu(self) -> None:
        """Refresh the quick built-in context menu."""
        if self._context_menu is None:
            return

        snapshot = self._current_context_snapshot()
        active_file = snapshot.get("active_file")
        selection = snapshot.get("selection")
        current_row = snapshot.get("current_row")
        structure_configs = snapshot.get("structure_configs") or {}
        open_files = snapshot.get("open_files") or []

        menu = self._context_menu
        menu.clear()

        entries = [
            ("Current File", "current_file", active_file is not None),
            ("Selection", "selection", selection is not None),
            ("Current Row", "current_row", current_row is not None),
            ("Structure", "structure", bool(structure_configs.get("count", 0))),
            ("Open Files", "open_files", bool(open_files)),
        ]
        for label, kind, enabled in entries:
            action = menu.addAction(label)
            action.setEnabled(enabled)
            action.triggered.connect(lambda checked=False, target_kind=kind: self._attach_builtin_context(target_kind))

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

        active_label = "Active file"
        active_tooltip = "Attach the active file to each turn."
        if isinstance(active_file, dict):
            active_name = str(active_file.get("file_name") or active_file.get("target") or "").strip()
            if active_name:
                active_label = "Active file"
                active_tooltip = active_name

        self._active_file_button.setText(active_label)
        self._active_file_button.setToolTip(active_tooltip)
        self._active_file_button.setEnabled(active_file is not None)
        has_context = (
            bool(active_file)
            or bool(selection)
            or bool(current_row)
            or bool(structure_configs.get("count", 0))
            or bool(open_files)
        )
        self._attach_button.setEnabled(has_context)
        self._context_button.setEnabled(has_context)
        self._mention_button.setEnabled(has_context)
        self._prompt_button.setEnabled(True)
        self._preset_button.setEnabled(True)
        if hasattr(self, "_pin_active_file_action"):
            self._pin_active_file_action.setEnabled(active_file is not None)

    def _attach_builtin_context(self, kind: str) -> None:
        """Attach one of the built-in editor-context presets."""
        descriptor = self._builtin_attachment_descriptor(kind)
        if descriptor is None:
            self._status_hint.setText("That context is not available right now.")
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
        self._status_hint.setText(f'Attached "{descriptor.get("label", attachment_id)}"')
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
        self._clear_button.setEnabled(not running)
        self._mode_button.setEnabled(not running)
        self._model_button.setEnabled(not running)
        self._mention_button.setEnabled(not running)
        self._attach_button.setEnabled(not running)
        self._context_button.setEnabled(not running)
        self._preset_button.setEnabled(not running)
        self._prompt_button.setEnabled(not running)
        self._config_button.setEnabled(not running)
        self._active_file_button.setEnabled(not running)
        self._attachment_bar.setEnabled(not running)
        self._status_hint.setText("Running" if running else "Ready")
        if not running:
            self._refresh_context_controls()

    def _on_turn_finished(self, _result: str) -> None:
        self._status_hint.setText("Ready")
        self._refresh_context_controls()

    def _on_turn_failed(self, error_text: str) -> None:
        if error_text == "Agent turn cancelled.":
            self._status_hint.setText("Cancelled")
        else:
            self._status_hint.setText("Failed")
        self._refresh_context_controls()

    def _append_message(self, message: ChatMessage) -> None:
        self._placeholder.setVisible(False)
        card = _MessageCard(message, self)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._message_layout.insertWidget(max(0, self._message_layout.count() - 1), card)
        self._message_cards.append(card)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        scroll_bar = self._scroll_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())
