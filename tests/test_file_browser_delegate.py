#!/usr/bin/env python3
"""
Tests for file browser delegate text hover calculations.
"""

import os
import sys
import tempfile

from PyQt6.QtCore import QRect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import OpenHexApp
from src.ui.panels.file_browser import FileBrowser, FileTreeDelegate


def test_file_tree_delegate_clamps_text_hover_to_drawn_width():
    """Hover detection should only cover the actual drawn file name."""
    text_rect = QRect(40, 0, 180, 24)
    display_width = 96

    hit_rect = FileTreeDelegate._text_hit_rect(text_rect, display_width)

    assert hit_rect.x() == 40
    assert hit_rect.width() == 96
    assert hit_rect.height() == 24


def test_file_tree_delegate_caps_hover_width_at_text_rect():
    """Hover detection should never extend past the tree item's text rect."""
    text_rect = QRect(40, 0, 180, 24)
    display_width = 999

    hit_rect = FileTreeDelegate._text_hit_rect(text_rect, display_width)

    assert hit_rect.x() == 40
    assert hit_rect.width() == 180


def test_file_browser_uses_single_directory_double_click_handler():
    """Directory double-click should not also trigger Qt's built-in toggle."""
    app = OpenHexApp.instance()
    browser = FileBrowser()

    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = os.path.join(tmpdir, "UHP主站数据")
        os.mkdir(target_dir)
        with open(os.path.join(target_dir, "sample.dat"), "wb") as handle:
            handle.write(b"abc")

        browser.show()
        browser.set_root_path(tmpdir)
        app.processEvents()

        tree = browser._tree_view
        model = browser._model

        assert not tree.expandsOnDoubleClick()
        assert not tree.isSortingEnabled()

        root_item = model.item(0, 0)
        root_index = model.indexFromItem(root_item)
        tree.expand(root_index)
        app.processEvents()

        target_item = root_item.child(0, 0)
        index = model.indexFromItem(target_item)

        browser._on_item_double_clicked(index)
        app.processEvents()

        assert tree.isExpanded(index)
        assert target_item._is_loaded
        assert target_item.rowCount() == 1
        assert target_item.child(0, 0).text() == "sample.dat"

    browser.close()
