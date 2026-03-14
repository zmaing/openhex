"""
Main-thread bridge that exposes safe editor tools to the AI agent runtime.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict
from statistics import pstdev
from typing import Any, Optional, TYPE_CHECKING

from PyQt6.QtCore import QObject

from ..ai.agent import (
    FieldStatistic,
    PacketDescriptor,
    PacketizationContext,
    ToolInvocation,
    ToolResult,
    ToolSpec,
)
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
                name="get_packetization_context",
                description="Describe how the active file is currently packetized, including mode, start offset, selected structure, and packet count.",
                parameters={
                    "target": {"type": "string"},
                },
            ),
            ToolSpec(
                name="list_packets",
                description="List packet descriptors for the active file or target file.",
                parameters={
                    "target": {"type": "string"},
                    "start_index": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 256},
                },
            ),
            ToolSpec(
                name="read_packet",
                description="Read one packet by packet index, returning header, payload, and preview bytes.",
                parameters={
                    "target": {"type": "string"},
                    "packet_index": {"type": "integer", "minimum": 0},
                },
                required=["packet_index"],
            ),
            ToolSpec(
                name="sample_packets",
                description="Return an evenly spaced packet sample to help infer packet规律.",
                parameters={
                    "target": {"type": "string"},
                    "count": {"type": "integer", "minimum": 1, "maximum": 64},
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
                name="decode_packet",
                description="Decode a packet by packet index using a saved structure config or the selected structure.",
                parameters={
                    "target": {"type": "string"},
                    "packet_index": {"type": "integer", "minimum": 0},
                    "config_name": {"type": "string"},
                },
                required=["packet_index"],
            ),
            ToolSpec(
                name="summarize_field_stats",
                description="Compute deterministic field statistics across packets using a selected structure or synthetic byte-position fields.",
                parameters={
                    "target": {"type": "string"},
                    "config_name": {"type": "string"},
                    "sample_count": {"type": "integer", "minimum": 1, "maximum": 256},
                },
            ),
            ToolSpec(
                name="compare_packets",
                description="Compare two packets and summarize the differing offsets and decoded fields.",
                parameters={
                    "target": {"type": "string"},
                    "packet_a": {"type": "integer", "minimum": 0},
                    "packet_b": {"type": "integer", "minimum": 0},
                    "config_name": {"type": "string"},
                },
                required=["packet_a", "packet_b"],
            ),
            ToolSpec(
                name="find_field_correlations",
                description="Find deterministic correlations between packet fields, lengths, and packet indexes.",
                parameters={
                    "target": {"type": "string"},
                    "config_name": {"type": "string"},
                    "sample_count": {"type": "integer", "minimum": 1, "maximum": 256},
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
        packetization = self._packetization_context(current_hex_view, current_document)

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
                "configs": [str(config["name"]) for config in self._editor._structure_panel.configs()],
            },
            "packetization": asdict(packetization),
        }

    def build_analysis_workspace(self) -> dict[str, Any]:
        """Return a richer packet-analysis snapshot for the AI workspace UI."""
        current_hex_view = self._editor._get_current_hex_view()
        current_document = self._editor._document_model.current_document
        packetization = self._packetization_context(current_hex_view, current_document)
        packets = self._packet_descriptors(current_hex_view, current_document)
        field_stats = self._compute_field_stats(current_hex_view, current_document)
        correlations = self._compute_field_correlations(current_hex_view, current_document)
        return {
            "packetization": asdict(packetization),
            "packets": [asdict(packet) for packet in packets[:32]],
            "field_stats": [asdict(stat) for stat in field_stats[:24]],
            "correlations": correlations[:12],
            "length_distribution": self._packet_length_distribution(packets),
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
            "get_packetization_context": self._tool_get_packetization_context,
            "list_packets": self._tool_list_packets,
            "read_packet": self._tool_read_packet,
            "sample_packets": self._tool_sample_packets,
            "list_structure_configs": self._tool_list_structure_configs,
            "decode_structure": self._tool_decode_structure,
            "detect_patterns": self._tool_detect_patterns,
            "decode_packet": self._tool_decode_packet,
            "summarize_field_stats": self._tool_summarize_field_stats,
            "compare_packets": self._tool_compare_packets,
            "find_field_correlations": self._tool_find_field_correlations,
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

    def _tool_get_packetization_context(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("get_packetization_context", "Packetization context requires the target file to be active.")
        payload = asdict(self._packetization_context(hex_view, document))
        payload["target"] = self._target_for_document(document)
        return self._success_result("get_packetization_context", payload)

    def _tool_list_packets(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("list_packets", "Packet listing requires the target file to be active.")

        descriptors = self._packet_descriptors(hex_view, document)
        start_index = max(0, int(arguments.get("start_index", 0)))
        limit = max(1, min(256, int(arguments.get("limit", 32))))
        sliced = descriptors[start_index : start_index + limit]
        return self._success_result(
            "list_packets",
            {
                "target": self._target_for_document(document),
                "packet_count": len(descriptors),
                "start_index": start_index,
                "returned_count": len(sliced),
                "packets": [asdict(packet) for packet in sliced],
            },
        )

    def _tool_read_packet(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("read_packet", "Packet reading requires the target file to be active.")

        packet_index = max(0, int(arguments.get("packet_index", 0)))
        descriptor = self._packet_descriptor(hex_view, document, packet_index)
        if descriptor is None:
            return self._error_result("read_packet", f"Packet index {packet_index} is out of range.")

        packet_bytes = document.read(descriptor.offset, min(descriptor.total_length, self.MAX_READ_BYTES))
        header_bytes = packet_bytes[: descriptor.header_length]
        payload_bytes = packet_bytes[descriptor.header_length :]
        return self._success_result(
            "read_packet",
            {
                "target": self._target_for_document(document),
                "packet": asdict(descriptor),
                "header_hex": " ".join(f"{byte:02X}" for byte in header_bytes),
                "payload_hex": " ".join(f"{byte:02X}" for byte in payload_bytes),
                "payload_ascii": "".join(chr(byte) if 32 <= byte < 127 else "." for byte in payload_bytes),
            },
        )

    def _tool_sample_packets(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("sample_packets", "Packet sampling requires the target file to be active.")

        descriptors = self._packet_descriptors(hex_view, document)
        count = max(1, min(64, int(arguments.get("count", 8))))
        if not descriptors:
            return self._error_result("sample_packets", "No packets are available in the current arrangement.")
        if len(descriptors) <= count:
            sampled = descriptors
        else:
            step = max(1, len(descriptors) // count)
            sampled = [descriptors[index] for index in range(0, len(descriptors), step)][:count]

        return self._success_result(
            "sample_packets",
            {
                "target": self._target_for_document(document),
                "requested_count": count,
                "returned_count": len(sampled),
                "packets": [asdict(packet) for packet in sampled],
            },
        )

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

    def _tool_decode_packet(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("decode_packet", "Packet decoding requires the target file to be active.")

        packet_index = max(0, int(arguments.get("packet_index", 0)))
        config_name = str(arguments.get("config_name", "")).strip() or self._editor._structure_panel.selected_config_name()
        config = self._editor._structure_panel.get_config(config_name) if config_name else None
        if config is None:
            return self._error_result("decode_packet", "No structure config is selected or the requested config does not exist.")

        descriptor = self._packet_descriptor(hex_view, document, packet_index)
        if descriptor is None:
            return self._error_result("decode_packet", f"Packet index {packet_index} is out of range.")

        packet_bytes = document.read(descriptor.offset, descriptor.total_length)
        decoded_rows = decode_c_struct(config["parsed"], packet_bytes, display_base="hex")
        return self._success_result(
            "decode_packet",
            {
                "target": self._target_for_document(document),
                "config_name": config_name,
                "packet": asdict(descriptor),
                "fields": [
                    {"name": field.display_name, "value": value}
                    for field, value in decoded_rows
                ],
            },
        )

    def _tool_summarize_field_stats(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("summarize_field_stats", "Field statistics require the target file to be active.")

        config_name = str(arguments.get("config_name", "")).strip() or None
        sample_count = max(1, min(256, int(arguments.get("sample_count", 64))))
        stats = self._compute_field_stats(hex_view, document, config_name=config_name, sample_count=sample_count)
        return self._success_result(
            "summarize_field_stats",
            {
                "target": self._target_for_document(document),
                "sample_count": sample_count,
                "field_stats": [asdict(stat) for stat in stats],
            },
        )

    def _tool_compare_packets(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("compare_packets", "Packet comparison requires the target file to be active.")

        packet_a = max(0, int(arguments.get("packet_a", 0)))
        packet_b = max(0, int(arguments.get("packet_b", 0)))
        config_name = str(arguments.get("config_name", "")).strip() or None
        descriptor_a = self._packet_descriptor(hex_view, document, packet_a)
        descriptor_b = self._packet_descriptor(hex_view, document, packet_b)
        if descriptor_a is None or descriptor_b is None:
            return self._error_result("compare_packets", "One or both packet indexes are out of range.")

        data_a = document.read(descriptor_a.offset, descriptor_a.total_length)
        data_b = document.read(descriptor_b.offset, descriptor_b.total_length)
        diff_offsets = [
            {
                "relative_offset": index,
                "packet_a": data_a[index] if index < len(data_a) else None,
                "packet_b": data_b[index] if index < len(data_b) else None,
            }
            for index in range(min(max(len(data_a), len(data_b)), 64))
            if (data_a[index] if index < len(data_a) else None) != (data_b[index] if index < len(data_b) else None)
        ]
        payload = {
            "target": self._target_for_document(document),
            "packet_a": asdict(descriptor_a),
            "packet_b": asdict(descriptor_b),
            "different_byte_count": len(diff_offsets),
            "diff_offsets": diff_offsets[:32],
        }
        if config_name:
            compare_fields = self._decoded_field_pairs(hex_view, document, packet_a, packet_b, config_name)
            if compare_fields is not None:
                payload["field_differences"] = compare_fields
        return self._success_result("compare_packets", payload)

    def _tool_find_field_correlations(self, arguments: dict[str, Any]) -> ToolResult:
        hex_view, document = self._active_hex_view_and_document(arguments.get("target"))
        if hex_view is None or document is None:
            return self._error_result("find_field_correlations", "Field correlation analysis requires the target file to be active.")

        config_name = str(arguments.get("config_name", "")).strip() or None
        sample_count = max(1, min(256, int(arguments.get("sample_count", 64))))
        correlations = self._compute_field_correlations(
            hex_view,
            document,
            config_name=config_name,
            sample_count=sample_count,
        )
        return self._success_result(
            "find_field_correlations",
            {
                "target": self._target_for_document(document),
                "sample_count": sample_count,
                "correlations": correlations,
            },
        )

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

    def _packetization_context(self, hex_view: Any, document: Optional["FileHandle"]) -> PacketizationContext:
        """Build packetization metadata from the active hex-view arrangement."""
        if hex_view is None or document is None:
            return PacketizationContext()

        model = getattr(hex_view, "_model", None)
        if model is None:
            return PacketizationContext()

        mode = str(getattr(model, "_arrangement_mode", "equal_frame"))
        bytes_per_packet = None
        header_length = None
        if mode == "equal_frame":
            bytes_per_packet = int(getattr(model, "_bytes_per_row", 0) or 0)
        elif mode == "header_length":
            header_length = int(getattr(model, "_header_length", 0) or 0)

        return PacketizationContext(
            mode=mode,
            bytes_per_packet=bytes_per_packet or None,
            header_length=header_length or None,
            start_offset=int(getattr(hex_view, "get_start_offset", lambda: 0)() or 0),
            packet_count=int(getattr(model, "get_source_row_count", lambda: 0)() or 0),
            selected_structure=self._editor._structure_panel.selected_config_name(),
        )

    def _packet_descriptors(self, hex_view: Any, document: Optional["FileHandle"]) -> list[PacketDescriptor]:
        """Return packet descriptors for the active file arrangement."""
        if hex_view is None or document is None:
            return []

        model = getattr(hex_view, "_model", None)
        if model is None:
            return []

        row_count = int(getattr(model, "get_source_row_count", lambda: 0)() or 0)
        descriptors: list[PacketDescriptor] = []
        for packet_index in range(max(0, row_count)):
            row_start, row_end, data_start, data_end = model._get_source_row_bounds(packet_index)
            total_length = max(0, row_end - row_start)
            payload_length = max(0, data_end - data_start)
            header_length = max(0, data_start - row_start)
            preview = document.read(row_start, min(total_length, 12))
            descriptors.append(
                PacketDescriptor(
                    index=packet_index,
                    offset=row_start,
                    header_length=header_length,
                    payload_length=payload_length,
                    total_length=total_length,
                    preview_hex=" ".join(f"{byte:02X}" for byte in preview),
                )
            )
        return descriptors

    def _packet_descriptor(
        self,
        hex_view: Any,
        document: Optional["FileHandle"],
        packet_index: int,
    ) -> Optional[PacketDescriptor]:
        """Return one packet descriptor by index."""
        descriptors = self._packet_descriptors(hex_view, document)
        if 0 <= packet_index < len(descriptors):
            return descriptors[packet_index]
        return None

    def _packet_length_distribution(self, descriptors: list[PacketDescriptor]) -> list[dict[str, Any]]:
        """Summarize how often packet lengths repeat."""
        counts = Counter(packet.total_length for packet in descriptors)
        return [
            {"total_length": length, "count": count}
            for length, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def _resolved_structure_config(self, requested_name: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Resolve the requested structure config or fall back to the selected config."""
        config_name = str(requested_name or "").strip() or self._editor._structure_panel.selected_config_name()
        if not config_name:
            return None
        return self._editor._structure_panel.get_config(config_name)

    def _field_rows_for_stats(
        self,
        hex_view: Any,
        document: Optional["FileHandle"],
        *,
        config_name: Optional[str] = None,
        sample_count: int = 64,
    ) -> tuple[list[dict[str, Any]], str]:
        """Build packet-aligned field rows from a structure config or byte positions."""
        descriptors = self._packet_descriptors(hex_view, document)[:sample_count]
        config = self._resolved_structure_config(config_name)
        rows: list[dict[str, Any]] = []

        if config is not None and document is not None:
            for descriptor in descriptors:
                packet_bytes = document.read(descriptor.offset, descriptor.total_length)
                decoded_rows = decode_c_struct(config["parsed"], packet_bytes, display_base="hex")
                row = {"packet_index": descriptor.index, "__descriptor__": descriptor}
                for field, value in decoded_rows:
                    row[field.display_name] = value
                rows.append(row)
            return rows, str(config["name"])

        if document is None:
            return rows, ""

        max_payload_len = max((descriptor.payload_length for descriptor in descriptors), default=0)
        synthetic_width = min(max_payload_len, 16)
        for descriptor in descriptors:
            packet_bytes = document.read(descriptor.offset + descriptor.header_length, descriptor.payload_length)
            row = {"packet_index": descriptor.index, "__descriptor__": descriptor}
            for field_offset in range(synthetic_width):
                row[f"byte_{field_offset:02d}"] = (
                    f"0x{packet_bytes[field_offset]:02X}" if field_offset < len(packet_bytes) else None
                )
            rows.append(row)
        return rows, ""

    def _compute_field_stats(
        self,
        hex_view: Any,
        document: Optional["FileHandle"],
        *,
        config_name: Optional[str] = None,
        sample_count: int = 64,
    ) -> list[FieldStatistic]:
        """Compute deterministic field summaries across packets."""
        rows, _resolved_name = self._field_rows_for_stats(
            hex_view,
            document,
            config_name=config_name,
            sample_count=sample_count,
        )
        if not rows:
            return []

        value_map: dict[str, list[tuple[int, Any]]] = defaultdict(list)
        for row in rows:
            packet_index = int(row.get("packet_index", 0))
            for field_name, value in row.items():
                if field_name in {"packet_index", "__descriptor__"} or value in {None, ""}:
                    continue
                value_map[field_name].append((packet_index, value))

        stats: list[FieldStatistic] = []
        for field_name, samples in value_map.items():
            numeric_values = [value for _packet, value in samples if self._numeric_value(value) is not None]
            parsed_numeric = [self._numeric_value(value) for value in numeric_values]
            parsed_numeric = [value for value in parsed_numeric if value is not None]
            sample_values = [value for _packet, value in samples]
            packet_indexes = [packet for packet, _value in samples[:8]]
            unique_count = len({str(value) for value in sample_values})
            entropy_hint = self._entropy_hint(unique_count, len(sample_values))
            likely_kind, confidence = self._infer_field_kind(field_name, parsed_numeric, packet_indexes, rows, sample_values)
            stats.append(
                FieldStatistic(
                    field_name=field_name,
                    sample_count=len(sample_values),
                    unique_count=unique_count,
                    min=min(parsed_numeric) if parsed_numeric else None,
                    max=max(parsed_numeric) if parsed_numeric else None,
                    entropy_hint=entropy_hint,
                    likely_kind=likely_kind,
                    confidence=confidence,
                    evidence_packet_indexes=packet_indexes,
                )
            )

        stats.sort(key=lambda item: (-item.confidence, item.field_name))
        return stats

    def _compute_field_correlations(
        self,
        hex_view: Any,
        document: Optional["FileHandle"],
        *,
        config_name: Optional[str] = None,
        sample_count: int = 64,
    ) -> list[dict[str, Any]]:
        """Derive lightweight correlations between decoded field values and packet properties."""
        rows, _resolved_name = self._field_rows_for_stats(
            hex_view,
            document,
            config_name=config_name,
            sample_count=sample_count,
        )
        if not rows:
            return []

        correlations: list[dict[str, Any]] = []
        field_names = [name for name in rows[0] if name not in {"packet_index", "__descriptor__"}]
        for field_name in field_names:
            numeric_values: list[float] = []
            packet_indexes: list[int] = []
            payload_lengths: list[int] = []
            for row in rows:
                numeric = self._numeric_value(row.get(field_name))
                descriptor = row.get("__descriptor__")
                if numeric is None or descriptor is None:
                    continue
                numeric_values.append(numeric)
                packet_indexes.append(int(row.get("packet_index", 0)))
                payload_lengths.append(int(descriptor.payload_length))

            if len(numeric_values) < 3:
                continue

            if numeric_values == payload_lengths:
                correlations.append(
                    {
                        "field_name": field_name,
                        "type": "matches_payload_length",
                        "confidence": 0.95,
                    }
                )
            if all(
                numeric_values[index] + 1 == numeric_values[index + 1]
                for index in range(len(numeric_values) - 1)
            ):
                correlations.append(
                    {
                        "field_name": field_name,
                        "type": "monotonic_counter",
                        "confidence": 0.9,
                    }
                )

            if len(set(numeric_values)) > 1 and len(set(payload_lengths)) > 1:
                score = self._normalized_covariance(numeric_values, payload_lengths)
                if score >= 0.8:
                    correlations.append(
                        {
                            "field_name": field_name,
                            "type": "correlates_with_payload_length",
                            "confidence": round(score, 3),
                        }
                    )
            if len(set(numeric_values)) > 1 and len(set(packet_indexes)) > 1:
                score = self._normalized_covariance(numeric_values, packet_indexes)
                if score >= 0.8:
                    correlations.append(
                        {
                            "field_name": field_name,
                            "type": "correlates_with_packet_index",
                            "confidence": round(score, 3),
                        }
                    )
        return correlations

    def _decoded_field_pairs(
        self,
        hex_view: Any,
        document: Optional["FileHandle"],
        packet_a: int,
        packet_b: int,
        config_name: str,
    ) -> Optional[list[dict[str, Any]]]:
        """Return field-level differences for two decoded packets."""
        config = self._resolved_structure_config(config_name)
        if config is None or document is None:
            return None

        descriptor_a = self._packet_descriptor(hex_view, document, packet_a)
        descriptor_b = self._packet_descriptor(hex_view, document, packet_b)
        if descriptor_a is None or descriptor_b is None:
            return None

        decoded_a = decode_c_struct(config["parsed"], document.read(descriptor_a.offset, descriptor_a.total_length), display_base="hex")
        decoded_b = decode_c_struct(config["parsed"], document.read(descriptor_b.offset, descriptor_b.total_length), display_base="hex")
        left = {field.display_name: value for field, value in decoded_a}
        right = {field.display_name: value for field, value in decoded_b}
        diff_fields = []
        for field_name in sorted(set(left) | set(right)):
            if left.get(field_name) != right.get(field_name):
                diff_fields.append(
                    {
                        "field_name": field_name,
                        "packet_a": left.get(field_name),
                        "packet_b": right.get(field_name),
                    }
                )
        return diff_fields

    def _entropy_hint(self, unique_count: int, sample_count: int) -> str:
        """Convert uniqueness ratio into a compact entropy label."""
        if sample_count <= 0:
            return "unknown"
        ratio = unique_count / max(1, sample_count)
        if ratio <= 0.1:
            return "low"
        if ratio <= 0.5:
            return "medium"
        return "high"

    def _infer_field_kind(
        self,
        field_name: str,
        numeric_values: list[float],
        packet_indexes: list[int],
        rows: list[dict[str, Any]],
        sample_values: list[Any],
    ) -> tuple[str, float]:
        """Infer a likely semantic role for one field."""
        lowered_name = field_name.lower()
        if len(set(str(value) for value in sample_values)) == 1:
            return "constant", 0.98
        if "length" in lowered_name or "size" in lowered_name:
            return "length_candidate", 0.85
        if "time" in lowered_name or "timestamp" in lowered_name:
            return "timestamp_candidate", 0.82
        if "crc" in lowered_name or "checksum" in lowered_name:
            return "checksum_candidate", 0.9
        if numeric_values and len(set(numeric_values)) <= max(8, len(numeric_values) // 4):
            return "enum_candidate", 0.72
        if numeric_values and len(numeric_values) >= 3:
            if all(numeric_values[index] + 1 == numeric_values[index + 1] for index in range(len(numeric_values) - 1)):
                return "counter_candidate", 0.92
            if min(numeric_values) >= 946684800 and max(numeric_values) <= 4102444800:
                return "timestamp_candidate", 0.78

            payload_lengths = [int(row["__descriptor__"].payload_length) for row in rows[: len(numeric_values)] if row.get("__descriptor__") is not None]
            if payload_lengths and numeric_values[: len(payload_lengths)] == payload_lengths[: len(numeric_values)]:
                return "length_candidate", 0.9
        return "free_form_bytes", 0.45

    def _normalized_covariance(self, left: list[float], right: list[float]) -> float:
        """Return a lightweight [0, 1] covariance strength estimate."""
        if len(left) != len(right) or len(left) < 3:
            return 0.0
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
        left_std = pstdev(left)
        right_std = pstdev(right)
        if left_std <= 0 or right_std <= 0:
            return 0.0
        correlation = numerator / (len(left) * left_std * right_std)
        return abs(max(-1.0, min(1.0, correlation)))

    def _numeric_value(self, value: Any) -> Optional[float]:
        """Parse a display value into a numeric value when possible."""
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value or "").strip()
        if not text:
            return None
        if text.lower().startswith("0x"):
            try:
                return float(int(text, 16))
            except ValueError:
                return None
        try:
            return float(text)
        except ValueError:
            return None

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
