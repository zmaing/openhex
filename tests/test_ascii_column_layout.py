#!/usr/bin/env python3
"""Regression tests for the split hex/ASCII viewport."""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtTest import QTest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFont, QFontMetrics

from src.app import OpenHexApp
from src.ui.views.hex_view import HexViewWidget


def test_split_view_keeps_hex_and_ascii_visible_together():
    """Hex data and ASCII should share the viewport instead of pushing ASCII off-screen."""
    OpenHexApp.instance()

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


def test_offset_ruler_is_visible_and_starts_from_zero():
    """The ruler above the data should be visible and count offsets from 0."""
    OpenHexApp.instance()

    widget = HexViewWidget()
    widget.resize(1200, 320)
    widget.hex_view.set_bytes_per_row(32)
    widget.hex_view._model.set_data(bytes(range(64)))
    widget.show()
    QTest.qWait(50)

    try:
        ticks = widget._ruler._get_visible_major_ticks()
        labels = [label for label, _ in ticks]

        assert widget._ruler.isVisible()
        assert labels
        assert labels[0] == 0
        assert 10 in labels
    finally:
        widget.close()


def test_offset_ruler_has_tick_for_last_visible_byte():
    """The ruler should provide a tick for every visible byte, not only the 10-byte labels."""
    OpenHexApp.instance()

    widget = HexViewWidget()
    widget.resize(1800, 320)
    widget.hex_view.set_bytes_per_row(32)
    widget.hex_view._model.set_data(bytes(range(64)))
    widget.show()
    QTest.qWait(50)

    try:
        visible_count = widget.hex_view._model.get_visible_byte_count()
        byte_ticks = [label for label, _ in widget._ruler._get_visible_byte_ticks()]

        assert visible_count >= 32
        assert 30 in byte_ticks
        assert 31 in byte_ticks
        assert byte_ticks[-1] == visible_count - 1
    finally:
        widget.close()


def test_offset_ruler_ticks_align_to_left_edge_of_data_cells():
    """Byte ticks should align to the left edge of each visible data cell."""
    OpenHexApp.instance()

    widget = HexViewWidget()
    widget.resize(1800, 320)
    widget.hex_view.set_bytes_per_row(32)
    widget.hex_view._model.set_data(bytes(range(64)))
    widget.show()
    QTest.qWait(50)

    try:
        ticks = widget._ruler._get_visible_byte_ticks()
        first_tick_x = ticks[0][1]
        second_tick_x = ticks[1][1]

        model = widget.hex_view._model
        display_text = model.data(model.index(0, 0))
        font = QFont("Menlo", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        fm = QFontMetrics(font)
        prefix_chars = model.get_hex_prefix_char_count()
        chars_per_byte = model.get_chars_per_byte()
        expected_first_tick_x = 5 + fm.horizontalAdvance(display_text[:prefix_chars])
        expected_second_tick_x = 5 + fm.horizontalAdvance(display_text[:prefix_chars + chars_per_byte])

        assert abs(first_tick_x - expected_first_tick_x) < 1
        assert abs(second_tick_x - expected_second_tick_x) < 1
    finally:
        widget.close()


def test_offset_ruler_labels_only_decade_ticks():
    """The ruler should label only every 10th byte."""
    OpenHexApp.instance()

    widget = HexViewWidget()
    widget.resize(900, 320)
    widget.hex_view.set_bytes_per_row(32)
    widget.hex_view._model.set_data(bytes(range(128)))
    widget.show()
    QTest.qWait(50)

    try:
        widget.hex_view.set_ascii_visible(True)
        QTest.qWait(10)
        widget._horizontal_scrollbar.setValue(12)
        QTest.qWait(10)

        labels = [label for label, _ in widget._ruler._get_visible_major_ticks()]

        assert 20 in labels
        assert 30 in labels
        assert 31 not in labels
    finally:
        widget.close()


def test_offset_ruler_scale_caption_is_hover_revealed_only():
    """The left caption should stay out of the way until the ruler is hovered."""
    OpenHexApp.instance()

    widget = HexViewWidget()
    widget.resize(900, 320)
    widget.hex_view.set_bytes_per_row(32)
    widget.hex_view._model.set_data(bytes(range(64)))
    widget.show()
    QTest.qWait(50)

    try:
        widget._ruler._set_hovered(False)
        assert not widget._ruler._should_show_scale_caption()

        widget._ruler._set_hovered(True)
        assert widget._ruler._should_show_scale_caption()

        widget._ruler._set_hovered(False)
        assert not widget._ruler._should_show_scale_caption()
    finally:
        widget.close()


def test_offset_ruler_hides_scale_caption_in_tight_widths():
    """Tight ruler widths should keep the caption collapsed even on hover."""
    OpenHexApp.instance()

    widget = HexViewWidget()
    widget.resize(300, 320)
    widget.hex_view.set_bytes_per_row(32)
    widget.hex_view._model.set_data(bytes(range(64)))
    widget.show()
    QTest.qWait(50)

    try:
        widget._ruler.resize(280, widget._ruler.height())
        widget._ruler._set_hovered(True)

        assert not widget._ruler._should_show_scale_caption()
    finally:
        widget.close()


def test_horizontal_scrollbar_moves_shared_byte_window():
    """Long rows should scroll hex and ASCII together via one shared scrollbar."""
    OpenHexApp.instance()

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


def test_touchpad_horizontal_scroll_moves_shared_byte_window():
    """Horizontal wheel gestures should move the shared byte window even without dragging the scrollbar."""
    OpenHexApp.instance()

    class FakeWheelEvent:
        def __init__(self, x_delta: int):
            self._pixel_delta = QPoint(x_delta, 0)
            self._angle_delta = QPoint(0, 0)
            self._accepted = False

        def type(self):
            return 31  # QEvent.Type.Wheel

        def pixelDelta(self):
            return self._pixel_delta

        def angleDelta(self):
            return self._angle_delta

        def modifiers(self):
            return Qt.KeyboardModifier.NoModifier

        def accept(self):
            self._accepted = True

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

        event = FakeWheelEvent(-120)
        moved = widget.hex_view._handle_horizontal_wheel_event(event)

        assert moved
        assert widget.hex_view._model.get_horizontal_byte_offset() > 0
    finally:
        widget.close()


def test_offset_ruler_updates_with_horizontal_scroll():
    """The ruler should move with the shared horizontal byte window."""
    OpenHexApp.instance()

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

        initial_labels = [label for label, _ in widget._ruler._get_visible_major_ticks()]
        widget._horizontal_scrollbar.setValue(min(12, widget._horizontal_scrollbar.maximum()))
        QTest.qWait(10)
        moved_labels = [label for label, _ in widget._ruler._get_visible_major_ticks()]

        assert initial_labels[0] == 0
        assert moved_labels[0] >= 10
        assert moved_labels != initial_labels
    finally:
        widget.close()
