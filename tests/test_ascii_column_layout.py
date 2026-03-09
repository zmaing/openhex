#!/usr/bin/env python3
"""Regression tests for the split hex/ASCII viewport."""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtTest import QTest

from src.app import HexForgeApp
from src.ui.views.hex_view import HexViewWidget


def test_split_view_keeps_hex_and_ascii_visible_together():
    """Hex data and ASCII should share the viewport instead of pushing ASCII off-screen."""
    HexForgeApp.instance()

    widget = HexViewWidget()
    widget.resize(1200, 320)
    widget.hex_view.set_bytes_per_row(16)
    widget.hex_view._model.set_data(bytes(range(32, 48)))
    widget.show()
    QTest.qWait(50)

    try:
        widget.hex_view.set_ascii_visible(True)
        QTest.qWait(10)

        viewport_width = widget.hex_view.viewport().width()
        total_width = widget.hex_view.columnWidth(0) + widget.hex_view.columnWidth(1)

        assert not widget.hex_view.isColumnHidden(1)
        assert total_width <= viewport_width + 2
        assert widget.hex_view.columnWidth(0) > widget.hex_view.columnWidth(1) > 0
        assert not widget._horizontal_scrollbar.isVisible()
    finally:
        widget.close()


def test_horizontal_scrollbar_moves_shared_byte_window():
    """Long rows should scroll hex and ASCII together via one shared scrollbar."""
    HexForgeApp.instance()

    widget = HexViewWidget()
    widget.resize(640, 320)
    widget.hex_view.set_bytes_per_row(256)
    payload = bytes(65 + (i % 26) for i in range(512))
    widget.hex_view._model.set_data(payload)
    widget.show()
    QTest.qWait(50)

    try:
        widget.hex_view.set_ascii_visible(True)
        QTest.qWait(10)

        scrollbar = widget._horizontal_scrollbar
        initial_hex = widget.hex_view._model.data(widget.hex_view._model.index(0, 0))
        initial_ascii = widget.hex_view._model.data(widget.hex_view._model.index(0, 1))

        assert scrollbar.isVisible()
        assert scrollbar.maximum() > 0

        scrollbar.setValue(min(8, scrollbar.maximum()))
        QTest.qWait(10)

        moved_hex = widget.hex_view._model.data(widget.hex_view._model.index(0, 0))
        moved_ascii = widget.hex_view._model.data(widget.hex_view._model.index(0, 1))

        assert widget.hex_view._model.get_horizontal_byte_offset() == scrollbar.value()
        assert moved_hex != initial_hex
        assert moved_ascii != initial_ascii
    finally:
        widget.close()
