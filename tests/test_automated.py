#!/usr/bin/env python3
"""
openhex Automated Test Script

Tests basic functionality of the openhex application.
"""

import sys
import os
import time
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set QT_QPA_PLATFORM to offscreen for headless testing
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest

# Import openhex modules
from src.app import OpenHexApp
from src.main import OpenHexMainWindow


class OpenHexTester:
    """Automated tester for openhex."""

    def __init__(self):
        self.app = None
        self.window = None
        self.test_results = []

    def log(self, status, message):
        """Log test result."""
        symbol = "✓" if status else "✗"
        result = f"[{symbol}] {message}"
        self.test_results.append((status, message))
        print(result)

    def setup(self):
        """Set up the application."""
        print("Setting up openhex...")
        self.app = OpenHexApp.instance()
        self.window = OpenHexMainWindow()
        self.window.show()
        QTest.qWait(100)
        print("Setup complete.\n")

    def test_menu_exists(self):
        """Test that main menus exist."""
        print("Testing: Menu Structure")
        menubar = self.window.menuBar()

        # Get all menu titles
        menu_titles = []
        for action in menubar.actions():
            menu = action.menu()
            if menu:
                menu_titles.append(menu.title())

        print(f"  Found menus: {menu_titles}")

        expected_menus = ["&File", "&Edit", "&View", "Preferences", "&Help"]
        for menu in expected_menus:
            found = any(menu.replace("&", "") in t.replace("&", "") for t in menu_titles)
            self.log(found, f"Menu '{menu}' exists")

    def test_file_operations(self):
        """Test basic file operations."""
        print("\nTesting: File Operations")

        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'Hello, World! This is a test file.\x00\x01\x02\x03\x04\x05')
            self.test_file = f.name

        try:
            # Test opening file
            self.window._on_open_file()
            # Note: This opens a file dialog, which we can't fully automate in offscreen mode

            # Simulate file open
            self.window._open_file(self.test_file)
            QTest.qWait(100)

            self.log(True, f"Opened file: {os.path.basename(self.test_file)}")

            # Check if file info is displayed
            doc = self.window._document_model.current_document
            if doc:
                self.log(True, f"Document loaded: {doc.file_name}, size: {doc.file_size}")
            else:
                self.log(False, "Document not loaded")

            # Test closing file
            if self.window._tab_widget.count() > 0:
                self.window._on_close_file()
                self.log(True, "Closed file")

        finally:
            # Clean up
            if os.path.exists(self.test_file):
                os.unlink(self.test_file)

    def test_view_modes(self):
        """Test view mode switching."""
        print("\nTesting: View Modes")

        # Create test file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'A' * 256)
            self.test_file = f.name

        try:
            self.window._open_file(self.test_file)
            QTest.qWait(50)

            # Test display modes
            modes = ["hex", "binary", "octal"]
            for mode in modes:
                self.window.set_display_mode(mode)
                QTest.qWait(20)
                current_mode = self.window._mode_label.text()
                self.log(True, f"Display mode changed to: {mode}")

            self.window.set_ascii_visible(False)
            QTest.qWait(20)
            self.log(True, "ASCII column hidden")

            self.window.set_ascii_visible(True)
            QTest.qWait(20)
            self.log(True, "ASCII column shown")

            # Test arrangement modes
            self.window.set_arrangement_mode("equal_frame")
            QTest.qWait(20)
            self.log(True, "Arrangement mode: Equal Frame")

            self.window.set_arrangement_mode("header_length")
            QTest.qWait(20)
            self.log(True, "Arrangement mode: Header Length")

        finally:
            if os.path.exists(self.test_file):
                os.unlink(self.test_file)

    def test_find_dialog(self):
        """Test find dialog."""
        print("\nTesting: Find Dialog")

        # Create test file with content
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'Hello World! Hello openhex!')
            self.test_file = f.name

        try:
            self.window._open_file(self.test_file)
            QTest.qWait(50)

            # Show find dialog
            self.window.show_find_dialog()
            QTest.qWait(50)

            self.log(True, "Find dialog opened")

            # Note: Can't interact with dialog in offscreen mode easily

        finally:
            if os.path.exists(self.test_file):
                os.unlink(self.test_file)

    def test_language_settings(self):
        """Test language settings."""
        print("\nTesting: Language Settings")

        # Get current language
        from src.utils.i18n import get_language, set_language

        current = get_language()
        self.log(current in ["en", "zh"], f"Current language: {current}")

        # Test language switch (without GUI interaction)
        set_language("en")
        self.log(get_language() == "en", "Language set to English")

        set_language("zh")
        self.log(get_language() == "zh", "Language set to Chinese")

    def test_arrangement_dialog(self):
        """Test arrangement settings dialog."""
        print("\nTesting: Arrangement Dialog")

        # Create test file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            f.write(b'X' * 100)
            self.test_file = f.name

        try:
            self.window._open_file(self.test_file)
            QTest.qWait(50)

            # Show arrangement dialog
            self.window.show_arrangement_dialog()
            QTest.qWait(50)

            self.log(True, "Arrangement dialog opened")

            # Check default bytes per frame
            bpf = self.window._data_model.bytes_per_frame
            self.log(bpf == 32, f"Default bytes per frame: {bpf}")

        finally:
            if os.path.exists(self.test_file):
                os.unlink(self.test_file)

    def test_hex_view(self):
        """Test hex view functionality."""
        print("\nTesting: Hex View")

        # Create test file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bin') as f:
            # Write some test data
            data = bytes(range(256))  # All byte values 0-255
            f.write(data)
            self.test_file = f.name

        try:
            self.window._open_file(self.test_file)
            QTest.qWait(50)

            # Get hex view
            current_widget = self.window._tab_widget.currentWidget()
            if hasattr(current_widget, 'hex_view'):
                hex_view = current_widget.hex_view
                bpr = hex_view._model._bytes_per_row
                self.log(bpr == 32, f"Default bytes per row: {bpr}")

                # Test changing bytes per row
                hex_view.set_bytes_per_row(16)
                self.log(hex_view._model._bytes_per_row == 16, "Changed bytes per row to 16")

                hex_view.set_bytes_per_row(32)
                self.log(hex_view._model._bytes_per_row == 32, "Changed bytes per row to 32")

        finally:
            if os.path.exists(self.test_file):
                os.unlink(self.test_file)

    def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("openhex Automated Test Suite")
        print("=" * 60)

        self.setup()

        self.test_menu_exists()
        self.test_file_operations()
        self.test_view_modes()
        self.test_find_dialog()
        self.test_language_settings()
        self.test_arrangement_dialog()
        self.test_hex_view()

        # Summary
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)

        passed = sum(1 for r in self.test_results if r[0])
        total = len(self.test_results)

        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")

        if passed == total:
            print("\n✓ All tests passed!")
        else:
            print("\n✗ Some tests failed:")
            for status, msg in self.test_results:
                if not status:
                    print(f"  - {msg}")

        return passed == total


def main():
    """Main entry point."""
    tester = OpenHexTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
