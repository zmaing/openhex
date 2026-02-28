"""
Search Engine

Hex and text search functionality.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from typing import Optional, List, Tuple, Callable
from enum import Enum, auto

import re


class SearchMode(Enum):
    """Search mode enumeration."""
    HEX = auto()
    TEXT = auto()
    REGEX = auto()


class SearchDirection(Enum):
    """Search direction."""
    FORWARD = auto()
    BACKWARD = auto()


class SearchResult:
    """Search result container."""

    def __init__(self, offset: int, length: int, text: str = ""):
        self.offset = offset
        self.length = length
        self.text = text

    def __repr__(self):
        return f"SearchResult(offset={self.offset}, length={self.length})"

    def __eq__(self, other):
        if isinstance(other, SearchResult):
            return self.offset == other.offset
        return False

    def __hash__(self):
        return hash(self.offset)


class SearchEngine(QObject):
    """
    Search engine for hex and text search.

    Provides search with progress reporting and result highlighting.
    """

    # Signals
    search_started = pyqtSignal(str)  # Search pattern
    search_progress = pyqtSignal(int, int)  # current, total
    search_result = pyqtSignal(object)  # Found result
    search_finished = pyqtSignal(object)  # All results
    search_cancelled = pyqtSignal()
    search_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._data: Optional[bytearray] = None
        self._mmap = None
        self._file_size: int = 0
        self._is_searching: bool = False

    @property
    def is_searching(self) -> bool:
        """Check if currently searching."""
        return self._is_searching

    def set_data(self, data: bytes):
        """Set data to search."""
        self._data = bytearray(data)
        self._mmap = None
        self._file_size = len(data)

    def set_mmap(self, m):
        """Set memory-mapped data."""
        self._data = None
        self._mmap = m
        self._file_size = len(m)

    def _read(self, offset: int, length: int) -> bytes:
        """Read bytes from data."""
        if self._data is not None:
            return bytes(self._data[offset:offset + length])
        elif self._mmap is not None:
            return self._mmap.read(offset, length)
        return b''

    def search(self, pattern: str, mode: SearchMode = SearchMode.TEXT,
               direction: SearchDirection = SearchDirection.FORWARD,
               start_offset: int = 0) -> Optional[SearchResult]:
        """
        Search for pattern.

        Args:
            pattern: Search pattern
            mode: Search mode
            direction: Search direction
            start_offset: Starting offset

        Returns:
            SearchResult if found, None otherwise
        """
        if self._file_size == 0 or not pattern:
            return None

        try:
            if mode == SearchMode.HEX:
                return self._search_hex(pattern, direction, start_offset)
            elif mode == SearchMode.TEXT:
                return self._search_text(pattern, direction, start_offset)
            elif mode == SearchMode.REGEX:
                return self._search_regex(pattern, direction, start_offset)
        except Exception as e:
            self.search_error.emit(str(e))
            return None

        return None

    def _search_hex(self, pattern: str, direction: SearchDirection,
                    start_offset: int) -> Optional[SearchResult]:
        """Search hex pattern."""
        # Convert hex string to bytes
        pattern = pattern.replace(' ', '').replace('-', '')
        if len(pattern) % 2 != 0:
            pattern = '0' + pattern

        try:
            search_bytes = bytes.fromhex(pattern)
        except ValueError:
            return None

        if direction == SearchDirection.FORWARD:
            pos = self._read_bytes(start_offset).find(search_bytes)
        else:
            pos = self._read_bytes(start_offset).rfind(search_bytes)

        if pos >= 0:
            return SearchResult(start_offset + pos, len(search_bytes))
        return None

    def _search_text(self, pattern: str, direction: SearchDirection,
                     start_offset: int) -> Optional[SearchResult]:
        """Search text pattern."""
        search_bytes = pattern.encode('utf-8')

        if direction == SearchDirection.FORWARD:
            pos = self._read_bytes(start_offset).find(search_bytes)
        else:
            pos = self._read_bytes(start_offset).rfind(search_bytes)

        if pos >= 0:
            return SearchResult(start_offset + pos, len(search_bytes), pattern)
        return None

    def _search_regex(self, pattern: str, direction: SearchDirection,
                      start_offset: int) -> Optional[SearchResult]:
        """Search with regex."""
        try:
            # Encode pattern as bytes for matching against bytes data
            pattern_bytes = pattern.encode('ascii')
            regex = re.compile(pattern_bytes)
            data = self._read_bytes(start_offset)

            if direction == SearchDirection.FORWARD:
                match = regex.search(data)
            else:
                # Find all and return last
                matches = list(regex.finditer(data))
                if matches:
                    match = matches[-1]
                else:
                    match = None

            if match:
                return SearchResult(
                    start_offset + match.start(),
                    match.end() - match.start(),
                    match.group()
                )
        except re.error as e:
            self.search_error.emit(f"Invalid regex: {e}")

        return None

    def search_all(self, pattern: str, mode: SearchMode = SearchMode.TEXT) -> List[SearchResult]:
        """
        Search for all occurrences.

        Args:
            pattern: Search pattern
            mode: Search mode

        Returns:
            List of search results
        """
        results = []

        if self._file_size == 0 or not pattern:
            return results

        try:
            if mode == SearchMode.HEX:
                results = self._search_all_hex(pattern)
            elif mode == SearchMode.TEXT:
                results = self._search_all_text(pattern)
            elif mode == SearchMode.REGEX:
                results = self._search_all_regex(pattern)
        except Exception as e:
            self.search_error.emit(str(e))

        return results

    def _search_all_hex(self, pattern: str) -> List[SearchResult]:
        """Search all hex occurrences."""
        import os
        log_path = "/Users/zhanghaoli/Documents/WorkFile/Code/myhxd/hex_forge/logs/debug.log"

        with open(log_path, "a") as f:
            f.write(f"[SEARCH] _search_all_hex INPUT: pattern='{pattern}'\n")

        pattern = pattern.replace(' ', '').replace('-', '')
        with open(log_path, "a") as f:
            f.write(f"[SEARCH] _search_all_hex cleaned: pattern='{pattern}'\n")

        if len(pattern) % 2 != 0:
            pattern = '0' + pattern
            with open(log_path, "a") as f:
                f.write(f"[SEARCH] _search_all_hex padded: pattern='{pattern}'\n")

        try:
            search_bytes = bytes.fromhex(pattern)
            with open(log_path, "a") as f:
                f.write(f"[SEARCH] _search_all_hex parsed: search_bytes={search_bytes!r}, len={len(search_bytes)}\n")
        except ValueError as e:
            with open(log_path, "a") as f:
                f.write(f"[SEARCH] _search_all_hex ERROR: {e}\n")
            return []

        results = []
        data = self._read_bytes(0)

        pos = 0
        while True:
            pos = data.find(search_bytes, pos)
            if pos < 0:
                break
            with open(log_path, "a") as f:
                f.write(f"[SEARCH] Found at pos={pos}\n")
            results.append(SearchResult(pos, len(search_bytes)))
            pos += 1

        return results

    def _search_all_text(self, pattern: str) -> List[SearchResult]:
        """Search all text occurrences."""
        search_bytes = pattern.encode('utf-8')
        results = []
        data = self._read_bytes(0)
        pos = 0
        while True:
            pos = data.find(search_bytes, pos)
            if pos < 0:
                break
            results.append(SearchResult(pos, len(search_bytes), pattern))
            pos += 1

        return results

    def _search_all_regex(self, pattern: str) -> List[SearchResult]:
        """Search all regex matches."""
        try:
            # Encode pattern as bytes for matching against bytes data
            pattern_bytes = pattern.encode('ascii')
            regex = re.compile(pattern_bytes)
            data = self._read_bytes(0)
            results = []

            for match in regex.finditer(data):
                results.append(SearchResult(
                    match.start(),
                    match.end() - match.start(),
                    match.group()
                ))

            return results
        except re.error as e:
            self.search_error.emit(f"Invalid regex: {e}")
            return []

    def _read_bytes(self, offset: int) -> bytes:
        """Read all bytes from offset."""
        if self._data is not None:
            return bytes(self._data[offset:])
        elif self._mmap is not None:
            return self._mmap.read(offset, self._file_size - offset)
        return b''

    def replace(self, offset: int, length: int, replacement: bytes) -> bytes:
        """
        Replace bytes at offset.

        Args:
            offset: Offset
            length: Length to replace
            replacement: Replacement data

        Returns:
            New data
        """
        if self._data is not None:
            new_data = bytearray(self._data)
            new_data[offset:offset + length] = replacement
            return bytes(new_data)
        return replacement

    def replace_all(self, pattern: str, replacement: str,
                    mode: SearchMode = SearchMode.TEXT) -> Tuple[int, bytes]:
        """
        Replace all occurrences.

        Args:
            pattern: Pattern to replace
            replacement: Replacement text
            mode: Search mode

        Returns:
            (count, new_data)
        """
        results = self.search_all(pattern, mode)
        if not results:
            return 0, b''

        if self._data is None:
            return 0, b''

        new_data = bytearray(self._data)
        offset_delta = 0

        for result in results:
            if mode == SearchMode.TEXT:
                replacement_bytes = replacement.encode('utf-8')
            else:
                replacement_bytes = bytes.fromhex(replacement.replace(' ', ''))

            old_len = result.length
            new_len = len(replacement_bytes)

            new_data[result.offset + offset_delta:result.offset + offset_delta + old_len] = replacement_bytes
            offset_delta += new_len - old_len

        return len(results), bytes(new_data)
