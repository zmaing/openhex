#!/usr/bin/env python3
"""
Tests for VALUE panel decoding logic.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import OpenHexApp
from src.ui.panels.data_value import (
    DataValuePanel,
    decode_data_values,
    decode_display_values,
    format_char,
    format_unix_time,
)


def _rows_by_type(data: bytes) -> dict[str, tuple[str, int, str, str]]:
    """Convert decoded rows into a dict keyed by type name."""
    return {
        type_name: (type_name, size, little_value, big_value)
        for type_name, size, little_value, big_value in decode_data_values(data)
    }


def test_decode_data_values_displays_integer_values_for_both_endians():
    """Integer rows should reflect the same bytes in little and big endian."""
    data = bytes.fromhex("41 02 03 04 05 06 07 08")
    rows = _rows_by_type(data)

    assert rows["char"][2] == "'A'"
    assert rows["char"][3] == "'A'"
    assert rows["uint16"][2] == str(int.from_bytes(data[:2], "little"))
    assert rows["uint16"][3] == str(int.from_bytes(data[:2], "big"))
    assert rows["int32"][2] == str(int.from_bytes(data[:4], "little", signed=True))
    assert rows["int32"][3] == str(int.from_bytes(data[:4], "big", signed=True))
    assert rows["uint64"][2] == str(int.from_bytes(data, "little"))
    assert rows["uint64"][3] == str(int.from_bytes(data, "big"))


def test_decode_display_values_selects_only_one_active_endian():
    """Display rows should expose only the currently selected byte order."""
    data = bytes.fromhex("23 21 2F 75")
    little_rows = {
        type_name: (type_name, size, value)
        for type_name, size, value in decode_display_values(data, "little")
    }
    big_rows = {
        type_name: (type_name, size, value)
        for type_name, size, value in decode_display_values(data, "big")
    }

    assert little_rows["uint16"][2] == str(int.from_bytes(data[:2], "little"))
    assert big_rows["uint16"][2] == str(int.from_bytes(data[:2], "big"))
    assert little_rows["uint32"][2] == str(int.from_bytes(data, "little"))
    assert big_rows["uint32"][2] == str(int.from_bytes(data, "big"))
    assert little_rows["time"][2] == format_unix_time(int.from_bytes(data, "little"))
    assert big_rows["time"][2] == format_unix_time(int.from_bytes(data, "big"))


def test_decode_data_values_handles_float_values_and_short_reads():
    """Float rows should decode, while oversized types should stay unavailable."""
    data = struct.pack(">f", 1.0)
    rows = _rows_by_type(data)

    assert rows["float"][3] == "1.0"
    assert rows["uint64"][2] == "N/A"
    assert rows["double"][3] == "N/A"


def test_format_char_escapes_non_printable_and_quote_characters():
    """Character formatting should remain readable in the table."""
    assert format_char(0x00) == "\\x00"
    assert format_char(ord("'")) == "'\\''"
    assert format_char(ord("\\")) == "'\\\\'"


def test_data_value_panel_uses_mutually_exclusive_endian_radios():
    """The panel should expose explicit little/big endian radio choices."""
    app = OpenHexApp.instance()
    panel = DataValuePanel()

    try:
        panel.update_values(0, bytes.fromhex("23 21 2F 75"))
        app.processEvents()

        assert panel._little_endian_radio.isChecked()
        assert not panel._big_endian_radio.isChecked()
        assert panel._value_table.horizontalHeaderItem(2).text() == "Value (LE)"

        panel._big_endian_radio.click()
        app.processEvents()

        assert not panel._little_endian_radio.isChecked()
        assert panel._big_endian_radio.isChecked()
        assert panel._value_table.horizontalHeaderItem(2).text() == "Value (BE)"
        assert panel._value_table.item(panel.get_row("uint16"), 2).text() == str(
            int.from_bytes(bytes.fromhex("23 21"), "big")
        )
    finally:
        panel.deleteLater()
