"""
Main-thread bridge that exposes safe editor tools to the AI agent runtime.
"""

from __future__ import annotations

import json
from typing import Any, Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject

from ..ai.agent import ToolInvocation, ToolResult, ToolSpec
from ..core.parser.auto import AutoParser
from ..core.parser.c_struct import decode_c_struct

if TYPE_CHECKING:
    from .main_window import HexEditorMainWindow
    from ..models.file_handle import FileHandle


class HexEditorAgentBridge(QObject):
    """Expose a fixed tool set to the agent runtime."""

    MAX_READ_BYTES = 4096

    def __init__(self, editor: "HexEditorMainWindow"):
        super().__init__(editor)
        self._editor = editor

    def tool_specs(self) -> list[ToolSpec]:
        """Return the fixed tool registry for the first agent iteration."""
        return [
            ToolSpec(
                name="list_open_files",
                description="List all open files and identify the active file.",
            ),
            ToolSpec(
                name="activate_file",
                description="Switch the active editor tab to the requested file target.",
                parameters={
                    "target": {"type": "string"},
                },
                required=["target"],
            ),
            ToolSpec(
                name="get_file_metadata",
                description="Get metadata and summary state for a file. Defaults to the active file.",
                parameters={
                    "target": {"type": "string"},
                },
            ),
            ToolSpec(
                name="read_bytes",
                description="Read raw bytes from a file at a specific offset. Maximum 4096 bytes returned.",
                parameters={
                    "target": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "length": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": self.MAX_READ_BYTES,
                    },
                },
                required=["offset", "length"],
            ),
            ToolSpec(
                name="read_selection",
                description="Read the current selection from the active file.",
                parameters={
                    "target": {"type": "string"},
                },
            ),
            ToolSpec(
                name="read_current_row",
                description="Read bytes from the current row around the active cursor.",
                parameters={
                    "target": {"type": "string"},
                },
            ),
            ToolSpec(
                name="list_structure_configs",
                description="List saved structure decoding configurations.",
            ),
            ToolSpec(
                name="decode_structure",
                description="Decode the current row or a row containing the given offset using a saved structure config.",
                parameters={
                    "config_name": {"type": "string"},
                    "target": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                },
                required=["config_name"],
            ),
            ToolSpec(
                name="detect_patterns",
                description="Run deterministic pattern detection on a byte range. Maximum 4096 bytes.",
                parameters={
                    "target": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "length": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": self.MAX_READ_BYTES,
                    },
                },
            ),
            ToolSpec(
                name="navigate_to_offset",
                description="Move the active cursor to a byte offset in a file.",
                parameters={
                    "target": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                },
                required=["offset"],
            ),
            ToolSpec(
                name="select_range",
                description="Create a continuous selection in the active file from start to end offsets.",
                parameters={
                    "target": {"type": "string"},
                    "start": {"type": "integer", "minimum": 0},
                    "end": {"type": "integer", "minimum": 0},
                },
                required=["start", "end"],
            ),
        ]

    def build_default_context(self) -> dict[str, Any]:
        """Return the summary context automatically injected into each turn."""
        current_hex_view = self._editor._get_current_hex_view()
        current_document = self._editor._document_model.current_document

        selection_info = None
        row_info = None
        if current_hex_view is not None and current_document is not None:
            _data, sel_start, sel_end = current_hex_view.get_selection_data()
            if sel_start >= 0 and sel_end >= sel_start:
                selection_info = {
                    "start": sel_start,
                    "end": sel_end,
                    "length": sel_end - sel_start + 1,
                }

            cursor_offset = current_hex_view.get_offset_at_cursor()
            row_start, row_end = current_hex_view.get_data_bounds_for_offset(cursor_offset)
            row_info = {
                "cursor_offset": cursor_offset,
                "row_start": row_start,
                "row_end_exclusive": row_end,
                "row_length": max(0, row_end - row_start),
            }

        return {
            "open_files": self._list_open_files_payload(),
            "active_file": self._build_file_summary(current_document),
            "selection": selection_info,
            "current_row": row_info,
            "structure_configs": {
                "selected": self._editor._structure_panel.selected_config_name(),
                "count": len(self._editor._structure_panel.configs()),
            },
        }

    def invoke_tool(self, invocation: ToolInvocation) -> ToolResult:
        """Dispatch one tool invocation."""
        name = invocation.name
        arguments = invocation.arguments

        handlers = {
            "list_open_files": self._tool_list_open_files,
            "activate_file": self._tool_activate_file,
            "get_file_metadata": self._tool_get_file_metadata,
            "read_bytes": self._tool_read_bytes,
            "read_selection": self._tool_read_selection,
            "read_current_row": self._tool_read_current_row,
            "list_structure_configs": self._tool_list_structure_configs,
            "decode_structure": self._tool_decode_structure,
            "detect_patterns": self._tool_detect_patterns,
            "navigate_to_offset": self._tool_navigate_to_offset,
            "select_range": self._tool_select_range,
        }

        handler = handlers.get(name)
        if handler is None:
            return self._error_result(name, f"Unknown tool: {name}")

        try:
            return handler(arguments)
        except Exception as exc:
            return self._error_result(name, str(exc))

    def _tool_list_open_files(self, arguments: dict[str, Any]) -> ToolResult:
        payload = self._list_open_files_payload()
        return self._success_result(
            "list_open_files",
            {
                "count": len(payload),
                "files": payload,
            },
        )

    def _tool_activate_file(self, arguments: dict[str, Any]) -> ToolResult:
        lookup = self._find_document(arguments.get("target"))
        if lookup is None:
            return self._error_result("activate_file", "Target file not found.")

        index, document = lookup
        self._editor._tab_widget.setCurrentIndex(index)
        summary = self._build_file_summary(document)
        return self._success_result("activate_file", {"active_file": summary})

    def _tool_get_file_metadata(self, arguments: dict[str, Any]) -> ToolResult:
        lookup = self._find_document(arguments.get("target"))
        if lookup is None:
            return self._error_result("get_file_metadata", "No matching file found.")

        _index, document = lookup
        return self._success_result("get_file_metadata", self._build_file_summary(document))

    def _tool_read_bytes(self, arguments: dict[str, Any]) -> ToolResult:
        lookup = self._find_document(arguments.get("target"))
        if lookup is None:
            return self._error_result("read_bytes", "No matching file found.")

        _index, document = lookup
        offset = max(0, int(arguments.get("offset", 0)))
        requested_length = max(1, int(arguments.get("length", 1)))
        limited_length = min(requested_length, self.MAX_READ_BYTES)

        if offset >= document.file_size:
            return self._error_result("read_bytes", "Offset is beyond the end of file.")

        data = document.read(offset, limited_length)
        payload = self._build_bytes_payload(offset, requested_length, data, document.file_size)
        payload["target"] = self._target_for_document(document)
        return self._success_result("read_bytes", payload)

    def _tool_read_selection(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("read_selection", "Selection is only available for the active file.")

        data, start, end = hex_view.get_selection_data()
        if data is None or start < 0 or end < start:
            return self._error_result("read_selection", "There is no active selection.")

        payload = self._build_bytes_payload(start, len(data), data[: self.MAX_READ_BYTES], document.file_size)
        payload.update(
            {
                "start": start,
                "end": end,
                "selection_length": end - start + 1,
                "target": self._target_for_document(document),
            }
        )
        return self._success_result("read_selection", payload)

    def _tool_read_current_row(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("read_current_row", "Current row is only available for the active file.")

        cursor_offset = hex_view.get_offset_at_cursor()
        row_start, row_end = hex_view.get_data_bounds_for_offset(cursor_offset)
        if row_end <= row_start:
            return self._error_result("read_current_row", "No readable row is available.")

        data = document.read(row_start, min(row_end - row_start, self.MAX_READ_BYTES))
        payload = self._build_bytes_payload(row_start, row_end - row_start, data, document.file_size)
        payload.update(
            {
                "cursor_offset": cursor_offset,
                "row_start": row_start,
                "row_end_exclusive": row_end,
                "row_length": row_end - row_start,
                "target": self._target_for_document(document),
            }
        )
        return self._success_result("read_current_row", payload)

    def _tool_list_structure_configs(self, arguments: dict[str, Any]) -> ToolResult:
        configs = self._editor._structure_panel.configs()
        payload = {
            "selected": self._editor._structure_panel.selected_config_name(),
            "configs": [
                {
                    "name": str(config["name"]),
                    "size": int(config["parsed"].total_size),
                }
                for config in configs
            ],
        }
        return self._success_result("list_structure_configs", payload)

    def _tool_decode_structure(self, arguments: dict[str, Any]) -> ToolResult:
        config_name = str(arguments.get("config_name", "")).strip()
        config = self._editor._structure_panel.get_config(config_name)
        if config is None:
            return self._error_result("decode_structure", f"Unknown structure config: {config_name}")

        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("decode_structure", "Structure decoding requires the target file to be active.")

        offset_value = arguments.get("offset")
        if offset_value is None:
            target_offset = hex_view.get_offset_at_cursor()
        else:
            target_offset = max(0, int(offset_value))

        row_start, row_end = hex_view.get_data_bounds_for_offset(target_offset)
        if row_end <= row_start:
            return self._error_result("decode_structure", "No row data available for decoding.")

        row_data = document.read(row_start, row_end - row_start)
        decoded_rows = decode_c_struct(config["parsed"], row_data, display_base="hex")
        payload = {
            "config_name": config_name,
            "row_start": row_start,
            "row_end_exclusive": row_end,
            "fields": [
                {
                    "name": field.display_name,
                    "value": value,
                }
                for field, value in decoded_rows
            ],
        }
        return self._success_result("decode_structure", payload)

    def _tool_detect_patterns(self, arguments: dict[str, Any]) -> ToolResult:
        lookup = self._find_document(arguments.get("target"))
        if lookup is None:
            return self._error_result("detect_patterns", "No matching file found.")

        _index, document = lookup
        offset = max(0, int(arguments.get("offset", 0)))
        requested_length = int(arguments.get("length", min(document.file_size, self.MAX_READ_BYTES)))
        length = min(max(1, requested_length), self.MAX_READ_BYTES)
        if offset >= document.file_size:
            return self._error_result("detect_patterns", "Offset is beyond the end of file.")

        data = document.read(offset, length)
        parser = AutoParser()
        patterns = parser.analyze(data)
        payload = {
            "offset": offset,
            "requested_length": requested_length,
            "returned_length": len(data),
            "pattern_count": len(patterns),
            "patterns": [
                {
                    "type": pattern.pattern_type.name,
                    "offset": offset + pattern.offset,
                    "length": pattern.length,
                    "confidence": round(pattern.confidence, 3),
                    "description": pattern.description,
                }
                for pattern in patterns[:20]
            ],
        }
        return self._success_result("detect_patterns", payload)

    def _tool_navigate_to_offset(self, arguments: dict[str, Any]) -> ToolResult:
        lookup = self._find_document(arguments.get("target"))
        if lookup is None:
            return self._error_result("navigate_to_offset", "No matching file found.")

        index, document = lookup
        self._editor._tab_widget.setCurrentIndex(index)
        current_widget = self._editor._tab_widget.currentWidget()
        if not hasattr(current_widget, "hex_view"):
            return self._error_result("navigate_to_offset", "No active hex view available.")

        offset = max(0, int(arguments.get("offset", 0)))
        current_widget.hex_view.scrollToOffset(offset)
        summary = self._build_file_summary(document)
        return self._success_result("navigate_to_offset", {"active_file": summary})

    def _tool_select_range(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"), activate=True)
        if hex_view is None or document is None:
            return self._error_result("select_range", "No active file available for selection.")

        start = max(0, int(arguments.get("start", 0)))
        end = max(0, int(arguments.get("end", 0)))
        if end < start:
            start, end = end, start

        hex_view.select_offset_range(start, end)
        payload = {
            "target": self._target_for_document(document),
            "start": start,
            "end": end,
            "length": end - start + 1,
        }
        return self._success_result("select_range", payload)

    def _active_hex_view_and_document(
        self,
        target: Optional[str],
        *,
        activate: bool = False,
    ) -> tuple[Any, Optional["FileHandle"]]:
        if target:
            lookup = self._find_document(target)
            if lookup is None:
                return None, None
            index, document = lookup
            if activate and self._editor._tab_widget.currentIndex() != index:
                self._editor._tab_widget.setCurrentIndex(index)
            if self._editor._document_model.current_document != document:
                return None, None
        else:
            document = self._editor._document_model.current_document

        current_widget = self._editor._tab_widget.currentWidget()
        if current_widget is None or not hasattr(current_widget, "hex_view"):
            return None, document
        return current_widget.hex_view, document

    def _list_open_files_payload(self) -> list[dict[str, Any]]:
        payload = []
        active_document = self._editor._document_model.current_document
        for index, document in enumerate(self._editor._document_model.documents):
            payload.append(
                {
                    "target": self._target_for_document(document),
                    "index": index,
                    "file_name": document.file_name,
                    "file_path": document.file_path,
                    "file_size": document.file_size,
                    "is_active": document == active_document,
                }
            )
        return payload

    def _build_file_summary(self, document: Optional["FileHandle"]) -> Optional[dict[str, Any]]:
        if document is None:
            return None

        summary = {
            "target": self._target_for_document(document),
            "file_name": document.file_name,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "is_active": document == self._editor._document_model.current_document,
        }

        if summary["is_active"]:
            hex_view = self._editor._get_current_hex_view()
            if hex_view is not None:
                summary["cursor_offset"] = hex_view.get_offset_at_cursor()
                _data, sel_start, sel_end = hex_view.get_selection_data()
                if sel_start >= 0 and sel_end >= sel_start:
                    summary["selection"] = {
                        "start": sel_start,
                        "end": sel_end,
                        "length": sel_end - sel_start + 1,
                    }

        return summary

    def _find_document(self, target: Any) -> Optional[tuple[int, "FileHandle"]]:
        documents = self._editor._document_model.documents
        current_document = self._editor._document_model.current_document
        if not documents:
            return None

        if target is None or str(target).strip() == "":
            if current_document is None:
                return None
            for index, document in enumerate(documents):
                if document == current_document:
                    return index, document
            return None

        target_text = str(target).strip()
        for index, document in enumerate(documents):
            if document.file_path == target_text:
                return index, document
            if document.file_name == target_text:
                return index, document
            if self._target_for_document(document) == target_text:
                return index, document

        return None

    def _target_for_document(self, document: "FileHandle") -> str:
        return document.file_path or document.file_name

    def _build_bytes_payload(
        self,
        offset: int,
        requested_length: int,
        data: bytes,
        file_size: int,
    ) -> dict[str, Any]:
        returned_length = len(data)
        truncated = requested_length > self.MAX_READ_BYTES or returned_length < requested_length
        return {
            "offset": offset,
            "requested_length": requested_length,
            "returned_length": returned_length,
            "file_size": file_size,
            "truncated": truncated,
            "hex": " ".join(f"{byte:02X}" for byte in data),
            "ascii": "".join(chr(byte) if 32 <= byte < 127 else "." for byte in data),
        }

    def _success_result(self, name: str, data: dict[str, Any]) -> ToolResult:
        return ToolResult(
            name=name,
            success=True,
            content=json.dumps(data, ensure_ascii=False, indent=2),
            data=data,
        )

    def _error_result(self, name: str, message: str) -> ToolResult:
        data = {"error": message}
        return ToolResult(
            name=name,
            success=False,
            content=json.dumps(data, ensure_ascii=False, indent=2),
            data=data,
        )
