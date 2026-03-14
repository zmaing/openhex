"""
Focused UI tests for shared shell chrome surfaces.
"""

import os
import tempfile
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QWidget, QTabBar, QSizePolicy

from src.app import OpenHexApp
from src.main import OpenHexMainWindow
from src.ui.panels.structure_view import StructureConfigManagerDialog
from src.utils.i18n import tr


def _write_temp_file(payload: bytes, suffix: str = ".dat") -> str:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(payload)
        return handle.name
    finally:
        handle.close()


def test_workspace_status_bar_uses_grouped_footer_chrome():
    """The center status bar should expose grouped capsules, a compact state dot, and no dividers."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor

        assert editor._status_bar.findChild(QFrame, "statusDocumentGroup") is not None
        assert editor._status_bar.findChild(QFrame, "statusMetricGroup") is not None
        assert editor._status_bar.findChild(QFrame, "statusModeGroup") is not None
        assert editor._document_status_group.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Maximum
        assert editor._document_status_group.layout().indexOf(editor._document_status_state_dot) < editor._document_status_group.layout().indexOf(editor._document_status_name)
        assert editor._document_status_name.objectName() == "statusDocumentName"
        assert editor._pos_label.objectName() == "statusFieldValue"
        assert editor._mode_label.objectName() == "statusFieldValueStrong"
        assert editor._document_status_state_dot.objectName() == "statusDocumentStateDot"
        assert editor._document_status_state_dot.toolTip() == tr("workspace_state_draft")
        assert editor._document_metric_divider.isHidden()
        assert editor._metric_offset_selection_divider.isHidden()
        assert editor._metric_mode_divider.isHidden()
        assert editor._document_status_meta.isHidden()
        assert editor._document_status_kind_chip.isHidden()
        assert editor._document_status_state_chip.isHidden()
        assert editor._arrangement_field.isHidden()
        assert editor._encoding_field.isHidden()
        assert editor._msg_label.isHidden()

        editor._status_bar.showMessage("Saved", 1000)
        app.processEvents()

        assert not editor._msg_label.isHidden()
        assert editor._msg_label.text() == "Saved"
        assert editor._msg_label.height() == editor._document_status_group.height()
    finally:
        window.close()


def test_toolbar_length_control_stays_with_leading_action_cluster():
    """The length control should remain grouped with the primary toolbar actions."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        leading_cluster = window.findChild(QWidget, "toolbarLeadingCluster")
        assert leading_cluster is not None
        assert window._toolbar_length_group.parentWidget() is leading_cluster
        assert window._start_offset_spinbox.parentWidget() is window._toolbar_length_group
    finally:
        window.close()


def test_toolbar_start_offset_control_updates_active_hex_view():
    """Changing the toolbar start offset should rebase the active view immediately."""
    app = OpenHexApp.instance()
    file_path = _write_temp_file(bytes(range(12)), suffix=".bin")
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        window._hex_editor.open_file(file_path)
        app.processEvents()

        window._start_offset_spinbox.setValue(4)
        app.processEvents()

        hex_view = window._hex_editor._tab_widget.currentWidget().hex_view
        assert hex_view.get_start_offset() == 4
        assert hex_view._model._get_row_bounds(0)[0] == 4
    finally:
        window.close()
        os.unlink(file_path)


