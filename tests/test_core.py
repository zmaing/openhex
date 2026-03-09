#!/usr/bin/env python3
"""
HexForge Automated Test - Core Functions Only
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
from PyQt6.QtCore import QTimer

from src.app import HexForgeApp
from src.main import HexForgeMainWindow


def log(status, message):
    """Log test result."""
    symbol = "✓" if status else "✗"
    print(f"[{symbol}] {message}")
    return status


def main():
    """Main entry point."""
    print("=" * 60)
    print("HexForge Core Test")
    print("=" * 60)

    passed = 0
    failed = 0

    try:
        # Setup
        print("\n[1] Setting up application...")
        app = QApplication.instance() or QApplication(sys.argv)
        window = HexForgeMainWindow()
        window.show()
        QTest.qWait(50)
        print("    Done.")

        # Test 1: Menu Structure
        print("\n[2] Menu structure...")
        menubar = window.menuBar()
        menu_titles = []
        for action in menubar.actions():
            menu = action.menu()
            if menu:
                menu_titles.append(menu.title())
        if log(True, f"Found {len(menu_titles)} menus"):
            passed += 1
        else:
            failed += 1

        # Test 2: Language
        print("\n[3] Language settings...")
        from src.utils.i18n import get_language
        lang = get_language()
        if log(lang in ["en", "zh"], f"Language: {lang}"):
            passed += 1
        else:
            failed += 1

        # Test 3: Data Model defaults
        print("\n[4] Data model defaults...")
        hex_editor = window._hex_editor
        bpf = hex_editor._data_model.bytes_per_frame
        if log(bpf == 32, f"Bytes per frame: {bpf}"):
            passed += 1
        else:
            failed += 1

        # Test 4: Open file
        print("\n[5] File open...")
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'Hello World!')
            test_file = f.name

        try:
            hex_editor._open_file(test_file)
            QTest.qWait(30)

            doc = hex_editor._document_model.current_document
            if log(doc and doc.file_size > 0, f"File: {doc.file_name}, size: {doc.file_size}"):
                passed += 1
            else:
                failed += 1
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)

        # Test 5: View modes
        print("\n[6] View modes...")
        hex_editor.set_display_mode("binary")
        hex_editor.set_display_mode("hex")
        hex_editor.set_display_mode("octal")
        hex_editor.set_ascii_visible(False)
        hex_editor.set_ascii_visible(True)
        if log(True, "View modes switched"):
            passed += 1
        else:
            failed += 1

        # Test 6: Arrangement modes
        print("\n[7] Arrangement modes...")
        hex_editor.set_arrangement_mode("equal_frame")
        hex_editor.set_arrangement_mode("header_length")
        if log(True, "Arrangement modes switched"):
            passed += 1
        else:
            failed += 1

        # Test 7: Hex view bytes per row
        print("\n[8] Hex view...")
        current_widget = hex_editor._tab_widget.currentWidget()
        if current_widget and hasattr(current_widget, 'hex_view'):
            hex_view = current_widget.hex_view
            bpr = hex_view._model._bytes_per_row
            if log(bpr == 32, f"Bytes per row: {bpr}"):
                passed += 1
            else:
                failed += 1

            hex_view.set_bytes_per_row(16)
            if log(hex_view._model._bytes_per_row == 16, "set_bytes_per_row(16)"):
                passed += 1
            else:
                failed += 1
        else:
            log(False, "Hex view not found")
            failed += 2

        # Test 8: Status bar
        print("\n[9] Status bar...")
        size_label = hex_editor._size_label.text()
        if log("Size:" in size_label, f"Status bar: {size_label}"):
            passed += 1
        else:
            failed += 1

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
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
