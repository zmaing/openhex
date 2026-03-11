#!/usr/bin/env python3
"""
Regression tests for row filtering.
"""

import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtTest import QTest

from src.app import OpenHexApp
from src.core.filter_engine import compile_row_filter
from src.main import OpenHexMainWindow
from src.models.file_handle import FileState
from src.ui.dialogs.filter_dialog import FilterDialog


def test_row_filter_expression_supports_bitwise_example():
    """Bitwise filter examples should behave like the documented UI examples."""
    compiled = compile_row_filter("data[0] & 1 == 1")

    assert compiled.matches(bytes([0x01]))
    assert compiled.matches(bytes([0x03]))
    assert not compiled.matches(bytes([0x02]))


def test_hex_view_row_filters_hide_rows_and_reapply_after_edit():
    """Editing the document should re-run active row filters."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            f.write(bytes([0x00, 0x10, 0x02, 0x20, 0x04, 0x30]))
            file_path = f.name

        window._hex_editor.open_file(file_path)
        QTest.qWait(50)

        editor = window._hex_editor
        editor.set_arrangement_length(2)
        QTest.qWait(10)

        hex_view = editor._tab_widget.currentWidget().hex_view
        hex_view.set_row_filters(["data[0] > 1"])
        QTest.qWait(10)

        assert hex_view.get_total_row_count() == 3
        assert hex_view.get_visible_row_count() == 2
        assert hex_view._model.rowCount() == 2
        assert hex_view._model.map_view_row_to_source(0) == 1
        assert hex_view._model.map_view_row_to_source(1) == 2

        doc = editor._document_model.current_document
        doc.write(0, bytes([0x03]))
        QTest.qWait(10)

        assert hex_view.get_visible_row_count() == 3
        assert hex_view._model.map_view_row_to_source(0) == 0
    finally:
        if window._hex_editor._document_model.current_document is not None:
            window._hex_editor._document_model.current_document.file_state = FileState.UNCHANGED
        window.close()
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)


def test_filter_dialog_loads_saved_group_and_updates_history():
    """Selecting a saved group should replace the active filters and preserve new history."""
    app = OpenHexApp.instance()
    dialog = FilterDialog(
        active_filters=["data[0] > 1"],
        condition_history=["data[0] > 1"],
        saved_groups={"odd rows": ["data[0] & 1 == 1"]},
    )

    try:
        index = dialog._saved_group_combo.findData("odd rows")
        dialog._saved_group_combo.setCurrentIndex(index)

        assert dialog.get_active_filters() == ["data[0] & 1 == 1"]

        dialog._filter_input.setPlainText("data[1] == 0x20")
        dialog._on_add_condition_clicked()

        assert dialog.get_active_filters() == ["data[0] & 1 == 1", "data[1] == 0x20"]
        assert "data[1] == 0x20" in dialog.get_condition_history()
    finally:
        dialog.close()