def test_main_window_uses_styled_opaque_background():
    """The native window shell should paint a dark background instead of leaving OS defaults exposed."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        assert window.objectName() == "openhexMainWindow"
        assert window.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        assert window.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        image = window.grab().toImage()
        corner = image.pixelColor(1, 1)
        assert max(corner.red(), corner.green(), corner.blue()) < 48
    finally:
        window.close()


def test_workspace_status_bar_absorbs_document_summary_content():
    """Document name should stay visible while save state collapses into a tooltip-backed status dot."""
    app = OpenHexApp.instance()
    file_path = _write_temp_file(b"\x01\x02\x03\x04", suffix=".dat")
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor
        editor.open_file(file_path)
        app.processEvents()

        assert editor._document_status_name.text() == os.path.basename(file_path)
        assert editor._document_status_name.toolTip() == os.path.basename(file_path)
        assert editor._document_status_meta.isHidden()
        assert editor._document_status_meta.text()
        assert editor._document_status_meta.toolTip() == file_path
        assert editor._document_status_kind_chip.isHidden()
        assert editor._document_status_kind_chip.text() == "DAT"
        assert editor._document_status_state_dot.toolTip() == tr("status_saved")
    finally:
        window.close()
        os.unlink(file_path)


def test_status_document_summary_width_stays_stable_across_filename_lengths():
    """Switching between short and long file names should not resize the lower summary block."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        metric_group = editor._status_bar.findChild(QFrame, "statusMetricGroup")
        assert metric_group is not None

        with tempfile.TemporaryDirectory() as tmpdir:
            short_path = os.path.join(tmpdir, "a.bin")
            long_path = os.path.join(
                tmpdir,
                "very_very_very_long_file_name_for_status_region_regression_check_123456789.bin",
            )
            for path in (short_path, long_path):
                with open(path, "wb") as handle:
                    handle.write(b"\x00\x01\x02\x03")

            for path in (short_path, long_path):
                editor.open_file(path)
                app.processEvents()
                QTest.qWait(20)
            app.processEvents()
            QTest.qWait(20)

        widths = []
        metric_positions = []
        for index in (0, 1, 0, 1):
            editor._tab_widget.setCurrentIndex(index)
            app.processEvents()
            QTest.qWait(20)
            widths.append(editor._document_status_group.width())
            metric_positions.append(metric_group.x())

        assert max(widths) - min(widths) <= 1
        assert max(metric_positions) - min(metric_positions) <= 1
    finally:
        window.close()


def test_save_as_does_not_resize_window_width():
    """Saving a draft with a long filename should not change the main window width."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        editor.new_file()
        QTest.qWait(20)
        width_before = window.width()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(
                tmpdir,
                "very_long_file_name_for_save_width_regression_capture_1234567890abcdef.bin",
            )
            with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(file_path, "All Files (*)")):
                editor.save_file()
                app.processEvents()
                QTest.qWait(50)

            assert abs(window.width() - width_before) <= 1
            assert editor._document_status_name.toolTip() == os.path.basename(file_path)
            assert editor._document_status_meta.toolTip() == file_path
    finally:
        window.close()


def test_side_panel_switcher_stays_hidden_with_single_value_panel():
    """The inspector switcher should disappear once only the Value panel remains in the right column."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        app.processEvents()
        QTest.qWait(20)

        assert editor._right_panel_switcher.isHidden()
        assert editor._right_panel_tab_bar.count() == 0
        assert editor._get_active_panel_ids() == ["data"]
        assert editor._active_panel_id == "data"
    finally:
        window.close()


def test_structure_manager_dialog_uses_shared_dialog_chrome():
    """The structure manager should render with the shared dark shell and consistent action buttons."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()
    dialog = None

    try:
        dialog = StructureConfigManagerDialog(window._hex_editor._structure_panel, window)
        dialog.show()
        QTest.qWait(50)
        app.processEvents()

        assert dialog.objectName() == "structureConfigManagerDialog"
        assert dialog.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        assert dialog._config_list.objectName() == "structureConfigList"
        assert dialog._edit_button.objectName() == "structureSecondaryButton"
        assert dialog._delete_button.objectName() == "structureDangerButton"
        assert dialog._close_button.objectName() == "structurePrimaryButton"
        assert dialog.findChild(QFrame, "dialogHeaderCard") is None
        assert dialog._edit_button.minimumWidth() == dialog._delete_button.minimumWidth() == 96
        assert dialog._close_button.minimumWidth() == 102
        assert dialog._edit_button.height() == dialog._delete_button.height() == dialog._close_button.height()
        assert dialog._edit_button.height() >= 28
        assert dialog._count_badge.text() == "0"

        image = dialog.grab().toImage()
        corner = image.pixelColor(4, 4)
        assert max(corner.red(), corner.green(), corner.blue()) < 48
    finally:
        if dialog is not None:
            dialog.close()
        window.close()


def test_right_panel_focus_stays_on_value_panel_without_info_tab():
    """The right column should keep the Value panel active because no secondary info tab remains."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        app.processEvents()
        QTest.qWait(20)

        assert editor._right_panel_switcher.isHidden()
        assert editor._right_panel_tab_bar.count() == 0
        assert editor._active_panel_id == "data"
        assert editor._right_panel_stack.currentWidget() is editor._side_panel_hosts["data"]
        assert editor._side_panel_hosts["data"].isVisible()
        assert editor._side_panel_hosts["data"].property("activeView") == "true"
    finally:
        window.close()


