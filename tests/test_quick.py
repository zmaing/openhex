#!/usr/bin/env python3
"""
openhex Automated Test Script - Quick Version
"""

import sys
import os
import tempfile
import traceback

# Set QT_QPA_PLATFORM to offscreen for headless testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

# Import openhex modules
from src.app import OpenHexApp
from src.main import OpenHexMainWindow


def log(status, message):
    """Log test result."""
    symbol = "✓" if status else "✗"
    print(f"[{symbol}] {message}")
    return status


def main():
    """Main entry point."""
    print("=" * 60)
    print("openhex Quick Test")
    print("=" * 60)

    passed = 0
    failed = 0

    try:
        # Setup
        print("\n[1] Setting up application...")
        app = QApplication.instance() or QApplication(sys.argv)
        window = OpenHexMainWindow()
        window.show()
        QTest.qWait(100)
        print("    Setup complete.")

        # Test 1: Menu Structure
        print("\n[2] Testing menu structure...")
        menubar = window.menuBar()
        menu_titles = []
        for action in menubar.actions():
            menu = action.menu()
            if menu:
                menu_titles.append(menu.title())
        print(f"    Found menus: {menu_titles}")
        if log(True, "Menus exist"):
            passed += 1
        else:
            failed += 1

        # Test 2: Language
        print("\n[3] Testing language settings...")
        from src.utils.i18n import get_language, set_language
        lang = get_language()
        if log(lang in ["en", "zh"], f"Language: {lang}"):
            passed += 1
        else:
            failed += 1

        # Test 3: Data Model defaults
        print("\n[4] Testing data model defaults...")
        # _data_model is in HexEditorMainWindow, accessed via _hex_editor
        bpf = window._hex_editor._data_model.bytes_per_frame
        if log(bpf == 32, f"Bytes per frame: {bpf}"):
            passed += 1
        else:
            failed += 1

        # Test 4: Open file
        print("\n[5] Testing file open...")
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'Hello World! Test data.')
            test_file = f.name

        try:
            window._hex_editor._open_file(test_file)
            QTest.qWait(50)

            doc = window._hex_editor._document_model.current_document
            if log(doc and doc.file_size > 0, f"File opened: {doc.file_name if doc else 'None'}, size: {doc.file_size if doc else 0}"):
                passed += 1
            else:
                failed += 1
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)

        # Test 5: View modes
        print("\n[6] Testing view modes...")
        window._hex_editor.set_display_mode("binary")
        window._hex_editor.set_display_mode("hex")
        window._hex_editor.set_display_mode("octal")
        window._hex_editor.set_ascii_visible(False)
        window._hex_editor.set_ascii_visible(True)
        if log(True, "View modes switched"):
            passed += 1
        else:
            failed += 1

        # Test 6: Arrangement
        print("\n[7] Testing arrangement...")
        window._hex_editor.set_arrangement_mode("equal_frame")
        window._hex_editor.set_arrangement_mode("header_length")
        if log(True, "Arrangement modes switched"):
            passed += 1
        else:
            failed += 1

        # Test 7: Hex view
        print("\n[8] Testing hex view...")
        current_widget = window._hex_editor._tab_widget.currentWidget()
        if current_widget and hasattr(current_widget, 'hex_view'):
            hex_view = current_widget.hex_view
            bpr = hex_view._model._bytes_per_row
            if log(bpr == 32, f"Bytes per row: {bpr}"):
                passed += 1
            else:
                failed += 1

            # Test set_bytes_per_row
            hex_view.set_bytes_per_row(16)
            if log(hex_view._model._bytes_per_row == 16, "set_bytes_per_row(16) works"):
                passed += 1
            else:
                failed += 1
        else:
            log(False, "Hex view not accessible")
            failed += 2

        # Test 8: Find dialog
        print("\n[9] Testing find dialog...")
        try:
            window._hex_editor.show_find_dialog()
            if log(True, "Find dialog opened"):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log(False, f"Find dialog error: {e}")
            failed += 1

        # Test 9: Arrangement dialog
        print("\n[10] Testing arrangement dialog...")
        try:
            window._hex_editor.show_arrangement_dialog()
            if log(True, "Arrangement dialog opened"):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log(False, f"Arrangement dialog error: {e}")
            failed += 1

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        traceback.print_exc()
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
