"""
Regression tests for the structure parsing side panel.
"""

import os
import sys
import tempfile

import PyQt6

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault(
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    os.path.join(os.path.dirname(PyQt6.__file__), "Qt6", "plugins", "platforms"),
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtTest import QTest

from src.app import OpenHexApp
from src.main import OpenHexMainWindow
from src.utils.i18n import get_language, set_language


def test_structure_panel_toggle_and_parse_current_row():
    """The structure panel should decode the current row using a saved config."""
    app = OpenHexApp.instance()
    settings = app.settings
    previous_language = get_language()
    keys = [
        "language",
        "side_panel/value_visible",
        "side_panel/ai_visible",
        "side_panel/structure_visible",
        "side_panel/layout_mode",
        "side_panel/active_panel",
        "structure_parser/configs",
        "structure_parser/selected_config",
    ]
    snapshot = {key: settings.value(key) for key in keys}

    for key in keys:
        settings.remove(key)
    settings.sync()
    set_language("en")

    file_path = None
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        structure_action = window._show_structure_panel_action

        assert not structure_action.isChecked()
        assert not editor.is_structure_panel_visible()

        structure_action.trigger()
        app.processEvents()

        assert structure_action.isChecked()
        assert editor.is_structure_panel_visible()
        assert editor._panel_tabs.count() == 3
        tab_titles = [editor._panel_tabs.tabText(i).lower() for i in range(editor._panel_tabs.count())]
        assert "structure" in tab_titles

        panel = editor._structure_panel
        assert panel._config_combo.itemData(0) == "__new__"
        assert panel._config_combo.itemData(1) == "__manage__"

        panel.add_config(
            "Packet",
            """
            typedef struct {
                uint8_t type;
                uint16_t size;
                char tag[2];
            } Packet;
            """,
        )
        panel.set_selected_config("Packet")

        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as handle:
            handle.write(bytes([0xAB, 0x34, 0x12, 0x48, 0x49]))
            file_path = handle.name

        editor.open_file(file_path)
        app.processEvents()

        assert panel._table.rowCount() == 3
        assert panel._table.item(0, 0).text() == "type"
        assert panel._table.item(0, 1).text() == "0xAB"
        assert panel._table.item(1, 1).text() == "0x1234"
        assert panel._table.item(2, 1).text() == "48 49"

        panel._decimal_radio.click()
        app.processEvents()

        assert panel._table.item(0, 1).text() == "171"
        assert panel._table.item(1, 1).text() == "4660"
        assert panel._table.item(2, 1).text() == "HI"
    finally:
        window.close()
        set_language(previous_language)
        for key, value in snapshot.items():
            if value is None:
                settings.remove(key)
            else:
                settings.setValue(key, value)
        settings.sync()
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)


def test_structure_panel_can_update_and_delete_saved_configs():
    """Saved configs should support rename/update and deletion."""
    app = OpenHexApp.instance()
    settings = app.settings
    keys = [
        "structure_parser/configs",
        "structure_parser/selected_config",
    ]
    snapshot = {key: settings.value(key) for key in keys}

    for key in keys:
        settings.remove(key)
    settings.sync()

    window = OpenHexMainWindow()
    app.processEvents()

    try:
        panel = window._hex_editor._structure_panel
        panel.add_config(
            "Packet",
            """
            typedef struct {
                uint8_t type;
            } Packet;
            """,
        )
        panel.add_config(
            "Footer",
            """
            typedef struct {
                uint16_t crc;
            } Footer;
            """,
        )

        updated_name = panel.update_config(
            "Packet",
            "PacketV2",
            """
            typedef struct {
                uint8_t type;
                uint8_t flags;
            } PacketV2;
            """,
        )

        assert updated_name == "PacketV2"
        assert panel.get_config("Packet") is None
        updated_config = panel.get_config("PacketV2")
        assert updated_config is not None
        assert updated_config["parsed"].total_size == 2
        assert panel.selected_config_name() == "PacketV2"

        panel.delete_config("PacketV2")

        assert panel.get_config("PacketV2") is None
        assert panel.selected_config_name() == "Footer"
        assert panel._config_combo.itemData(0) == "__new__"
        assert panel._config_combo.itemData(1) == "__manage__"
    finally:
        window.close()
        for key, value in snapshot.items():
            if value is None:
                settings.remove(key)
            else:
                settings.setValue(key, value)
        settings.sync()


