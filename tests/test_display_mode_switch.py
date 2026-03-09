#!/usr/bin/env python3
"""Regression tests for display mode switching."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.views.hex_view import HexTableModel, HexView


class DisplayModeSwitchTests(unittest.TestCase):
    """Ensure display mode changes propagate to the rendered row text."""

    def test_hex_view_exposes_display_mode_switch(self):
        """The main window relies on HexView.set_display_mode()."""
        self.assertTrue(hasattr(HexView, "set_display_mode"))
        self.assertTrue(hasattr(HexView, "set_ascii_visible"))

    def test_model_switches_row_text_from_hex_to_binary(self):
        """Binary mode should render row data as 8-bit groups."""
        model = HexTableModel()
        model.set_data(b"AB")

        self.assertEqual(model.data(model.index(0, 0)).rstrip(), "00000000  41 42")

        model.set_display_mode("binary")

        self.assertEqual(
            model.data(model.index(0, 0)).rstrip(),
            "00000000  01000001 01000010",
        )


if __name__ == "__main__":
    unittest.main()