def test_value_panel_uses_single_stack_page_inside_inspector_column():
    """The inspector column should host only the Value panel while AI stays separate."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()

    try:
        editor = window._hex_editor

        assert editor._resolved_side_panel_signature == (
            "single",
            ("data",),
        )
        assert editor._right_panel_switcher.isHidden()
        assert editor._right_panel_tab_bar.count() == 0
        assert editor._right_panel_stack.currentWidget() is editor._side_panel_hosts["data"]
        assert not editor._side_panel_hosts["data"].isHidden()
        assert editor._right_panel.minimumWidth() >= 228
        assert editor._splitter.widget(2) is editor._ai_panel_shell
        assert editor._splitter.widget(3) is editor._right_panel
        assert editor._ai_panel_shell.minimumWidth() >= 260
    finally:
        window.close()


def test_startup_restores_active_structure_panel_when_saved():
    """Saved inspector settings should restore the structure panel as the active right-side page."""
    app = OpenHexApp.instance()
    settings = app.settings
    keys = [
        "side_panel/value_visible",
        "side_panel/structure_visible",
        "side_panel/active_panel",
    ]
    snapshot = {key: settings.value(key) for key in keys}
    settings.setValue("side_panel/value_visible", True)
    settings.setValue("side_panel/structure_visible", True)
    settings.setValue("side_panel/active_panel", "structure")
    settings.sync()

    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor

        assert editor.is_structure_panel_visible()
        assert editor._get_active_panel_ids() == ["data", "structure"]
        assert editor._active_panel_id == "structure"
        assert editor._right_panel_tab_bar.count() == 2
        assert not editor._right_panel_switcher.isHidden()
        assert editor._right_panel_stack.currentWidget() is editor._side_panel_hosts["structure"]
        assert editor._side_panel_hosts["structure"].isVisible()
    finally:
        window.close()
        for key, value in snapshot.items():
            if value is None:
                settings.remove(key)
            else:
                settings.setValue(key, value)
        settings.sync()


def test_right_panel_footer_stays_hidden_to_reduce_duplicate_chrome():
    """The inspector footer should stay hidden so tabs remain the only panel navigation."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    app.processEvents()

    try:
        editor = window._hex_editor

        assert editor._right_panel_status_bar.isHidden()
        assert editor._right_panel_status_bar.findChild(QFrame, "sidePanelSummaryGroup") is not None
        assert editor._right_panel_status_bar.findChild(QFrame, "sidePanelControlsGroup") is not None
        assert editor._right_panel_switcher.isHidden()

        editor.set_structure_panel_visible(True)
        app.processEvents()

        assert editor._right_panel_status_bar.isHidden()
        assert not editor._right_panel_switcher.isHidden()
        assert editor._right_panel_tab_bar.count() == 2

        editor.toggle_structure_panel()
        app.processEvents()
        assert editor._right_panel_status_bar.isHidden()
        assert editor._right_panel_switcher.isHidden()

        editor.toggle_structure_panel()
        app.processEvents()
        assert editor._right_panel_status_bar.isHidden()
        assert not editor._right_panel_switcher.isHidden()
    finally:
        window.close()


