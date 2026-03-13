"""
Regression tests for reusing editor tabs when opening files.
"""

import os

from PyQt6.QtTest import QTest

from src.app import OpenHexApp
from src.main import OpenHexMainWindow


def test_reopening_same_file_reuses_existing_tab(tmp_path):
    """Opening the same file repeatedly should keep a single tab and document."""
    app = OpenHexApp.instance()
    file_path = tmp_path / "sample.bin"
    file_path.write_bytes(b"\x00\x01openhex")
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor

        editor._open_file(str(file_path))
        QTest.qWait(20)
        first_doc = editor._document_model.current_document

        editor._open_file(str(file_path))
        QTest.qWait(20)

        assert first_doc is not None
        assert editor._document_model.document_count == 1
        assert editor._tab_widget.count() == 1
        assert editor._document_model.current_document is first_doc
        assert editor._tab_widget.currentWidget().document is first_doc
    finally:
        window.close()


def test_reopening_with_different_path_forms_still_reuses_tab(tmp_path, monkeypatch):
    """Relative and absolute paths to the same file should resolve to one tab."""
    app = OpenHexApp.instance()
    file_path = tmp_path / "sample.bin"
    file_path.write_bytes(b"\x10\x20\x30\x40")
    window = OpenHexMainWindow()
    window.show()
    QTest.qWait(50)

    try:
        editor = window._hex_editor

        editor._open_file(str(file_path))
        QTest.qWait(20)

        monkeypatch.chdir(tmp_path)
        editor._open_file(file_path.name)
        QTest.qWait(20)

        current_doc = editor._document_model.current_document
        assert current_doc is not None
        assert editor._document_model.document_count == 1
        assert editor._tab_widget.count() == 1
        assert os.path.samefile(current_doc.file_path, file_path)
    finally:
        window.close()
