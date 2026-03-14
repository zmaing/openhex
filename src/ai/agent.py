"""
Agent runtime for the chat-style AI sidebar.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import queue
import re
from statistics import mean
from typing import Any, Callable, Optional, Protocol

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class AgentCancelledError(RuntimeError):
    """Raised when an in-flight agent turn is cancelled."""


@dataclass
class ProviderCapabilities:
    """Capabilities exposed by the active model provider."""

    native_tools: bool = False
    reasoning_summary: bool = False
    model_options: list[str] = field(default_factory=list)


@dataclass
class PacketizationContext:
    """Summary of how the active file is packetized for AI analysis."""

    mode: str = "equal_frame"
    bytes_per_packet: Optional[int] = None
    header_length: Optional[int] = None
    start_offset: int = 0
    packet_count: int = 0
    selected_structure: str = ""
    active_lens: str = "generic"


@dataclass
class PacketDescriptor:
    """Compact description of one packet/frame in the active file."""

    index: int
    offset: int
    header_length: int
    payload_length: int
    total_length: int
    preview_hex: str


@dataclass
class FieldStatistic:
    """Deterministic field-level summary used as AI evidence."""

    field_name: str
    sample_count: int
    unique_count: int
    min: Optional[float] = None
    max: Optional[float] = None
    entropy_hint: str = "unknown"
    likely_kind: str = "unknown"
    confidence: float = 0.0
    evidence_packet_indexes: list[int] = field(default_factory=list)


@dataclass
class AgentRoleConfig:
    """Configuration for one primary or sub-agent."""

    agent_id: str
    label: str
    role: str = "primary"
    provider: str = ""
    model: str = ""
    temperature: Optional[float] = None
    max_steps: Optional[int] = None
    native_tools_enabled: bool = True
    enabled: bool = True
    is_primary: bool = False


@dataclass
class ConsensusArtifact:
    """Structured summary emitted by the primary agent after multi-agent analysis."""

    final_answer: str = ""
    agreements: list[str] = field(default_factory=list)
    disagreements: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: str = "unknown"
    next_actions: list[str] = field(default_factory=list)


@dataclass
class AnalysisWorkspaceState:
    """Shared UI/runtime state for packet-analysis conversations."""

    packet_context: PacketizationContext = field(default_factory=PacketizationContext)
    active_task: str = "profile_packets"
    active_view: str = "consensus"
    expanded_sections: dict[str, bool] = field(default_factory=dict)
    agent_configs: list[AgentRoleConfig] = field(default_factory=list)


@dataclass
class ChatMessage:
    """A rendered chat message in the sidebar transcript."""

    kind: str
    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    collapsed: bool = False

    def to_model_message(self) -> Optional[dict[str, str]]:
        """Convert supported transcript entries to LLM chat messages."""
        if self.kind not in {"user", "assistant"}:
            return None
        return {"role": self.role, "content": self.content}


@dataclass
class ToolSpec:
    """Describes a tool that the agent can invoke."""

    name: str
    description: str
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def schema_for_prompt(self) -> dict[str, Any]:
        """Return a compact JSON-serializable schema for prompt construction."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "required": self.required,
        }

    def schema_for_native_tools(self) -> dict[str, Any]:
        """Return an OpenAI-compatible function tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }

    def validate_arguments(self, arguments: Any) -> tuple[bool, Any]:
        """Validate raw tool-call arguments."""
        if not isinstance(arguments, dict):
            return False, "Tool arguments must be a JSON object."

        unknown = sorted(set(arguments) - set(self.parameters))
        if unknown:
            return False, f"Unknown argument(s): {', '.join(unknown)}"

        normalized: dict[str, Any] = {}
        for name in self.required:
            if name not in arguments:
                return False, f"Missing required argument: {name}"

        for name, value in arguments.items():
            spec = self.parameters.get(name, {})
            expected_type = spec.get("type")

            if expected_type == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    return False, f"Argument '{name}' must be an integer."
                minimum = spec.get("minimum")
                maximum = spec.get("maximum")
                if minimum is not None and value < minimum:
                    return False, f"Argument '{name}' must be >= {minimum}."
                if maximum is not None and value > maximum:
                    return False, f"Argument '{name}' must be <= {maximum}."
            elif expected_type == "string":
                if not isinstance(value, str):
                    return False, f"Argument '{name}' must be a string."
                allowed = spec.get("enum")
                if allowed and value not in allowed:
                    return False, f"Argument '{name}' must be one of: {', '.join(map(str, allowed))}."
            elif expected_type == "boolean":
                if not isinstance(value, bool):
                    return False, f"Argument '{name}' must be a boolean."
            elif expected_type == "object":
                if not isinstance(value, dict):
                    return False, f"Argument '{name}' must be an object."

            normalized[name] = value

        return True, normalized


@dataclass
class ToolInvocation:
    """A single tool call requested by the LLM."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """The result of a tool invocation."""

    name: str
    success: bool
    content: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_model_payload(self) -> dict[str, Any]:
        """Serialize the tool result back into the model loop."""
        return {
            "tool_name": self.name,
            "success": self.success,
            "content": self.content,
            "data": self.data,
        }


@dataclass
class AgentSession:
    """In-memory transcript storage for the sidebar."""

    messages: list[ChatMessage] = field(default_factory=list)

    def clear(self) -> None:
        """Clear the current transcript."""
        self.messages.clear()

    def append(self, message: ChatMessage) -> None:
        """Append a new message to the transcript."""
        self.messages.append(message)

    def to_model_messages(self, *, channel: Optional[str] = None) -> list[dict[str, str]]:
        """Return the user/assistant history to reuse in later turns."""
        result: list[dict[str, str]] = []
        for message in self.messages:
            if channel is not None:
                message_channel = str(message.metadata.get("channel", "") or "").strip()
                if message_channel and message_channel != channel:
                    continue
            converted = message.to_model_message()
            if converted is not None:
                result.append(converted)
        return result


class AgentToolHost(Protocol):
    """Protocol for the UI bridge exposed to the agent runner."""

    def tool_specs(self) -> list[ToolSpec]:
        """Return tool specs available to the current runtime."""

    def build_default_context(self) -> dict[str, Any]:
        """Return the default editor context summary for each turn."""

    def invoke_tool(self, invocation: ToolInvocation) -> ToolResult:
        """Execute a tool invocation on the main thread."""


class AgentTurnExecutor:
    """Synchronous agent loop that can be reused in tests and worker threads."""

    def __init__(
        self,
        provider: Any,
        tool_specs: list[ToolSpec],
        default_context: dict[str, Any],
        execute_tool: Callable[[ToolInvocation], ToolResult],
        *,
        max_steps: int = 8,
        is_cancelled: Optional[Callable[[], bool]] = None,
        system_prompt_parts: Optional[list[str]] = None,
        extra_system_messages: Optional[list[str]] = None,
        emit_user_message: bool = True,
    ):
        self._provider = provider
        self._tool_specs = {spec.name: spec for spec in tool_specs}
        self._tool_specs_list = tool_specs
        self._default_context = default_context
        self._execute_tool = execute_tool
        self._max_steps = max_steps
        self._is_cancelled = is_cancelled or (lambda: False)
        self._system_prompt_parts = [str(part).strip() for part in (system_prompt_parts or []) if str(part).strip()]
        self._extra_system_messages = [str(part).strip() for part in (extra_system_messages or []) if str(part).strip()]
        self._emit_user_message = bool(emit_user_message)

    def execute(
        self,
        history_messages: list[dict[str, str]],
        prompt: str,
        *,
        display_prompt: Optional[str] = None,
        on_message: Optional[Callable[[ChatMessage], None]] = None,
    ) -> list[ChatMessage]:
        """Run one complete user turn."""
        emitted: list[ChatMessage] = []

        def emit(message: ChatMessage) -> None:
            emitted.append(message)
            if on_message is not None:
                on_message(message)

        model_messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {
                "role": "system",
                "content": (
                    "Current editor context (summary only, use tools for byte data):\n"
                    f"{json.dumps(self._default_context, ensure_ascii=False, indent=2)}"
                ),
            },
            *[
                {"role": "system", "content": content}
                for content in self._extra_system_messages
            ],
            *history_messages,
        ]

        visible_prompt = str(display_prompt or prompt).strip() or prompt
        if self._emit_user_message:
            emit(ChatMessage(kind="user", role="user", content=visible_prompt))
        model_messages.append({"role": "user", "content": prompt})

        for step in range(1, self._max_steps + 1):
            self._check_cancelled()
            emit(
                ChatMessage(
                    kind="thinking",
                    role="system",
                    content=f"Thinking (step {step}/{self._max_steps})",
                    metadata={"step": step},
                )
            )

            parsed_response, raw_response = self._request_valid_response(model_messages)
            self._check_cancelled()

            response_type = parsed_response.get("type")
            if response_type in {"assistant", "respond", "final"}:
                content = str(parsed_response.get("content", "")).strip()
                if not content:
                    raise RuntimeError("Assistant response was empty.")
                emit(ChatMessage(kind="assistant", role="assistant", content=content))
                return emitted

            invocation = self._build_tool_invocation(parsed_response, raw_response)
            emit(
                ChatMessage(
                    kind="tool_call",
                    role="assistant",
                    content=json.dumps(
                        {
                            "tool_name": invocation.name,
                            "arguments": invocation.arguments,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    metadata={
                        "tool_name": invocation.name,
                        "arguments": invocation.arguments,
                        "step": step,
                    },
                )
            )

            self._check_cancelled()
            tool_result = self._execute_tool(invocation)
            emit(
                ChatMessage(
                    kind="tool_result",
                    role="tool",
                    content=tool_result.content,
                    metadata={
                        "tool_name": tool_result.name,
                        "success": tool_result.success,
                        "data": tool_result.data,
                        "step": step,
                    },
                    collapsed=True,
                )
            )

            model_messages.append({"role": "assistant", "content": raw_response})
            model_messages.append(
                {
                    "role": "user",
                    "content": (
                        "Tool result:\n"
                        f"{json.dumps(tool_result.to_model_payload(), ensure_ascii=False, indent=2)}"
                    ),
                }
            )

            if not tool_result.success:
                model_messages.append(
                    {
                        "role": "system",
                        "content": (
                            "The tool call failed. You may recover by calling another tool or by"
                            " answering the user directly with the limitation."
                        ),
                    }
                )

        raise RuntimeError("Agent reached the maximum number of tool/response steps.")

    def _request_valid_response(
        self,
        model_messages: list[dict[str, str]],
    ) -> tuple[dict[str, Any], str]:
        """Request a single valid JSON envelope from the model."""
        repair_used = False
        local_messages = list(model_messages)

        while True:
            self._check_cancelled()
            native_response = self._request_native_tool_response(local_messages)
            if native_response is not None:
                parsed = native_response
                raw_response = json.dumps(parsed, ensure_ascii=False)
            else:
                raw_response = str(self._provider.complete(local_messages))
            provider_error = self._extract_provider_error(raw_response)
            if provider_error is not None:
                raise RuntimeError(provider_error)
            if native_response is not None:
                error = self._validate_model_payload(parsed)
                if error is None:
                    return parsed, raw_response
            else:
                parsed, error = self._parse_model_response(raw_response)
                if error is None:
                    payload_error = self._validate_model_payload(parsed)
                    if payload_error is None:
                        return parsed, raw_response
                    error = payload_error

            if error is None:
                return parsed, raw_response

            if repair_used:
                fallback_payload = self._coerce_plaintext_assistant(raw_response)
                if fallback_payload is not None:
                    return fallback_payload, raw_response
                raise RuntimeError(f"Model produced invalid agent JSON twice: {error}")

            repair_used = True
            local_messages.append({"role": "assistant", "content": raw_response})
            local_messages.append(
                {
                    "role": "system",
                    "content": (
                        "Your previous response was invalid. "
                        f"Error: {error} "
                        "Reply again with exactly one JSON object and no surrounding text."
                    ),
                }
            )

    def _provider_capabilities(self) -> ProviderCapabilities:
        """Return provider capability flags when the provider exposes them."""
        capabilities = getattr(self._provider, "capabilities", None)
        if isinstance(capabilities, ProviderCapabilities):
            return capabilities
        if capabilities is not None:
            native_tools = bool(getattr(capabilities, "native_tools", False))
            reasoning_summary = bool(getattr(capabilities, "reasoning_summary", False))
            model_options = list(getattr(capabilities, "model_options", []) or [])
            return ProviderCapabilities(
                native_tools=native_tools,
                reasoning_summary=reasoning_summary,
                model_options=model_options,
            )
        return ProviderCapabilities()

    def _request_native_tool_response(
        self,
        model_messages: list[dict[str, str]],
    ) -> Optional[dict[str, Any]]:
        """Use provider-native tool calling when available."""
        capabilities = self._provider_capabilities()
        if not capabilities.native_tools or not self._tool_specs_list:
            return None

        complete_with_tools = getattr(self._provider, "complete_with_tools", None)
        if not callable(complete_with_tools):
            return None

        native_payload = complete_with_tools(
            model_messages,
            [spec.schema_for_native_tools() for spec in self._tool_specs_list],
        )
        if not isinstance(native_payload, dict):
            return None
        return native_payload

    def _extract_provider_error(self, raw_response: str) -> Optional[str]:
        """Treat provider-generated error strings as hard failures, not assistant replies."""
        text = str(raw_response or "").strip()
        if not text:
            return None

        lowered = text.lower()
        if lowered.startswith("error:"):
            return text[6:].strip() or text
        if text == "No response from AI":
            return text
        return None

    def _coerce_plaintext_assistant(self, raw_response: str) -> Optional[dict[str, Any]]:
        """Fallback for models that never follow the JSON envelope."""
        text = str(raw_response or "").strip()
        if not text:
            return None

        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()

        if not text:
            return None

        return {
            "type": "assistant",
            "content": text,
        }

    def _validate_model_payload(self, payload: dict[str, Any]) -> Optional[str]:
        """Validate the parsed payload against the tool registry."""
        response_type = payload.get("type")
        if response_type != "tool_call":
            return None

        tool_name = str(payload.get("tool_name", "")).strip()
        spec = self._tool_specs.get(tool_name)
        if spec is None:
            return f"Unknown tool requested: {tool_name}"

        valid, result = spec.validate_arguments(payload.get("arguments", {}))
        if not valid:
            return f"Invalid arguments for '{tool_name}': {result}"

        payload["arguments"] = result
        return None

    def _parse_model_response(self, raw_response: str) -> tuple[dict[str, Any], Optional[str]]:
        """Parse and validate the model envelope."""
        text = raw_response.strip()
        if not text:
            return {}, "Empty response."

        provider_tool_payload = self._parse_provider_tool_markup(text)
        if provider_tool_payload is not None:
            return provider_tool_payload, None

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                return {}, "Response was not valid JSON."
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                return {}, f"Response was not valid JSON: {exc}"

        if not isinstance(payload, dict):
            return {}, "Top-level JSON value must be an object."

        response_type = payload.get("type")
        if not isinstance(response_type, str):
            return {}, "Response must include a string 'type'."

        if response_type in {"assistant", "respond", "final"}:
            content = payload.get("content")
            if not isinstance(content, str) or not content.strip():
                return {}, "Assistant response must include non-empty string 'content'."
            return payload, None

        if response_type == "tool_call":
            tool_name = payload.get("tool_name")
            arguments = payload.get("arguments")
            if not isinstance(tool_name, str) or not tool_name.strip():
                return {}, "Tool call must include string 'tool_name'."
            if not isinstance(arguments, dict):
                return {}, "Tool call must include object 'arguments'."
            return payload, None

        return {}, "Unsupported response type."

    def _parse_provider_tool_markup(self, raw_response: str) -> Optional[dict[str, Any]]:
        """Accept provider-specific XML-like tool call formats as a fallback."""
        text = str(raw_response or "").strip()
        if not text:
            return None

        tool_block = self._extract_xml_block(text, "tool_calls")
        if tool_block:
            json_payload = self._parse_tool_calls_json_block(tool_block)
            if json_payload is not None:
                return json_payload

        minimax_block = self._extract_xml_block(text, "tool_call")
        if minimax_block:
            minimax_invoke_payload = self._parse_xml_invoke_tool_call(minimax_block)
            if minimax_invoke_payload is not None:
                return minimax_invoke_payload
            minimax_payload = self._parse_xml_attribute_tool_call(minimax_block)
            if minimax_payload is not None:
                return minimax_payload

        minimax_invoke_payload = self._parse_xml_invoke_tool_call(text)
        if minimax_invoke_payload is not None:
            return minimax_invoke_payload

        minimax_payload = self._parse_xml_attribute_tool_call(text)
        if minimax_payload is not None:
            return minimax_payload

        return None

    def _extract_xml_block(self, text: str, tag_name: str) -> Optional[str]:
        """Extract the first XML-like block content for a tag."""
        match = re.search(
            rf"<(?:[A-Za-z_][\w.-]*:)?{tag_name}>(.*?)</(?:[A-Za-z_][\w.-]*:)?{tag_name}>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip()
        return None

    def _parse_tool_calls_json_block(self, text: str) -> Optional[dict[str, Any]]:
        """Parse MiniMax-style <tool_calls> JSON payloads."""
        cleaned = text.strip()
        if not cleaned:
            return None

        candidates = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if cleaned.startswith("{") and cleaned.endswith("}"):
            candidates.insert(0, cleaned)

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue

            tool_name = payload.get("name") or payload.get("tool_name")
            arguments = payload.get("arguments", {})
            if isinstance(tool_name, str) and isinstance(arguments, dict):
                return {
                    "type": "tool_call",
                    "tool_name": tool_name,
                    "arguments": arguments,
                }

        return None

    def _parse_xml_attribute_tool_call(self, text: str) -> Optional[dict[str, Any]]:
        """Parse XML-like attribute tool calls such as <tool_name=\"read_bytes\" .../>."""
        if "<tool_name=" not in text:
            return None

        attributes = {
            key: self._coerce_tool_argument(value)
            for key, value in re.findall(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"', text)
        }
        tool_name = attributes.pop("tool_name", None)
        if not isinstance(tool_name, str) or not tool_name.strip():
            return None

        return {
            "type": "tool_call",
            "tool_name": tool_name,
            "arguments": attributes,
        }

    def _parse_xml_invoke_tool_call(self, text: str) -> Optional[dict[str, Any]]:
        """Parse XML-like invoke markup such as <invoke name=\"detect_patterns\">...</invoke>."""
        invoke_match = re.search(
            r'<invoke\s+name="([^"]+)"\s*>(.*?)</invoke>',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if invoke_match is None:
            return None

        tool_name = invoke_match.group(1).strip()
        if not tool_name:
            return None

        body = invoke_match.group(2)
        arguments = {
            name: self._coerce_tool_argument(value.strip())
            for name, value in re.findall(
                r'<parameter\s+name="([^"]+)"\s*>(.*?)</parameter>',
                body,
                flags=re.IGNORECASE | re.DOTALL,
            )
        }
        return {
            "type": "tool_call",
            "tool_name": tool_name,
            "arguments": arguments,
        }

    def _coerce_tool_argument(self, value: str) -> Any:
        """Convert XML-style string attributes into JSON-compatible values."""
        text = str(value)
        lowered = text.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False

        if re.fullmatch(r"-?\d+", text):
            try:
                return int(text)
            except ValueError:
                return text

        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        return text

    def _build_tool_invocation(
        self,
        payload: dict[str, Any],
        raw_response: str,
    ) -> ToolInvocation:
        """Validate the requested tool invocation against the registered specs."""
        tool_name = str(payload.get("tool_name", "")).strip()
        return ToolInvocation(name=tool_name, arguments=payload.get("arguments", {}))

    def _check_cancelled(self) -> None:
        """Abort execution if cancellation was requested."""
        if self._is_cancelled():
            raise AgentCancelledError("Agent turn cancelled.")

    def _build_system_prompt(self) -> str:
        """Build the fixed system prompt for the agent runtime."""
        tools_payload = [spec.schema_for_prompt() for spec in self._tool_specs_list]
        parts = list(self._system_prompt_parts)
        if not parts:
            parts = [
                "Runtime Contract:\n"
                "- Reply with exactly one JSON object.\n"
                "- Allowed response shapes:\n"
                '  {"type":"assistant","content":"..."}\n'
                '  {"type":"tool_call","tool_name":"...","arguments":{...}}\n'
                "- Call at most one tool per response.\n"
                "- Do not invent tool names or arguments.\n"
                "- Every conclusion must point to concrete packet indexes, field names, offsets,"
                " or deterministic statistics.\n"
                "- If evidence is insufficient, say so explicitly and propose the next check.",
                "Core Packet Analyst:\n"
                "You are embedded inside a binary and protocol analysis editor. Your job is to"
                " explain packet structure, summarize known-field规律, and infer plausible"
                " meanings for unknown fields from deterministic evidence.",
                "Tool Rules:\n"
                "- Use tools whenever you need packet bytes, structure decoding, statistics,"
                " field correlations, metadata, or packet comparisons.\n"
                "- Navigation tools are only for explicit user requests to move the cursor,"
                " switch files, or highlight ranges.\n"
                "- Default context only contains summaries, not raw packet bytes.",
            ]

        parts.append(f"Available tools:\n{json.dumps(tools_payload, ensure_ascii=False, indent=2)}")
        return "\n\n".join(part for part in parts if str(part).strip())


class _AgentWorker(QThread):
    """Worker thread used by AgentRunner to keep the UI responsive."""

    message_emitted = pyqtSignal(object)
    turn_succeeded = pyqtSignal()
    turn_failed = pyqtSignal(str)
    tool_requested = pyqtSignal(object, object)

    def __init__(
        self,
        provider: Any,
        history_messages: list[dict[str, str]],
        prompt: str,
        display_prompt: str,
        tool_specs: list[ToolSpec],
        default_context: dict[str, Any],
        *,
        max_steps: int = 8,
        system_prompt_parts: Optional[list[str]] = None,
        extra_system_messages: Optional[list[str]] = None,
        emit_user_message: bool = True,
        message_metadata: Optional[dict[str, Any]] = None,
    ):
        super().__init__()
        self._provider = provider
        self._history_messages = history_messages
        self._prompt = prompt
        self._display_prompt = display_prompt
        self._tool_specs = tool_specs
        self._default_context = default_context
        self._max_steps = max_steps
        self._cancelled = False
        self._system_prompt_parts = list(system_prompt_parts or [])
        self._extra_system_messages = list(extra_system_messages or [])
        self._emit_user_message = bool(emit_user_message)
        self._message_metadata = dict(message_metadata or {})

    def cancel(self) -> None:
        """Request cancellation for the active turn."""
        self._cancelled = True
        provider_cancel = getattr(self._provider, "cancel", None)
        if callable(provider_cancel):
            provider_cancel()

    def run(self) -> None:
        """Execute the turn loop."""
        executor = AgentTurnExecutor(
            self._provider,
            self._tool_specs,
            self._default_context,
            self._invoke_tool_on_main_thread,
            max_steps=self._max_steps,
            is_cancelled=lambda: self._cancelled,
            system_prompt_parts=self._system_prompt_parts,
            extra_system_messages=self._extra_system_messages,
            emit_user_message=self._emit_user_message,
        )

        try:
            executor.execute(
                self._history_messages,
                self._prompt,
                display_prompt=self._display_prompt,
                on_message=self._emit_message,
            )
        except AgentCancelledError as exc:
            self.turn_failed.emit(str(exc))
        except Exception as exc:
            self.turn_failed.emit(str(exc))
        else:
            self.turn_succeeded.emit()

    def _invoke_tool_on_main_thread(self, invocation: ToolInvocation) -> ToolResult:
        """Synchronously execute a tool call on the UI thread."""
        result_queue: queue.Queue[Any] = queue.Queue(maxsize=1)
        self.tool_requested.emit(invocation, result_queue)
        result = result_queue.get()
        if isinstance(result, Exception):
            raise result
        return result

    def _emit_message(self, message: ChatMessage) -> None:
        """Attach worker-level metadata before forwarding a transcript message."""
        metadata = dict(message.metadata)
        metadata.update(self._message_metadata)
        self.message_emitted.emit(replace(message, metadata=metadata))


def _domain_lens_prompt(lens: str) -> str:
    """Return a compact domain-specific analysis lens."""
    normalized = str(lens or "generic").strip().lower()
    prompts = {
        "network": (
            "Domain Lens: network/protocol\n"
            "- Pay extra attention to length fields, type fields, checksums, sequence numbers,"
            " flags, addresses, and payload/header boundaries."
        ),
        "network/protocol": (
            "Domain Lens: network/protocol\n"
            "- Pay extra attention to length fields, type fields, checksums, sequence numbers,"
            " flags, addresses, and payload/header boundaries."
        ),
        "satellite": (
            "Domain Lens: satellite telemetry\n"
            "- Look for frame counters, timestamps, subsystem status words, sensor payload"
            " blocks, and engineering-unit scaling patterns."
        ),
        "satellite telemetry": (
            "Domain Lens: satellite telemetry\n"
            "- Look for frame counters, timestamps, subsystem status words, sensor payload"
            " blocks, and engineering-unit scaling patterns."
        ),
        "industrial": (
            "Domain Lens: industrial/serial\n"
            "- Look for function codes, register addresses, CRC/checksum fields, channel IDs,"
            " and fixed payload templates."
        ),
        "industrial/serial": (
            "Domain Lens: industrial/serial\n"
            "- Look for function codes, register addresses, CRC/checksum fields, channel IDs,"
            " and fixed payload templates."
        ),
    }
    return prompts.get(
        normalized,
        "Domain Lens: generic\n"
        "- Prefer conservative interpretations. Separate observations from hypotheses and cite"
        " deterministic evidence for every claim.",
    )


def _task_overlay_prompt(task_name: str) -> str:
    """Describe the currently selected packet-analysis task."""
    normalized = str(task_name or "profile_packets").strip().lower()
    overlays = {
        "profile_packets": "Task Focus: summarize packet layout, stable fields, changing fields, and field groups.",
        "infer_unknown_fields": "Task Focus: infer plausible meanings for unknown fields and rank competing hypotheses.",
        "validate_known_fields": "Task Focus: validate known field assumptions against observed packet evidence and point out mismatches.",
        "compare_packet_groups": "Task Focus: compare packet cohorts or samples and explain the most meaningful differences.",
        "generate_parser": "Task Focus: produce parser-ready conclusions and highlight assumptions required before code generation.",
    }
    return overlays.get(normalized, overlays["profile_packets"])


def _role_overlay_prompt(config: AgentRoleConfig, *, has_subagents: bool) -> str:
    """Return role-specific instructions for a primary or sub-agent."""
    if config.is_primary or config.role == "primary":
        if has_subagents:
            return (
                "Role Overlay: primary agent\n"
                "- You are the final decision-maker.\n"
                "- Review sub-agent findings, resolve disagreements, and deliver the final answer.\n"
                "- Keep clear sections: Observed packet规律, Known fields summary, Unknown field hypotheses,"
                " Disagreements, Recommended next checks."
            )
        return (
            "Role Overlay: primary agent\n"
            "- Analyze the request directly.\n"
            "- Keep clear sections: Observed packet规律, Known fields summary, Unknown field hypotheses,"
            " Disagreements, Recommended next checks."
        )

    return (
        f"Role Overlay: sub-agent {config.label}\n"
        "- Work independently and focus on evidence gathering.\n"
        "- Challenge easy assumptions, note alternative interpretations, and report uncertainty explicitly.\n"
        "- End with a short Findings / Risks / Next checks structure."
    )


def _build_system_prompt_parts(
    config: AgentRoleConfig,
    workspace_state: AnalysisWorkspaceState,
    *,
    has_subagents: bool,
) -> list[str]:
    """Assemble the layered prompt stack for one agent role."""
    packet_context = workspace_state.packet_context
    packet_summary = (
        f"Packet Context:\n- mode: {packet_context.mode}\n"
        f"- packet_count: {packet_context.packet_count}\n"
        f"- start_offset: {packet_context.start_offset}\n"
        f"- selected_structure: {packet_context.selected_structure or 'none'}"
    )
    return [
        "Runtime Contract:\n"
        "- Reply with valid tool output or a grounded answer.\n"
        "- Tie all claims to packets, fields, offsets, or statistics.\n"
        "- Never present guesses as facts.",
        "Core Packet Analyst:\n"
        "You analyze packetized binary data, summarize known fields, and infer unknown field meaning from evidence.",
        _domain_lens_prompt(packet_context.active_lens),
        _task_overlay_prompt(workspace_state.active_task),
        packet_summary,
        _role_overlay_prompt(config, has_subagents=has_subagents),
    ]


def _extract_final_assistant(messages: list[ChatMessage]) -> str:
    """Return the last assistant utterance from a finished agent turn."""
    for message in reversed(messages):
        if message.kind == "assistant":
            return str(message.content or "").strip()
    return ""


class _ConsensusWorker(QThread):
    """Worker that orchestrates a primary agent with optional sub-agents."""

    message_emitted = pyqtSignal(object)
    turn_succeeded = pyqtSignal()
    turn_failed = pyqtSignal(str)
    tool_requested = pyqtSignal(object, object)

    def __init__(
        self,
        ai_manager: Any,
        history_messages: list[dict[str, str]],
        prompt: str,
        display_prompt: str,
        tool_specs: list[ToolSpec],
        default_context: dict[str, Any],
        workspace_state: AnalysisWorkspaceState,
        agent_configs: list[AgentRoleConfig],
        *,
        max_steps: int = 8,
    ):
        super().__init__()
        self._ai_manager = ai_manager
        self._history_messages = history_messages
        self._prompt = prompt
        self._display_prompt = display_prompt
        self._tool_specs = tool_specs
        self._default_context = default_context
        self._workspace_state = workspace_state
        self._agent_configs = list(agent_configs)
        self._max_steps = max_steps
        self._cancelled = False
        self._active_providers: list[Any] = []

    def cancel(self) -> None:
        """Request cancellation for all in-flight agent providers."""
        self._cancelled = True
        for provider in list(self._active_providers):
            provider_cancel = getattr(provider, "cancel", None)
            if callable(provider_cancel):
                provider_cancel()

    def run(self) -> None:
        """Run sub-agents first, then let the primary agent synthesize the result."""
        try:
            active_configs = [config for config in self._agent_configs if config.enabled]
            if not active_configs:
                active_configs = [
                    AgentRoleConfig(
                        agent_id="primary",
                        label="Main Agent",
                        role="primary",
                        is_primary=True,
                    )
                ]

            primary = next((config for config in active_configs if config.is_primary), active_configs[0])
            subagents = [config for config in active_configs if config.agent_id != primary.agent_id]

            if not subagents:
                self._run_role(
                    primary,
                    history_messages=self._history_messages,
                    emit_user_message=True,
                    extra_system_messages=[],
                    message_metadata={
                        "agent_id": primary.agent_id,
                        "agent_label": primary.label,
                        "channel": "consensus",
                        "channels": ["consensus", primary.agent_id],
                    },
                )
                self.turn_succeeded.emit()
                return

            self._emit_message(
                ChatMessage(kind="user", role="user", content=self._display_prompt),
                {
                    "agent_id": primary.agent_id,
                    "agent_label": primary.label,
                    "channel": "consensus",
                },
            )

            findings: list[dict[str, Any]] = []
            for config in subagents:
                self._check_cancelled()
                messages = self._run_role(
                    config,
                    history_messages=[],
                    emit_user_message=True,
                    extra_system_messages=[
                        "Sub-agent assignment:\nWork independently. Focus on gathering evidence and"
                        " highlighting alternative interpretations for the primary agent."
                    ],
                    message_metadata={
                        "agent_id": config.agent_id,
                        "agent_label": config.label,
                        "channel": config.agent_id,
                    },
                )
                findings.append(
                    {
                        "agent_id": config.agent_id,
                        "label": config.label,
                        "summary": _extract_final_assistant(messages),
                    }
                )

            primary_extra = [
                "Sub-agent findings (review these before answering):\n"
                + json.dumps(findings, ensure_ascii=False, indent=2)
            ]
            self._run_role(
                primary,
                history_messages=self._history_messages,
                emit_user_message=False,
                extra_system_messages=primary_extra,
                message_metadata={
                    "agent_id": primary.agent_id,
                    "agent_label": primary.label,
                    "channel": "consensus",
                    "channels": ["consensus", primary.agent_id],
                },
            )
        except AgentCancelledError as exc:
            self.turn_failed.emit(str(exc))
        except Exception as exc:
            self.turn_failed.emit(str(exc))
        else:
            self.turn_succeeded.emit()

    def _run_role(
        self,
        config: AgentRoleConfig,
        *,
        history_messages: list[dict[str, str]],
        emit_user_message: bool,
        extra_system_messages: list[str],
        message_metadata: dict[str, Any],
    ) -> list[ChatMessage]:
        """Execute one agent role synchronously inside the orchestration worker."""
        provider = self._create_provider(config)
        self._active_providers.append(provider)
        try:
            max_steps = config.max_steps if config.max_steps is not None else self._max_steps
            executor = AgentTurnExecutor(
                provider,
                self._tool_specs,
                self._default_context,
                self._invoke_tool_on_main_thread,
                max_steps=max_steps,
                is_cancelled=lambda: self._cancelled,
                system_prompt_parts=_build_system_prompt_parts(
                    config,
                    self._workspace_state,
                    has_subagents=any(
                        other.enabled and other.agent_id != config.agent_id
                        for other in self._agent_configs
                    ),
                ),
                extra_system_messages=extra_system_messages,
                emit_user_message=emit_user_message,
            )

            return executor.execute(
                history_messages,
                self._prompt,
                display_prompt=self._display_prompt,
                on_message=lambda message: self._emit_message(message, message_metadata),
            )
        finally:
            if provider in self._active_providers:
                self._active_providers.remove(provider)

    def _create_provider(self, config: AgentRoleConfig) -> Any:
        """Create a model provider for one role configuration."""
        factory = getattr(self._ai_manager, "create_completion_provider_for_config", None)
        if callable(factory):
            provider = factory(config)
            if provider is not None:
                return provider

        fallback = getattr(self._ai_manager, "create_completion_provider", None)
        if callable(fallback):
            provider = fallback()
            if provider is not None:
                return provider

        raise RuntimeError(f"No AI provider configured for {config.label}.")

    def _emit_message(self, message: ChatMessage, message_metadata: dict[str, Any]) -> None:
        """Forward one message with agent metadata attached."""
        metadata = dict(message.metadata)
        metadata.update(message_metadata)
        self.message_emitted.emit(replace(message, metadata=metadata))

    def _invoke_tool_on_main_thread(self, invocation: ToolInvocation) -> ToolResult:
        """Synchronously execute a tool call on the UI thread."""
        result_queue: queue.Queue[Any] = queue.Queue(maxsize=1)
        self.tool_requested.emit(invocation, result_queue)
        result = result_queue.get()
        if isinstance(result, Exception):
            raise result
        return result

    def _check_cancelled(self) -> None:
        """Abort when the outer runner requests cancellation."""
        if self._cancelled:
            raise AgentCancelledError("Agent turn cancelled.")


class AgentRunner(QObject):
    """Orchestrates worker-thread execution for the chat sidebar."""

    message_emitted = pyqtSignal(object)
    running_changed = pyqtSignal(bool)
    turn_finished = pyqtSignal(str)
    turn_failed = pyqtSignal(str)

    def __init__(self, ai_manager: Any, tool_host: AgentToolHost, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._ai_manager = ai_manager
        self._tool_host = tool_host
        self._worker: Optional[QThread] = None
        self._run_id = 0
        self._running = False
        self._max_steps = 8
        self._disabled_tool_names: set[str] = set()
        self._workspace_state = AnalysisWorkspaceState()
        self._agent_configs: list[AgentRoleConfig] = [
            AgentRoleConfig(
                agent_id="primary",
                label="Main Agent",
                role="primary",
                is_primary=True,
            )
        ]

    @property
    def is_running(self) -> bool:
        """Return whether a turn is currently active."""
        return self._running

    def set_tool_host(self, tool_host: AgentToolHost) -> None:
        """Replace the active tool host."""
        self._tool_host = tool_host

    def set_max_steps(self, max_steps: int) -> None:
        """Update the step budget for future turns."""
        self._max_steps = max(1, int(max_steps))

    def set_workspace_state(self, workspace_state: AnalysisWorkspaceState) -> None:
        """Replace the shared packet-analysis workspace state."""
        self._workspace_state = workspace_state

    def set_agent_configs(self, configs: list[AgentRoleConfig]) -> None:
        """Replace the active primary/sub-agent configuration."""
        normalized = [config for config in configs if isinstance(config, AgentRoleConfig)]
        if not normalized:
            normalized = [
                AgentRoleConfig(
                    agent_id="primary",
                    label="Main Agent",
                    role="primary",
                    is_primary=True,
                )
            ]
        if not any(config.is_primary for config in normalized):
            normalized[0].is_primary = True
        self._agent_configs = normalized

    def set_disabled_tools(self, disabled_tool_names: set[str]) -> None:
        """Disable a subset of registered tools for future turns."""
        self._disabled_tool_names = {str(name).strip() for name in disabled_tool_names if str(name).strip()}

    def _tool_specs_for_turn(self) -> list[ToolSpec]:
        """Return the currently enabled tool specs."""
        specs = self._tool_host.tool_specs()
        if not self._disabled_tool_names:
            return specs
        return [spec for spec in specs if spec.name not in self._disabled_tool_names]

    def _active_agent_configs(self) -> list[AgentRoleConfig]:
        """Return enabled agent configs, always keeping one primary config."""
        configs = [config for config in self._agent_configs if config.enabled]
        if not configs:
            configs = [
                AgentRoleConfig(
                    agent_id="primary",
                    label="Main Agent",
                    role="primary",
                    is_primary=True,
                )
            ]
        if not any(config.is_primary for config in configs):
            configs[0].is_primary = True
        return configs

    def start_turn(
        self,
        session: AgentSession,
        prompt: str,
        *,
        display_prompt: Optional[str] = None,
    ) -> bool:
        """Start a new user turn asynchronously."""
        prompt = str(prompt or "").strip()
        if not prompt:
            return False

        if self._worker is not None and self._worker.isRunning():
            return False

        if not getattr(self._ai_manager, "is_enabled", True):
            error_text = "AI features are disabled."
            self.message_emitted.emit(ChatMessage(kind="error", role="system", content=error_text))
            self.turn_failed.emit(error_text)
            return False

        self._run_id += 1
        run_id = self._run_id
        active_configs = self._active_agent_configs()
        primary = next((config for config in active_configs if config.is_primary), active_configs[0])
        history_messages = session.to_model_messages(channel="consensus")
        tool_specs = self._tool_specs_for_turn()
        default_context = self._tool_host.build_default_context()
        packetization = default_context.get("packetization")
        if isinstance(packetization, dict):
            self._workspace_state.packet_context = PacketizationContext(
                mode=str(packetization.get("mode", "equal_frame")),
                bytes_per_packet=packetization.get("bytes_per_packet"),
                header_length=packetization.get("header_length"),
                start_offset=int(packetization.get("start_offset", 0)),
                packet_count=int(packetization.get("packet_count", 0)),
                selected_structure=str(packetization.get("selected_structure", "") or ""),
                active_lens=str(self._workspace_state.packet_context.active_lens or "generic"),
            )
        self._workspace_state.agent_configs = [replace(config) for config in active_configs]

        worker: QThread
        if len(active_configs) > 1:
            worker = _ConsensusWorker(
                self._ai_manager,
                history_messages,
                prompt,
                str(display_prompt or prompt),
                tool_specs,
                default_context,
                self._workspace_state,
                active_configs,
                max_steps=self._max_steps,
            )
        else:
            provider_factory = getattr(self._ai_manager, "create_completion_provider_for_config", None)
            provider = provider_factory(primary) if callable(provider_factory) else None
            if provider is None:
                fallback = getattr(self._ai_manager, "create_completion_provider", None)
                provider = fallback() if callable(fallback) else None
            if provider is None:
                error_text = "No AI provider configured."
                self.message_emitted.emit(ChatMessage(kind="error", role="system", content=error_text))
                self.turn_failed.emit(error_text)
                return False

            worker = _AgentWorker(
                provider,
                history_messages,
                prompt,
                str(display_prompt or prompt),
                tool_specs,
                default_context,
                max_steps=self._max_steps,
                system_prompt_parts=_build_system_prompt_parts(
                    primary,
                    self._workspace_state,
                    has_subagents=False,
                ),
                message_metadata={
                    "agent_id": primary.agent_id,
                    "agent_label": primary.label,
                    "channel": "consensus",
                    "channels": ["consensus", primary.agent_id],
                },
            )
        worker.message_emitted.connect(lambda message, token=run_id: self._forward_message(token, message))
        worker.tool_requested.connect(self._on_tool_requested)
        worker.turn_succeeded.connect(lambda token=run_id: self._on_turn_succeeded(token))
        worker.turn_failed.connect(lambda error, token=run_id: self._on_turn_failed(token, error))
        worker.finished.connect(lambda token=run_id: self._on_worker_finished(token))

        self._worker = worker
        self._set_running(True)
        worker.start()
        return True

    def cancel(self) -> None:
        """Cancel the active turn."""
        if self._worker is None:
            return

        if self._worker.isRunning():
            self._worker.cancel()

        self._run_id += 1
        self._set_running(False)
        self.turn_failed.emit("Agent turn cancelled.")

    def shutdown(self, timeout_ms: int = 500) -> None:
        """Best-effort shutdown for widget teardown and app exit."""
        if self._worker is None:
            return

        worker = self._worker
        if worker.isRunning():
            worker.cancel()
            if not worker.wait(timeout_ms):
                worker.terminate()
                worker.wait(timeout_ms)

        self._worker = None
        self._set_running(False)

    def run_turn_sync(
        self,
        session: AgentSession,
        prompt: str,
        *,
        display_prompt: Optional[str] = None,
    ) -> list[ChatMessage]:
        """Run a turn synchronously. Intended for tests and non-UI callers."""
        active_configs = self._active_agent_configs()
        if len(active_configs) > 1:
            worker = _ConsensusWorker(
                self._ai_manager,
                session.to_model_messages(channel="consensus"),
                prompt,
                str(display_prompt or prompt),
                self._tool_specs_for_turn(),
                self._tool_host.build_default_context(),
                self._workspace_state,
                active_configs,
                max_steps=self._max_steps,
            )
            emitted: list[ChatMessage] = []
            failures: list[str] = []
            worker.message_emitted.connect(emitted.append)
            worker.turn_failed.connect(failures.append)
            worker.run()
            if failures:
                raise RuntimeError(failures[-1])
            return emitted

        primary = active_configs[0]
        provider_factory = getattr(self._ai_manager, "create_completion_provider_for_config", None)
        provider = provider_factory(primary) if callable(provider_factory) else None
        if provider is None:
            fallback = getattr(self._ai_manager, "create_completion_provider", None)
            provider = fallback() if callable(fallback) else None
        if provider is None:
            raise RuntimeError("No AI provider configured.")

        default_context = self._tool_host.build_default_context()
        packetization = default_context.get("packetization")
        if isinstance(packetization, dict):
            self._workspace_state.packet_context = PacketizationContext(
                mode=str(packetization.get("mode", "equal_frame")),
                bytes_per_packet=packetization.get("bytes_per_packet"),
                header_length=packetization.get("header_length"),
                start_offset=int(packetization.get("start_offset", 0)),
                packet_count=int(packetization.get("packet_count", 0)),
                selected_structure=str(packetization.get("selected_structure", "") or ""),
                active_lens=str(self._workspace_state.packet_context.active_lens or "generic"),
            )
        executor = AgentTurnExecutor(
            provider,
            self._tool_specs_for_turn(),
            default_context,
            self._tool_host.invoke_tool,
            max_steps=self._max_steps,
            system_prompt_parts=_build_system_prompt_parts(
                primary,
                self._workspace_state,
                has_subagents=False,
            ),
        )
        return executor.execute(
            session.to_model_messages(channel="consensus"),
            prompt,
            display_prompt=display_prompt,
        )

    def _forward_message(self, run_id: int, message: ChatMessage) -> None:
        """Forward worker messages for the active run only."""
        if run_id != self._run_id:
            return
        self.message_emitted.emit(message)

    def _on_tool_requested(self, invocation: ToolInvocation, result_queue: queue.Queue[Any]) -> None:
        """Execute tools on the main thread for the worker."""
        try:
            result_queue.put(self._tool_host.invoke_tool(invocation))
        except Exception as exc:
            result_queue.put(exc)

    def _on_turn_succeeded(self, run_id: int) -> None:
        """Handle a successful worker completion."""
        if run_id != self._run_id:
            return
        self.turn_finished.emit("ok")

    def _on_turn_failed(self, run_id: int, error_text: str) -> None:
        """Handle a failed worker completion."""
        if run_id != self._run_id:
            return
        self.message_emitted.emit(ChatMessage(kind="error", role="system", content=error_text))
        self.turn_failed.emit(error_text)

    def _on_worker_finished(self, run_id: int) -> None:
        """Reset runner state after the worker exits."""
        if self._worker is not None and not self._worker.isRunning():
            self._worker.deleteLater()
            self._worker = None
        if run_id == self._run_id:
            self._set_running(False)

    def _set_running(self, running: bool) -> None:
        """Update and emit the current running state."""
        if self._running == running:
            return
        self._running = running
        self.running_changed.emit(running)
