"""
Integration tests for the editor-to-agent bridge.
"""

from __future__ import annotations

import os
import tempfile

from PyQt6.QtTest import QTest

from src.ai.agent import ToolInvocation
from src.app import OpenHexApp
from src.main import OpenHexMainWindow


def _write_temp_file(payload: bytes) -> str:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    try:
        handle.write(payload)
        return handle.name
    finally:
        handle.close()


def test_agent_bridge_lists_files_and_supports_navigation():
    """The bridge should expose multi-file metadata and navigation tools."""
    app = OpenHexApp.instance()
    file_one = _write_temp_file(bytes([0x10, 0x11, 0x12, 0x13]))
    file_two = _write_temp_file(bytes([0x20, 0x21, 0x22, 0x23, 0x24]))
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        bridge = editor._agent_bridge

        editor.open_file(file_one)
        editor.open_file(file_two)
        app.processEvents()

        list_result = bridge.invoke_tool(ToolInvocation(name="list_open_files"))
        assert list_result.success
        assert list_result.data["count"] == 2
        assert list_result.data["files"][-1]["is_active"] is True

        activate_result = bridge.invoke_tool(
            ToolInvocation(name="activate_file", arguments={"target": file_one})
        )
        assert activate_result.success
        assert editor._document_model.current_document.file_path == file_one

        navigate_result = bridge.invoke_tool(
            ToolInvocation(name="navigate_to_offset", arguments={"offset": 2})
        )
        assert navigate_result.success
        assert editor._get_current_hex_view().get_offset_at_cursor() == 2

        select_result = bridge.invoke_tool(
            ToolInvocation(name="select_range", arguments={"start": 1, "end": 3})
        )
        assert select_result.success

        selection_result = bridge.invoke_tool(ToolInvocation(name="read_selection"))
        assert selection_result.success
        assert selection_result.data["start"] == 1
        assert selection_result.data["end"] == 3
        assert selection_result.data["selection_length"] == 3
    finally:
        window.close()
        os.unlink(file_one)
        os.unlink(file_two)


def test_agent_bridge_reads_current_row_and_decodes_structure():
    """Current-row reads and structure decoding should reuse the existing parser stack."""
    app = OpenHexApp.instance()
    file_path = _write_temp_file(bytes([0xAB, 0x34, 0x12, 0x48, 0x49]))
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        bridge = editor._agent_bridge
        panel = editor._structure_panel
        panel.add_config(
            "Packet",
            """
            typedef struct {
                uint8_t type;
                uint16_t size;
                char tag[2];
            } Packet;
            """,
        )

        editor.open_file(file_path)
        QTest.qWait(20)

        row_result = bridge.invoke_tool(ToolInvocation(name="read_current_row"))
        assert row_result.success
        assert row_result.data["row_start"] == 0
        assert row_result.data["row_length"] == 5
        assert row_result.data["hex"].startswith("AB 34 12")

        decode_result = bridge.invoke_tool(
            ToolInvocation(
                name="decode_structure",
                arguments={"config_name": "Packet"},
            )
        )
        assert decode_result.success
        assert decode_result.data["fields"][0]["name"] == "type"
        assert decode_result.data["fields"][0]["value"] == "0xAB"
        assert decode_result.data["fields"][1]["value"] == "0x1234"
    finally:
        window.close()
        os.unlink(file_path)


def test_agent_bridge_returns_structured_errors_without_open_file():
    """Bridge tools should return structured errors when no file is available."""
    window = OpenHexMainWindow()

    try:
        bridge = window._hex_editor._agent_bridge
        result = bridge.invoke_tool(ToolInvocation(name="read_current_row"))
        assert not result.success
        assert result.data["error"]
    finally:
        window.close()
