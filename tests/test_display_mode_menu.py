#!/usr/bin/env python3
"""
Regression tests for the View -> Display Mode menu.
"""

import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QStyleOptionViewItem

from src.app import HexForgeApp
from src.core.data_model import DisplayMode
from src.main import HexForgeMainWindow
from src.utils.i18n import get_language, set_language


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


def test_file_tree_info_icon_replaces_info_tab():
    """The file browser exposes file metadata via hover icon instead of a separate Info tab."""
    app = HexForgeApp.instance()
    window = HexForgeMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        tab_titles = [editor._panel_tabs.tabText(i) for i in range(editor._panel_tabs.count())]
        assert tab_titles == ["Value", "AI"]

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "sample.bin")
            with open(file_path, "wb") as f:
                f.write(b"hello world")

            editor._file_browser.set_root_path(tmpdir)
            QTest.qWait(10)

            model = editor._file_browser._model
            tree = editor._file_browser._tree_view

            root_item = model.item(0, 0)
            root_index = model.indexFromItem(root_item)
            tree.expand(root_index)
            QTest.qWait(10)

            file_item = root_item.child(0, 0)
            index = model.indexFromItem(file_item)

            option = QStyleOptionViewItem()
            tree.initViewItemOption(option)
            option.rect = tree.visualRect(index)

            delegate = tree.itemDelegateForIndex(index)
            info_rect = delegate.info_icon_rect(option, index)

            assert info_rect.isValid()

            tooltip = tree.tooltip_for_pos(info_rect.center())
            assert "File Information" in tooltip
            assert "sample.bin" in tooltip
            assert file_path in tooltip
    finally:
        window.close()


def test_save_status_message_stays_short():
    """Saving should show a short status message instead of a long filename-based string."""
    app = HexForgeApp.instance()
    previous_language = get_language()
    set_language("zh")

    window = HexForgeMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            prefix="very_long_file_name_for_status_bar_regression_",
            suffix=".bin",
        ) as f:
            f.write(b"status message test")
            file_path = f.name

        window._hex_editor.open_file(file_path)
        QTest.qWait(50)

        window._hex_editor.save_file()
        QTest.qWait(10)

        assert window._hex_editor._msg_label.text() == "已保存"
    finally:
        set_language(previous_language)
        window.close()
        if "file_path" in locals() and os.path.exists(file_path):
            os.unlink(file_path)


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
