#!/usr/bin/env python3
"""
Tests for save logic around unsaved documents.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models.file_handle import FileHandle
from src.ui.main_window import _requires_save_as


def test_requires_save_as_for_modified_document_without_path():
    """Untitled modified documents should still go through Save As."""
    doc = FileHandle()
    doc.file_name = "Untitled"
    doc.write(0, b"\x01\x02\x03")

    assert doc.file_path is None
    assert _requires_save_as(doc)


def test_requires_save_as_false_after_path_is_assigned():
    """Documents with a real path should use direct save."""
    doc = FileHandle()
    doc.file_path = "/tmp/example.bin"

    assert not _requires_save_as(doc)


def test_new_document_can_save_to_explicit_path_after_editing():
    """Saving an untitled edited document to a chosen path should write the data."""
    doc = FileHandle()
    payload = b"save me"
    doc.write(0, payload)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as handle:
        path = handle.name

    try:
        assert doc.save(path)
        assert doc.file_path == path
        with open(path, "rb") as saved:
            assert saved.read() == payload
    finally:
        if os.path.exists(path):
            os.unlink(path)