def test_empty_state_multiline_labels_do_not_clip():
    """The welcome copy should reserve enough height for wrapped Chinese text."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        body = editor.findChild(QLabel, "editorEmptyStateBody")
        meta = editor.findChild(QLabel, "editorEmptyStateMeta")

        assert body is not None
        assert meta is not None
        assert body.width() >= 500
        assert meta.width() >= 500
        assert body.height() >= body.heightForWidth(body.width())
        assert meta.height() >= meta.heightForWidth(meta.width())
    finally:
        window.close()


def test_empty_state_open_file_button_opens_selected_file():
    """Clicking the empty-state file CTA should open the chosen document."""
    app = OpenHexApp.instance()
    file_path = _write_temp_file(b"\x00\x01\x02\x03", suffix=".bin")
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        open_file_btn = editor.findChild(QPushButton, "editorEmptyStatePrimary")

        assert open_file_btn is not None
        assert editor._center_stack.currentIndex() == 0

        with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileName", return_value=(file_path, "All Files (*)")):
            QTest.mouseClick(open_file_btn, Qt.MouseButton.LeftButton)
            app.processEvents()
            QTest.qWait(50)

        assert editor._tab_widget.count() == 1
        assert editor._document_model.current_document is not None
        assert editor._document_model.current_document.file_path == file_path
        assert editor._center_stack.currentIndex() == 1
    finally:
        window.close()
        os.unlink(file_path)


def test_empty_state_open_folder_button_reveals_and_updates_file_browser():
    """Clicking the empty-state folder CTA should reveal the file tree and set its root."""
    app = OpenHexApp.instance()
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        open_folder_btn = editor.findChild(QPushButton, "editorEmptyStateSecondary")

        assert open_folder_btn is not None
        if editor._is_side_panel_visible(editor._file_browser, 0):
            editor.toggle_file_tree()
            app.processEvents()

        assert not editor._is_side_panel_visible(editor._file_browser, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("PyQt6.QtWidgets.QFileDialog.getExistingDirectory", return_value=tmpdir):
                QTest.mouseClick(open_folder_btn, Qt.MouseButton.LeftButton)
                app.processEvents()
                QTest.qWait(50)

            assert editor._file_browser._root_path == tmpdir
            assert editor._is_side_panel_visible(editor._file_browser, 0)
    finally:
        window.close()


def test_editor_tabs_show_only_one_working_close_button(tmp_path):
    """Each editor tab should expose a single custom close button."""
    app = OpenHexApp.instance()
    file_path = tmp_path / "single-close-button.bin"
    file_path.write_bytes(b"\x00\x01\x02\x03")
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        editor.open_file(str(file_path))
        app.processEvents()
        QTest.qWait(50)

        assert editor._tab_widget.count() == 1

        tab_bar = editor._tab_widget.tabBar()
        buttons = [
            tab_bar.tabButton(0, side)
            for side in (QTabBar.ButtonPosition.LeftSide, QTabBar.ButtonPosition.RightSide)
            if tab_bar.tabButton(0, side) is not None
        ]

        assert len(buttons) == 1
        assert buttons[0].objectName() == "editorTabCloseButton"

        QTest.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
        app.processEvents()
        QTest.qWait(50)

        assert editor._tab_widget.count() == 0
    finally:
        window.close()


def test_editor_tabs_close_requested_file_in_multi_tab_strip(tmp_path):
    """Clicking a tab close button in a crowded strip should close that specific file."""
    app = OpenHexApp.instance()
    file_names = ["alpha.bin", "beta.bin", "gamma.bin"]
    file_paths = []

    for index, name in enumerate(file_names):
        file_path = tmp_path / name
        file_path.write_bytes(bytes([index, index + 1, index + 2, index + 3]))
        file_paths.append(file_path)

    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor
        for file_path in file_paths:
            editor.open_file(str(file_path))
            app.processEvents()
            QTest.qWait(50)

        assert editor._tab_widget.count() == 3
        assert not editor._tab_widget.tabsClosable()

        tab_bar = editor._tab_widget.tabBar()
        buttons = [
            tab_bar.tabButton(1, side)
            for side in (QTabBar.ButtonPosition.LeftSide, QTabBar.ButtonPosition.RightSide)
            if tab_bar.tabButton(1, side) is not None
        ]

        assert len(buttons) == 1

        QTest.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
        app.processEvents()
        QTest.qWait(50)

        remaining = [editor._tab_widget.tabText(i) for i in range(editor._tab_widget.count())]
        assert editor._tab_widget.count() == 2
        assert file_names[1] not in remaining
        assert remaining == [file_names[0], file_names[2]]
    finally:
        window.close()