def test_structure_panel_renders_bitfields_and_flexible_arrays():
    """The panel table should show bitfield labels and flexible-array values."""
    app = OpenHexApp.instance()
    settings = app.settings
    keys = [
        "structure_parser/configs",
        "structure_parser/selected_config",
    ]
    snapshot = {key: settings.value(key) for key in keys}

    for key in keys:
        settings.remove(key)
    settings.sync()

    window = OpenHexMainWindow()
    app.processEvents()

    try:
        panel = window._hex_editor._structure_panel
        panel.add_config(
            "BitmapPacket",
            """
            typedef struct {
                uint8_t kind;
                uint8_t enabled:1;
                uint8_t mode:2;
                uint8_t reserved:5;
                uint8_t payload[];
            } BitmapPacket;
            """,
        )
        panel.update_row_data(0, bytes([0x01, 0x8D, 0xAA, 0xBB]))

        assert panel._table.rowCount() == 5
        assert panel._table.item(1, 0).text() == "enabled:1"
        assert panel._table.item(2, 0).text() == "mode:2"
        assert panel._table.item(4, 0).text() == "payload[]"
        assert panel._table.item(1, 1).text() == "0x1"
        assert panel._table.item(2, 1).text() == "0x2"
        assert panel._table.item(4, 1).text() == "[0xAA, 0xBB]"

        panel._decimal_radio.click()
        app.processEvents()

        assert panel._table.item(1, 1).text() == "1"
        assert panel._table.item(2, 1).text() == "2"
        assert panel._table.item(4, 1).text() == "[170, 187]"
    finally:
        window.close()
        for key, value in snapshot.items():
            if value is None:
                settings.remove(key)
            else:
                settings.setValue(key, value)
        settings.sync()


def test_structure_panel_renders_nested_struct_fields():
    """Nested struct fields should appear as dotted paths in the table."""
    app = OpenHexApp.instance()
    settings = app.settings
    keys = [
        "structure_parser/configs",
        "structure_parser/selected_config",
    ]
    snapshot = {key: settings.value(key) for key in keys}

    for key in keys:
        settings.remove(key)
    settings.sync()

    window = OpenHexMainWindow()
    app.processEvents()

    try:
        panel = window._hex_editor._structure_panel
        panel.add_config(
            "NestedPacket",
            """
            typedef struct {
                uint8_t kind;
                struct {
                    uint8_t version;
                    uint8_t flags:3;
                    uint8_t reserved:5;
                } header;
                uint8_t payload[2];
            } NestedPacket;
            """,
        )
        panel.update_row_data(0, bytes([0x01, 0x02, 0x1D, 0xAA, 0xBB]))

        assert panel._table.rowCount() == 5
        assert panel._table.item(1, 0).text() == "header.version"
        assert panel._table.item(2, 0).text() == "header.flags:3"
        assert panel._table.item(3, 0).text() == "header.reserved:5"
        assert panel._table.item(4, 0).text() == "payload[2]"
        assert panel._table.item(1, 1).text() == "0x02"
        assert panel._table.item(2, 1).text() == "0x5"
        assert panel._table.item(3, 1).text() == "0x03"

        panel._decimal_radio.click()
        app.processEvents()

        assert panel._table.item(1, 1).text() == "2"
        assert panel._table.item(2, 1).text() == "5"
        assert panel._table.item(3, 1).text() == "3"
    finally:
        window.close()
        for key, value in snapshot.items():
            if value is None:
                settings.remove(key)
            else:
                settings.setValue(key, value)
        settings.sync()


def test_structure_panel_renders_external_struct_type_references():
    """Separate struct type definitions should render as flattened dotted fields."""
    app = OpenHexApp.instance()
    settings = app.settings
    keys = [
        "structure_parser/configs",
        "structure_parser/selected_config",
    ]
    snapshot = {key: settings.value(key) for key in keys}

    for key in keys:
        settings.remove(key)
    settings.sync()

    window = OpenHexMainWindow()
    app.processEvents()

    try:
        panel = window._hex_editor._structure_panel
        panel.add_config(
            "ExternalPacket",
            """
            typedef struct {
                uint8_t version;
                uint8_t flags:3;
                uint8_t reserved:5;
            } Header;

            struct Footer {
                uint16_t crc;
            };

            typedef struct {
                Header header;
                struct Footer footer;
                uint8_t payload[2];
            } ExternalPacket;
            """,
        )
        panel.update_row_data(0, bytes([0x02, 0x1D, 0x34, 0x12, 0xAA, 0xBB]))

        assert panel._table.rowCount() == 5
        assert panel._table.item(0, 0).text() == "header.version"
        assert panel._table.item(1, 0).text() == "header.flags:3"
        assert panel._table.item(2, 0).text() == "header.reserved:5"
        assert panel._table.item(3, 0).text() == "footer.crc"
        assert panel._table.item(4, 0).text() == "payload[2]"
        assert panel._table.item(0, 1).text() == "0x02"
        assert panel._table.item(1, 1).text() == "0x5"
        assert panel._table.item(2, 1).text() == "0x03"
        assert panel._table.item(3, 1).text() == "0x1234"

        panel._decimal_radio.click()
        app.processEvents()

        assert panel._table.item(0, 1).text() == "2"
        assert panel._table.item(1, 1).text() == "5"
        assert panel._table.item(2, 1).text() == "3"
        assert panel._table.item(3, 1).text() == "4660"
    finally:
        window.close()
        for key, value in snapshot.items():
            if value is None:
                settings.remove(key)
            else:
                settings.setValue(key, value)
        settings.sync()
