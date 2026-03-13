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


def test_file_browser_reveals_active_file_in_nested_directories():
    """Setting the active file should expand parent folders and select the target row."""
    app = OpenHexApp.instance()
    browser = FileBrowser()

    with tempfile.TemporaryDirectory() as tmpdir:
        nested_dir = os.path.join(tmpdir, "frames")
        os.mkdir(nested_dir)
        target_file = os.path.join(nested_dir, "sample.dat")
        with open(target_file, "wb") as handle:
            handle.write(b"abc")

        browser.show()
        browser.set_root_path(tmpdir)
        browser.set_active_file(target_file)
        app.processEvents()

        tree = browser._tree_view
        model = browser._model

        root_item = model.item(0, 0)
        root_index = model.indexFromItem(root_item)
        nested_item = root_item.child(0, 0)
        nested_index = model.indexFromItem(nested_item)

        assert browser._delegate.active_file_path == os.path.normcase(
            os.path.normpath(os.path.abspath(target_file))
        )
        assert tree.isExpanded(root_index)
        assert tree.isExpanded(nested_index)
        assert nested_item._is_loaded

        active_item = nested_item.child(0, 0)
        active_index = model.indexFromItem(active_item)
        assert tree.currentIndex() == active_index
        assert tree.selectionModel().isSelected(active_index)

    browser.close()


def test_file_browser_layout_omits_workspace_summary_card():
    """The explorer should render only the header and tree without a workspace card."""
    browser = FileBrowser()

    try:
        layout = browser.layout()

        assert layout.count() == 2
        assert layout.itemAt(0).widget().objectName() == "fileBrowserHeader"
        assert layout.itemAt(1).widget() is browser._tree_view
        assert "fileBrowserWorkspaceCard" not in browser.styleSheet()
    finally:
        browser.close()


def test_file_browser_marks_workspace_root_as_distinct_directory():
    """The workspace root should keep its own icon and semantic flag."""
    app = OpenHexApp.instance()
    browser = FileBrowser()

    with tempfile.TemporaryDirectory() as tmpdir:
        child_dir = os.path.join(tmpdir, "frames")
        os.mkdir(child_dir)

        browser.show()
        browser.set_root_path(tmpdir)
        app.processEvents()

        root_item = browser._model.item(0, 0)
        child_item = root_item.child(0, 0)

        assert root_item.is_root
        assert not child_item.is_root
        assert root_item.icon().cacheKey() != child_item.icon().cacheKey()

    browser.close()


def test_file_browser_tree_keeps_branch_gutter_out_of_selected_fill():
    """Selection chrome should not paint the branch gutter as a separate blue block."""
    browser = FileBrowser()

    try:
        stylesheet = browser.styleSheet()
        assert "show-decoration-selected: 0;" in stylesheet
        assert "QTreeView#fileBrowserTree::branch:selected" in stylesheet
        assert "background: transparent;" in stylesheet
    finally:
        browser.close()
