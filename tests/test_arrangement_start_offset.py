"""
Regression coverage for arrangement start-offset handling.
"""

from src.app import OpenHexApp
from src.ui.views.hex_view import HexViewWidget


def test_equal_frame_start_offset_rebases_rows():
    """Equal-frame rows should start and count from the configured offset."""
    app = OpenHexApp.instance()
    widget = HexViewWidget()
    app.processEvents()

    try:
        view = widget.hex_view
        view.set_bytes_per_row(4)
        view._model.set_data(bytes(range(16)))

        view.set_start_offset(5)
        app.processEvents()

        model = view._model
        assert view.get_start_offset() == 5
        assert model.rowCount() == 3
        assert model._get_row_bounds(0) == (5, 9, 5, 9)
        assert model._get_row_bounds(1) == (9, 13, 9, 13)
        assert model.data(model.index(0, 0)).startswith("00000005  05 06 07 08")
    finally:
        widget.close()


def test_header_length_start_offset_reparses_frames_from_offset():
    """Header-length parsing should treat the configured offset as the first frame."""
    app = OpenHexApp.instance()
    widget = HexViewWidget()
    app.processEvents()

    try:
        view = widget.hex_view
        view._model.set_data(bytes([2, 0xAA, 0xBB, 1, 0xCC, 3, 0x11, 0x22, 0x33]))
        view.set_arrangement_mode("header_length", 1)

        view.set_start_offset(3)
        app.processEvents()

        model = view._model
        assert view.get_start_offset() == 3
        assert model.rowCount() == 2
        assert model._get_row_bounds(0) == (3, 5, 4, 5)
        assert model._get_row_bounds(1) == (5, 9, 6, 9)
        assert bytes(model.get_source_row_data(0)) == b"\xCC"
        assert model.data(model.index(0, 0)).startswith("00000003  01 CC")
    finally:
        widget.close()
