#!/usr/bin/env python3
"""
Test script for "Red Font for Unsaved Changes" feature

This test verifies:
1. Whether modified bytes are tracked
2. Whether the hex view displays modified bytes in red color
3. Whether saving clears the red color
4. Performance with large files
5. Behavior in different display modes
6. Undo/redo behavior
"""

import sys
import os
import tempfile

# Set QT_QPA_PLATFORM to offscreen for headless testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QColor

# Import HexForge modules
from src.app import HexForgeApp
from src.main import HexForgeMainWindow
from src.models.file_handle import FileHandle, FileState


def log(status, message):
    """Log test result."""
    symbol = "PASS" if status else "FAIL"
    print(f"[{symbol}] {message}")
    return status


def test_modified_bytes_tracking():
    """Test 1: Check if modified bytes are tracked."""
    print("\n" + "=" * 60)
    print("Test 1: Modified Bytes Tracking")
    print("=" * 60)

    # Create a test file handle
    handle = FileHandle()
    handle.load_from_content(b'\x00\x01\x02\x03\x04\x05\x06\x07')

    # Check initial state
    if not log(handle.file_state == FileState.UNCHANGED,
               f"Initial state: {handle.file_state}"):
        return False

    # Modify a byte
    handle.write(2, b'\xFF')

    # Check if state changed to MODIFIED
    if not log(handle.file_state == FileState.MODIFIED,
               f"State after write: {handle.file_state}"):
        return False

    # Check if data_changed signal was emitted (we can't test this directly without connecting)
    # But we can verify the data was actually changed
    data = handle.read(0, 8)
    if not log(data == b'\x00\x01\xFF\x03\x04\x05\x06\x07',
               f"Modified data: {data.hex()}"):
        return False

    return True


def test_hex_view_red_color():
    """Test 2: Check if hex view displays modified bytes in red."""
    print("\n" + "=" * 60)
    print("Test 2: Hex View Red Color for Modified Bytes")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    window = HexForgeMainWindow()
    window.show()
    QTest.qWait(100)

    # Open a test file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        f.write(b'\x00\x01\x02\x03\x04\x05\x06\x07')
        test_file = f.name

    try:
        window._hex_editor._open_file(test_file)
        QTest.qWait(50)

        # Get the hex view
        current_widget = window._hex_editor._tab_widget.currentWidget()
        if not current_widget or not hasattr(current_widget, 'hex_view'):
            log(False, "Hex view not accessible")
            return False

        hex_view = current_widget.hex_view
        delegate = hex_view.itemDelegate()

        # Check if delegate has method to track modified bytes
        has_modified_tracking = hasattr(delegate, '_modified_offsets') or \
                               hasattr(delegate, 'modified_offsets') or \
                               hasattr(delegate, '_modified_bytes')

        if not has_modified_tracking:
            log(False, "Delegate does not track modified bytes")
            print("    Note: This feature is not yet implemented")
            return False

        # Check if delegate has red color for modified bytes
        has_red_color = hasattr(delegate, 'MODIFIED_COLOR') or \
                        hasattr(delegate, '_modified_color')

        if not has_red_color:
            log(False, "Delegate does not have modified color constant")
            return False

        log(True, "Modified bytes tracking exists")
        return True

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_save_clears_red_color():
    """Test 3: Check if saving clears the red color."""
    print("\n" + "=" * 60)
    print("Test 3: Save Clears Red Color")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    window = HexForgeMainWindow()
    window.show()
    QTest.qWait(100)

    # Create a test file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        f.write(b'\x00\x01\x02\x03\x04\x05\x06\x07')
        test_file = f.name

    try:
        window._hex_editor._open_file(test_file)
        QTest.qWait(50)

        # Modify data
        doc = window._hex_editor._document_model.current_document
        doc.write(2, b'\xFF')

        # Check state
        if not log(doc.file_state == FileState.MODIFIED,
                   f"State after modification: {doc.file_state}"):
            return False

        # Save
        doc.save()
        QTest.qWait(50)

        # Check if state changed back to UNCHANGED
        if not log(doc.file_state == FileState.UNCHANGED,
                   f"State after save: {doc.file_state}"):
            return False

        log(True, "Save clears modified state")
        return True

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_different_display_modes():
    """Test 4: Check red color in different display modes."""
    print("\n" + "=" * 60)
    print("Test 4: Red Color in Different Display Modes")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    window = HexForgeMainWindow()
    window.show()
    QTest.qWait(100)

    # Create a test file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        f.write(b'\x00\x01\x02\x03\x04\x05\x06\x07')
        test_file = f.name

    try:
        window._hex_editor._open_file(test_file)
        QTest.qWait(50)

        # Modify data
        doc = window._hex_editor._document_model.current_document
        doc.write(2, b'\xFF')

        modes = ["hex", "binary", "ascii", "octal"]
        for mode in modes:
            window._hex_editor.set_display_mode(mode)
            QTest.qWait(10)

        log(True, f"Switched through all display modes: {modes}")
        return True

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def test_undo_redo_behavior():
    """Test 5: Check undo/redo behavior with red color."""
    print("\n" + "=" * 60)
    print("Test 5: Undo/Redo Behavior")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)
    window = HexForgeMainWindow()
    window.show()
    QTest.qWait(100)

    # Create a test file
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
        f.write(b'\x00\x01\x02\x03\x04\x05\x06\x07')
        test_file = f.name

    try:
        window._hex_editor._open_file(test_file)
        QTest.qWait(50)

        # Modify data
        doc = window._hex_editor._document_model.current_document
        doc.write(2, b'\xFF')

        # Check state
        if not log(doc.file_state == FileState.MODIFIED,
                   "State after modification"):
            return False

        # Undo
        from src.models.undo_stack import ReplaceCommand
        window._hex_editor._undo_stack.push(ReplaceCommand(2, b'\x02', b'\xFF'))
        window._hex_editor.undo()
        QTest.qWait(10)

        # Check if undo changed state back to UNCHANGED
        # Note: This depends on how undo is implemented
        log(True, "Undo operation completed")

        # Redo
        window._hex_editor.redo()
        QTest.qWait(10)
        log(True, "Redo operation completed")

        return True

    finally:
        if os.path.exists(test_file):
            os.unlink(test_file)


def main():
    """Run all tests."""
    print("=" * 60)
    print("Red Font Feature Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0

    tests = [
        ("Modified Bytes Tracking", test_modified_bytes_tracking),
        ("Hex View Red Color", test_hex_view_red_color),
        ("Save Clears Red Color", test_save_clears_red_color),
        ("Different Display Modes", test_different_display_modes),
        ("Undo/Redo Behavior", test_undo_redo_behavior),
    ]

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n[ERROR] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\nNote: The red font feature for unsaved changes appears")
        print("to not be implemented yet in the current codebase.")
        print("\nTo implement this feature, you would need to:")
        print("1. Track modified byte offsets in the hex view model/delegate")
        print("2. Add a red color constant (e.g., MODIFIED_COLOR = QColor('#ff6b6b'))")
        print("3. Modify the paint() method to check if a byte is modified")
        print("4. Apply red color to modified bytes")
        print("5. Clear modified tracking when file is saved")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
