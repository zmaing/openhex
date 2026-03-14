"""
Unit tests for the agent runtime.
"""

from __future__ import annotations

import time

from PyQt6.QtTest import QTest

from src.ai.agent import (
    AgentRoleConfig,
    AgentRunner,
    AgentSession,
    ToolInvocation,
    ToolResult,
    ToolSpec,
)
from src.app import OpenHexApp


class FakeProvider:
    """Simple scripted provider used by agent tests."""

    def __init__(self, responses, delay: float = 0.0):
        self._responses = list(responses)
        self._delay = delay
        self.calls = []
        self.cancelled = False

    @property
    def provider_name(self):
        return "FakeProvider"

    @property
    def settings(self):
        class _Settings:
            model = "fake-model"

        return _Settings()

    def complete(self, messages):
        self.calls.append(messages)
        if self._delay:
            time.sleep(self._delay)
        if not self._responses:
            raise AssertionError("No scripted responses left.")
        return self._responses.pop(0)

    def cancel(self):
        self.cancelled = True


class FakeManager:
    """Fake AI manager exposing the runner-facing interface."""

    def __init__(self, provider):
        self._provider = provider
        self.is_enabled = True

    def create_completion_provider(self):
        return self._provider

    def status_text(self):
        return "FakeProvider · fake-model"


class ConfigAwareFakeManager:
    """Fake AI manager that returns a provider per agent config."""

    def __init__(self, providers_by_agent_id):
        self._providers_by_agent_id = dict(providers_by_agent_id)
        self.requested_agent_ids = []
        self.is_enabled = True

    def create_completion_provider_for_config(self, config):
        self.requested_agent_ids.append(config.agent_id)
        return self._providers_by_agent_id[config.agent_id]

    def status_text(self):
        return "FakeProvider · fake-model"


class FakeToolHost:
    """Tool host used by runtime tests."""

    def __init__(self):
        self.invocations = []
        self._tool_specs = [
            ToolSpec(
                name="read_current_row",
                description="Read current row",
            ),
            ToolSpec(
                name="read_bytes",
                description="Read raw bytes",
                parameters={
                    "target": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "length": {"type": "integer", "minimum": 1, "maximum": 4096},
                },
                required=["offset", "length"],
            ),
            ToolSpec(
                name="detect_patterns",
                description="Detect patterns in a byte range",
                parameters={
                    "target": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "length": {"type": "integer", "minimum": 1, "maximum": 4096},
                },
            ),
            ToolSpec(
                name="select_range",
                description="Select a range in the active file",
                parameters={
                    "target": {"type": "string"},
                    "start": {"type": "integer", "minimum": 0},
                    "end": {"type": "integer", "minimum": 0},
                },
                required=["start", "end"],
            ),
        ]

    def tool_specs(self):
        return self._tool_specs

    def build_default_context(self):
        return {"open_files": [], "active_file": None}

    def invoke_tool(self, invocation: ToolInvocation):
        self.invocations.append(invocation)
        return ToolResult(
            name=invocation.name,
            success=True,
            content='{"ok": true}',
            data={"ok": True, "tool": invocation.name, "arguments": invocation.arguments},
        )


def test_agent_runner_sync_handles_tool_chain_and_final_response():
    """A turn should support tool call -> tool result -> final assistant response."""
    provider = FakeProvider(
        [
            '{"type":"tool_call","tool_name":"read_current_row","arguments":{}}',
            '{"type":"assistant","content":"The current row looks like a small header."}',
        ]
    )
    runner = AgentRunner(FakeManager(provider), FakeToolHost())

    messages = runner.run_turn_sync(AgentSession(), "Inspect the active row")

    assert [message.kind for message in messages] == [
        "user",
        "thinking",
        "tool_call",
        "tool_result",
        "thinking",
        "assistant",
    ]
    assert messages[-1].content == "The current row looks like a small header."


def test_agent_runner_sync_repairs_invalid_json_once():
    """The runner should give the model one chance to repair invalid JSON output."""
    provider = FakeProvider(
        [
            "not json at all",
            '{"type":"assistant","content":"Recovered with valid JSON."}',
        ]
    )
    runner = AgentRunner(FakeManager(provider), FakeToolHost())

    messages = runner.run_turn_sync(AgentSession(), "Recover from invalid output")

    assert messages[-1].kind == "assistant"
    assert messages[-1].content == "Recovered with valid JSON."
    assert len(provider.calls) == 2
    assert "invalid" in provider.calls[1][-1]["content"].lower()


