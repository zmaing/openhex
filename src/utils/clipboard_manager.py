"""
Clipboard Manager for openhex.

Handles clipboard operations for hex data.
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject
import re


class ClipboardManager(QObject):
    """Manage clipboard operations for hex data."""

    @staticmethod
    def copy_hex(data: bytes) -> str:
        """Format bytes as hex string with spaces."""
        return ' '.join(f'{b:02X}' for b in data)

    @staticmethod
    def copy_binary(data: bytes) -> str:
        """Format bytes as binary string."""
        return ' '.join(f'{b:08b}' for b in data)

    @staticmethod
    def copy_octal(data: bytes) -> str:
        """Format bytes as octal string."""
        return ' '.join(f'{b:03o}' for b in data)

    @staticmethod
    def copy_ascii(data: bytes) -> str:
        """Format bytes as ASCII string."""
        return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)

    @staticmethod
    def copy_to_clipboard(text: str):
        """Copy text to system clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    @staticmethod
    def get_from_clipboard() -> str:
        """Get text from system clipboard."""
        clipboard = QApplication.clipboard()
        return clipboard.text()

    @staticmethod
    def parse_hex_string(text: str) -> bytes:
        """Parse hex string to bytes. Supports formats:
        - "00 01 02 FF"
        - "00FF"
        - "00, 01, FF"
        """
        # Remove common separators
        text = text.replace(',', ' ').replace(':', ' ')
        # Extract hex pairs
        hex_chars = re.findall(r'[0-9A-Fa-f]{2}', text)
        if not hex_chars:
            return None
        # Validate that the input is pure hex
        cleaned = text.replace(' ', '')
        if len(cleaned) % 2 != 0:
            return None
        try:
            return bytes(int(h, 16) for h in hex_chars)
        except ValueError:
            return None

    @staticmethod
    def parse_clipboard() -> bytes:
        """Parse clipboard content and return bytes.

        Tries hex format first, then ASCII text.
        """
        text = ClipboardManager.get_from_clipboard()
        if not text:
            return b''

        # Try hex format first
        result = ClipboardManager.parse_hex_string(text)
        if result is not None:
            return result

        # Try as ASCII text
        try:
            return text.encode('ascii')
        except UnicodeEncodeError:
            return b''
