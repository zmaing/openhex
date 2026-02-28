"""
Memory Map

Memory-mapped file access for large files.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List, Tuple
import mmap
import os

from ..utils.logger import logger


class MemoryMap(QObject):
    """
    Memory-mapped file access manager.

    Provides efficient access to large files using mmap.
    """

    # Signals
    mapped = pyqtSignal(int)  # File size
    unmapped = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._file_path: Optional[str] = None
        self._mmap: Optional[mmap.mmap] = None
        self._file_size: int = 0
        self._is_readonly: bool = True

    @property
    def file_path(self) -> Optional[str]:
        """Get mapped file path."""
        return self._file_path

    @property
    def file_size(self) -> int:
        """Get mapped file size."""
        return self._file_size

    @property
    def is_mapped(self) -> bool:
        """Check if file is mapped."""
        return self._mmap is not None

    @property
    def is_readonly(self) -> bool:
        """Check if mapping is read-only."""
        return self._is_readonly

    def map_file(self, path: str, readonly: bool = True) -> bool:
        """
        Memory map a file.

        Args:
            path: File path to map
            readonly: Open read-only

        Returns:
            True if successful
        """
        try:
            # Close existing mapping
            self.unmap()

            # Open file
            mode = 'rb' if readonly else 'r+b'
            file = open(path, mode)

            # Get file size
            file.seek(0, 2)
            self._file_size = file.tell()
            file.seek(0)

            if self._file_size == 0:
                # Can't mmap empty file
                file.close()
                logger.warning("Cannot mmap empty file")
                return False

            # Create mmap
            access = mmap.ACCESS_READ if readonly else mmap.ACCESS_WRITE
            self._mmap = mmap.mmap(file.fileno(), 0, access=access)
            self._file_path = path
            self._is_readonly = readonly

            # File handle will be closed when mmap is closed
            file.close()

            self.mapped.emit(self._file_size)
            logger.info(f"Mapped file: {path} ({self._file_size} bytes)")
            return True

        except Exception as e:
            logger.error(f"Failed to map file: {e}")
            return False

    def map_bytes(self, data: bytes) -> bool:
        """
        Map bytes data.

        Args:
            data: Bytes data

        Returns:
            True if successful
        """
        try:
            self.unmap()
            self._mmap = mmap.mmap(-1, len(data))
            self._mmap[:] = data
            self._file_size = len(data)
            self._file_path = None
            self._is_readonly = False
            self.mapped.emit(self._file_size)
            return True
        except Exception as e:
            logger.error(f"Failed to map bytes: {e}")
            return False

    def unmap(self):
        """Unmap current file."""
        if self._mmap:
            try:
                self._mmap.close()
            except Exception as e:
                logger.warning(f"Error closing mmap: {e}")
            self._mmap = None

        self._file_path = None
        self._file_size = 0
        self.unmap()

    def read(self, offset: int, length: int) -> bytes:
        """
        Read bytes from mapped file.

        Args:
            offset: Start offset
            length: Number of bytes

        Returns:
            Bytes read
        """
        if not self._mmap:
            return b''

        # Clamp to bounds
        if offset < 0:
            offset = 0
        if offset >= self._file_size:
            return b''

        length = min(length, self._file_size - offset)

        if self._is_readonly:
            return self._mmap[offset:offset + length]
        else:
            return bytes(self._mmap[offset:offset + length])

    def read_byte(self, offset: int) -> Optional[int]:
        """
        Read single byte.

        Args:
            offset: Offset

        Returns:
            Byte value or None
        """
        if offset < 0 or offset >= self._file_size:
            return None

        if self._is_readonly:
            return self._mmap[offset]
        else:
            return self._mmap[offset]

    def write(self, offset: int, data: bytes) -> int:
        """
        Write bytes to mapped file.

        Args:
            offset: Start offset
            data: Data to write

        Returns:
            Bytes written
        """
        if not self._mmap or self._is_readonly:
            return 0

        try:
            self._mmap[offset:offset + len(data)] = data
            return len(data)
        except Exception as e:
            logger.error(f"Write error: {e}")
            return 0

    def find(self, pattern: bytes, start: int = 0) -> Optional[int]:
        """
        Find pattern in mapped data.

        Args:
            pattern: Pattern to find
            start: Start offset

        Returns:
            Offset of pattern or None
        """
        if not self._mmap or not pattern:
            return None

        try:
            pos = self._mmap.find(pattern, start)
            if pos >= 0:
                return pos
            return None
        except Exception as e:
            logger.error(f"Find error: {e}")
            return None

    def find_all(self, pattern: bytes) -> List[int]:
        """
        Find all occurrences of pattern.

        Args:
            pattern: Pattern to find

        Returns:
            List of offsets
        """
        if not self._mmap or not pattern:
            return []

        positions = []
        pos = 0
        while True:
            pos = self.find(pattern, pos)
            if pos is None:
                break
            positions.append(pos)
            pos += 1

        return positions

    def flush(self) -> bool:
        """Flush changes to disk."""
        if self._mmap and not self._is_readonly:
            try:
                self._mmap.flush()
                return True
            except Exception as e:
                logger.error(f"Flush error: {e}")
        return False

    def get_page(self, offset: int, page_size: int = 4096) -> bytes:
        """
        Get a page of data.

        Args:
            offset: Page offset
            page_size: Page size

        Returns:
            Page data
        """
        return self.read(offset, page_size)

    def get_pages(self, offsets: List[int], page_size: int = 4096) -> List[bytes]:
        """
        Get multiple pages.

        Args:
            offsets: List of offsets
            page_size: Page size

        Returns:
            List of page data
        """
        return [self.get_page(offset, page_size) for offset in offsets]

    def __getitem__(self, index: int) -> int:
        """Get byte at index."""
        return self.read_byte(index)

    def __len__(self) -> int:
        """Get file size."""
        return self._file_size

    def __iter__(self):
        """Iterate over bytes."""
        for i in range(self._file_size):
            yield self.read_byte(i)

    def __del__(self):
        """Cleanup."""
        self.unmap()