def test_agent_runner_sync_repairs_unknown_tool_once():
    """Unknown tool calls should be rejected once and then repaired."""
    provider = FakeProvider(
        [
            '{"type":"tool_call","tool_name":"missing_tool","arguments":{}}',
            '{"type":"assistant","content":"I can answer without that tool."}',
        ]
    )
    host = FakeToolHost()
    runner = AgentRunner(FakeManager(provider), host)

    messages = runner.run_turn_sync(AgentSession(), "Use a missing tool")

    assert messages[-1].content == "I can answer without that tool."
    assert host.invocations == []
    assert len(provider.calls) == 2


def test_agent_runner_cancel_marks_turn_stopped_immediately():
    """Cancelling an async turn should drop the running flag immediately."""
    app = OpenHexApp.instance()
    provider = FakeProvider(
        ['{"type":"assistant","content":"Delayed answer"}'],
        delay=0.2,
    )
    runner = AgentRunner(FakeManager(provider), FakeToolHost())
    session = AgentSession()
    failures = []

    runner.turn_failed.connect(failures.append)

    assert runner.start_turn(session, "Cancel this turn")
    QTest.qWait(20)

    runner.cancel()
    app.processEvents()

    assert not runner.is_running
    assert failures[-1] == "Agent turn cancelled."


def test_agent_runner_falls_back_to_plaintext_after_two_invalid_json_responses():
    """Local models that never emit JSON should still surface a plain assistant reply."""
    provider = FakeProvider(
        [
            "我先分析一下这个文件。",
            "这是一个看起来像简单头部的数据块，没有触发工具调用。",
        ]
    )
    runner = AgentRunner(FakeManager(provider), FakeToolHost())

    messages = runner.run_turn_sync(AgentSession(), "分析数据")

    assert messages[-1].kind == "assistant"
    assert messages[-1].content == "这是一个看起来像简单头部的数据块，没有触发工具调用。"
    assert len(provider.calls) == 2


def test_agent_runner_parses_minimax_xml_style_tool_call_markup():
    """MiniMax XML-like tool call markup should be converted into a real tool invocation."""
    provider = FakeProvider(
        [
            (
                "<minimax:tool_call>\n"
                "<tool_call>\n"
                '<tool_name="read_bytes"\n'
                'target="/tmp/sample.bin"\n'
                'offset="0"\n'
                'length="512"/>\n'
                "</tool_call>\n"
            ),
            '{"type":"assistant","content":"读取到 512 字节，后续可以继续分析负载结构。"}',
        ]
    )
    host = FakeToolHost()
    runner = AgentRunner(FakeManager(provider), host)

    messages = runner.run_turn_sync(AgentSession(), "分析载荷数据")

    assert [message.kind for message in messages] == [
        "user",
        "thinking",
        "tool_call",
        "tool_result",
        "thinking",
        "assistant",
    ]
    assert host.invocations[0].name == "read_bytes"
    assert host.invocations[0].arguments == {
        "target": "/tmp/sample.bin",
        "offset": 0,
        "length": 512,
    }
    assert messages[-1].content == "读取到 512 字节，后续可以继续分析负载结构。"


def test_agent_runner_parses_minimax_invoke_parameter_tool_call_markup():
    """MiniMax invoke/parameter tool-call markup should trigger the requested tool."""
    provider = FakeProvider(
        [
            (
                "<minimax:tool_call>\n"
                '<invoke name="detect_patterns">\n'
                '<parameter name="target">/tmp/sample.bin</parameter>\n'
                '<parameter name="offset">62</parameter>\n'
                '<parameter name="length">128</parameter>\n'
                "</invoke>\n"
                "</minimax:tool_call>"
            ),
            '{"type":"assistant","content":"在 offset 62 开始的 128 字节里发现了候选载荷模式。"}',
        ]
    )
    host = FakeToolHost()
    runner = AgentRunner(FakeManager(provider), host)

    messages = runner.run_turn_sync(AgentSession(), "分析 data[62] 开始的载荷")

    assert [message.kind for message in messages] == [
        "user",
        "thinking",
        "tool_call",
        "tool_result",
        "thinking",
        "assistant",
    ]
    assert host.invocations[0].name == "detect_patterns"
    assert host.invocations[0].arguments == {
        "target": "/tmp/sample.bin",
        "offset": 62,
        "length": 128,
    }
    assert messages[-1].content == "在 offset 62 开始的 128 字节里发现了候选载荷模式。"


