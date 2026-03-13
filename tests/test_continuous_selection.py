#!/usr/bin/env python3
"""Regression tests for continuous byte-range selection."""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest

from src.app import OpenHexApp
from src.ui.views.hex_view import HexViewWidget


def _drag_with_left_button(view, start: QPoint, end: QPoint) -> None:
    """Send a drag gesture that keeps the left button pressed during motion."""
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(start),
        QPointF(start),
        QPointF(start),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(press_event)

    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(end),
        QPointF(end),
        QPointF(end),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseMoveEvent(move_event)

    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(end),
        QPointF(end),
        QPointF(end),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseReleaseEvent(release_event)


def test_continuous_drag_emits_selection_updates_and_keeps_anchor_focus():
    """Continuous dragging should stay on the custom path instead of Qt's cell selection."""
    OpenHexApp.instance()

    widget = HexViewWidget()
    widget.resize(1400, 420)
    view = widget.hex_view
    view.set_bytes_per_row(32)
    view._model.set_data(bytes(range(256)) * 4)
    widget.show()
    QTest.qWait(50)

    try:
        view.set_selection_mode(view.SELECTION_CONTINUOUS)
        seen_ranges: list[tuple[int, int]] = []
        view.selection_changed.connect(lambda start, end: seen_ranges.append((start, end)))

        start_index = view.model().index(2, 0)
        end_index = view.model().index(5, 1)
        start_rect = view.visualRect(start_index)
        end_rect = view.visualRect(end_index)

        start_pos = QPoint(start_rect.x() + int(start_rect.width() * 0.45), start_rect.center().y())
        end_pos = QPoint(end_rect.x() + int(end_rect.width() * 0.70), end_rect.center().y())

        start_byte = view._calculate_column_byte_pos(start_index, start_pos.x())
        end_byte = view._calculate_column_byte_pos(end_index, end_pos.x())
        _row_start, _row_end, start_data_start, _data_end = view._model._get_row_bounds(start_index.row())
        _row_start, _row_end, end_data_start, _data_end = view._model._get_row_bounds(end_index.row())
        expected_start = start_data_start + start_byte
        expected_end = end_data_start + end_byte

        _drag_with_left_button(view, start_pos, end_pos)

        assert seen_ranges
        assert seen_ranges[0] == (expected_start, expected_start)
        assert seen_ranges[-1] == (expected_start, expected_end)
        assert view._model._selection_ranges == [(expected_start, expected_end)]
        assert not view.selectionModel().selection().indexes()
        assert view.currentIndex() == start_index
    finally:
        widget.close()
