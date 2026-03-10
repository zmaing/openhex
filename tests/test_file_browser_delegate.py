#!/usr/bin/env python3
"""
Tests for file browser delegate text hover calculations.
"""

import os
import sys

from PyQt6.QtCore import QRect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.panels.file_browser import FileTreeDelegate


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