def test_agent_runner_sync_treats_provider_error_strings_as_failures():
    """Provider transport errors should surface as failures, not assistant replies."""
    provider = FakeProvider(["Error: Client error '400 Bad Request'"])
    runner = AgentRunner(FakeManager(provider), FakeToolHost())

    try:
        runner.run_turn_sync(AgentSession(), "分析数据")
    except RuntimeError as exc:
        assert "400 Bad Request" in str(exc)
    else:
        raise AssertionError("Expected provider error to raise RuntimeError.")


def test_agent_runner_keeps_display_prompt_separate_from_model_prompt():
    """The transcript can stay clean while the model receives the enriched prompt."""
    provider = FakeProvider(['{"type":"assistant","content":"done"}'])
    runner = AgentRunner(FakeManager(provider), FakeToolHost())

    messages = runner.run_turn_sync(
        AgentSession(),
        "Attached context:\n- hidden details\n\nUser request:\nAnalyze it",
        display_prompt="Analyze it",
    )

    assert messages[0].content == "Analyze it"
    assert provider.calls[0][-1]["content"].startswith("Attached context:")


def test_agent_runner_rejects_disabled_navigation_tools():
    """Disabled navigation tools should not be callable even if the model requests them."""
    provider = FakeProvider(
        [
            '{"type":"tool_call","tool_name":"select_range","arguments":{"start":62,"end":128}}',
            '{"type":"assistant","content":"I will analyze without changing the UI selection."}',
        ]
    )
    host = FakeToolHost()
    runner = AgentRunner(FakeManager(provider), host)
    runner.set_disabled_tools({"select_range"})

    messages = runner.run_turn_sync(AgentSession(), "分析载荷数据")

    assert messages[-1].content == "I will analyze without changing the UI selection."
    assert all(invocation.name != "select_range" for invocation in host.invocations)
    assert len(provider.calls) == 2


def test_agent_runner_single_primary_agent_runs_direct_analysis():
    """With only one enabled agent, the primary agent should answer directly."""
    provider = FakeProvider(['{"type":"assistant","content":"Primary direct analysis."}'])
    runner = AgentRunner(FakeManager(provider), FakeToolHost())
    runner.set_agent_configs(
        [
            AgentRoleConfig(
                agent_id="primary",
                label="Main Agent",
                role="primary",
                is_primary=True,
            ),
            AgentRoleConfig(
                agent_id="subagent_a",
                label="Subagent A",
                role="subagent",
                enabled=False,
            ),
        ]
    )

    messages = runner.run_turn_sync(AgentSession(), "Analyze the packets")

    assert [message.kind for message in messages] == ["user", "thinking", "assistant"]
    assert messages[-1].content == "Primary direct analysis."
    assert len(provider.calls) == 1


def test_agent_runner_multi_agent_routes_subagent_findings_to_primary():
    """With multiple enabled agents, sub-agents should run first and the primary should synthesize."""
    primary_provider = FakeProvider(['{"type":"assistant","content":"Primary consensus."}'])
    subagent_provider = FakeProvider(['{"type":"assistant","content":"Subagent evidence summary."}'])
    manager = ConfigAwareFakeManager(
        {
            "primary": primary_provider,
            "subagent_a": subagent_provider,
        }
    )
    runner = AgentRunner(manager, FakeToolHost())
    runner.set_agent_configs(
        [
            AgentRoleConfig(
                agent_id="primary",
                label="Main Agent",
                role="primary",
                is_primary=True,
            ),
            AgentRoleConfig(
                agent_id="subagent_a",
                label="Subagent A",
                role="subagent",
                enabled=True,
            ),
        ]
    )

    messages = runner.run_turn_sync(AgentSession(), "Infer unknown fields")

    assert manager.requested_agent_ids == ["subagent_a", "primary"]
    assert any(
        message.kind == "assistant"
        and message.metadata.get("channel") == "subagent_a"
        and message.content == "Subagent evidence summary."
        for message in messages
    )
    assert any(
        message.kind == "assistant"
        and message.metadata.get("channel") == "consensus"
        and message.content == "Primary consensus."
        for message in messages
    )
    primary_call_messages = primary_provider.calls[0]
    assert any(
        "Sub-agent findings" in entry.get("content", "")
        for entry in primary_call_messages
        if entry.get("role") == "system"
    )
