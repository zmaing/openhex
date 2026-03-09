#!/usr/bin/env python3
"""
Regression tests for the View -> Display Mode menu.
"""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtTest import QTest

from src.app import HexForgeApp
from src.core.data_model import DisplayMode
from src.main import HexForgeMainWindow


def test_display_mode_menu_is_exclusive():
    """Primary display modes are exclusive while ASCII stays independently toggleable."""
    app = HexForgeApp.instance()
    window = HexForgeMainWindow()
    window.show()
    window._hex_editor.new_file()
    QTest.qWait(50)

    try:
        hex_action = window._display_mode_actions["hex"]
        binary_action = window._display_mode_actions["binary"]
        octal_action = window._display_mode_actions["octal"]
        ascii_action = window._ascii_visibility_action

        assert hex_action.isChecked()
        assert ascii_action.isChecked()
        assert not window._hex_editor._tab_widget.currentWidget().hex_view.isColumnHidden(1)

        binary_action.trigger()
        QTest.qWait(10)

        assert not hex_action.isChecked()
        assert binary_action.isChecked()
        assert window._hex_editor._data_model.display_mode == DisplayMode.BINARY

        ascii_action.trigger()
        QTest.qWait(10)

        assert not ascii_action.isChecked()
        assert not octal_action.isChecked()
        assert binary_action.isChecked()
        assert window._hex_editor._data_model.display_mode == DisplayMode.BINARY
        assert window._hex_editor._tab_widget.currentWidget().hex_view.isColumnHidden(1)

        ascii_action.trigger()
        QTest.qWait(10)

        assert ascii_action.isChecked()
        assert not window._hex_editor._tab_widget.currentWidget().hex_view.isColumnHidden(1)

        octal_action.trigger()
        QTest.qWait(10)

        checked_modes = [
            mode for mode, action in window._display_mode_actions.items() if action.isChecked()
        ]
        assert checked_modes == ["octal"]
        assert window._hex_editor._data_model.display_mode == DisplayMode.OCTAL
    finally:
        window.close()


def test_view_panel_menu_toggles_affect_splitter_panels():
    """View menu toggles should actually hide and show the file tree and AI panel."""
    app = HexForgeApp.instance()
    window = HexForgeMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        file_tree_action = window._show_file_tree_action
        ai_panel_action = window._show_ai_panel_action

        assert file_tree_action.isChecked()
        assert ai_panel_action.isChecked()
        assert editor._file_browser.isVisible()
        assert editor._right_panel.isVisible()
        assert editor._splitter.sizes()[0] > 0
        assert editor._splitter.sizes()[2] > 0

        file_tree_action.trigger()
        QTest.qWait(10)

        assert not editor._file_browser.isVisible()
        assert editor._splitter.sizes()[0] == 0

        file_tree_action.trigger()
        QTest.qWait(10)

        assert editor._file_browser.isVisible()
        assert editor._splitter.sizes()[0] > 0

        ai_panel_action.trigger()
        QTest.qWait(10)

        assert not editor._right_panel.isVisible()
        assert editor._splitter.sizes()[2] == 0

        ai_panel_action.trigger()
        QTest.qWait(10)

        assert editor._right_panel.isVisible()
        assert editor._splitter.sizes()[2] > 0
    finally:
        window.close()
