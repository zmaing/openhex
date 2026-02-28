"""
File Handle Model

Manages a single file's data and state.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QByteArray
from PyQt6.QtWidgets import QFileDialog, QMessageBox

import os
import mmap
import tempfile
import hashlib
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum, auto

from ..utils.logger import logger


class FileState(Enum):
    """File state enumeration."""
    UNCHANGED = auto()
    MODIFIED = auto()
    NEW = auto()
    LOADING = auto()
    SAVING = auto()


class FileType(Enum):
    """File type enumeration."""
    BINARY = auto()
    TEXT = auto()
    JSON = auto()
    XML = auto()
    UNKNOWN = auto()


class FileHandle(QObject):
    """
    File handle for managing a single file's data.

    Provides memory-efficient handling for large files using mmap
    when appropriate.
    """

    # Signals
    data_changed = pyqtSignal(int, int)  # start, end positions
    state_changed = pyqtSignal(FileState)
    cursor_moved = pyqtSignal(int)  # offset
    selection_changed = pyqtSignal(int, int)  # start, end

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._file_path: Optional[str] = None
        self._file_name: str = "Untitled"
        self._file_size: int = 0
        self._file_state: FileState = FileState.NEW
        self._file_type: FileType = FileType.UNKNOWN
        self._encoding: str = "utf-8"

        # Data storage
        self._data: bytearray = bytearray()
        self._file = None  # File object for mmap
        self._mmap: Optional[mmap.mmap] = None
        self._is_mapped: bool = False
        self._temp_file: Optional[str] = None

        # For large file handling
        self._use_mmap_threshold: int = 100 * 1024 * 1024  # 100MB
        self._page_size: int = 4096

        # Bookmarks
        self._bookmarks: List[int] = []

        # Navigation history
        self._jump_history: List[int] = []
        self._jump_index: int = -1

    @property
    def file_path(self) -> Optional[str]:
        """Get file path."""
        return self._file_path

    @file_path.setter
    def file_path(self, path: str):
        """Set file path."""
        self._file_path = path
        if path:
            self._file_name = os.path.basename(path)
            self.detect_file_type()

    @property
    def file_name(self) -> str:
        """Get file name."""
        return self._file_name

    @file_name.setter
    def file_name(self, name: str):
        """Set file name."""
        self._file_name = name

    @property
    def file_size(self) -> int:
        """Get file size."""
        return self._file_size

    @property
    def file_state(self) -> FileState:
        """Get file state."""
        return self._file_state

    @file_state.setter
    def file_state(self, state: FileState):
        """Set file state."""
        if self._file_state != state:
            self._file_state = state
            self.state_changed.emit(state)

    @property
    def file_type(self) -> FileType:
        """Get file type."""
        return self._file_type

    @property
    def encoding(self) -> str:
        """Get text encoding."""
        return self._encoding

    @encoding.setter
    def encoding(self, enc: str):
        """Set text encoding."""
        self._encoding = enc

    @property
    def is_empty(self) -> bool:
        """Check if file is empty."""
        return self._file_size == 0

    @property
    def is_mapped(self) -> bool:
        """Check if file is memory mapped."""
        return self._is_mapped

    @property
    def bookmarks(self) -> List[int]:
        """Get bookmarks."""
        return self._bookmarks.copy()

    @property
    def jump_history(self) -> List[int]:
        """Get jump history."""
        return self._jump_history.copy()

    def detect_file_type(self):
        """Detect file type from path and content."""
        if not self._file_path:
            self._file_type = FileType.UNKNOWN
            return

        ext = os.path.splitext(self._file_name)[1].lower()

        type_map = {
            ".json": FileType.JSON,
            ".xml": FileType.XML,
            ".txt": FileType.TEXT,
        }

        self._file_type = type_map.get(ext, FileType.BINARY)

        # For small files, check content
        if self._file_type == FileType.BINARY and self._file_size < 1024 * 1024:
            try:
                content = self.read(0, min(1024, self._file_size))
                if b'\x00' not in content:
                    # Likely text
                    try:
                        content.decode('utf-8')
                        self._file_type = FileType.TEXT
                    except UnicodeDecodeError:
                        pass
            except Exception:
                pass

    def load_from_path(self, path: str) -> bool:
        """
        Load file from path.

        Args:
            path: File path to load

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(path):
                logger.error(f"File not found: {path}")
                return False

            self._file_path = path
            self._file_name = os.path.basename(path)
            self._file_size = os.path.getsize(path)
            self.file_state = FileState.UNCHANGED
            self.detect_file_type()

            if self._file_size >= self._use_mmap_threshold:
                return self._load_large_file()
            else:
                return self._load_small_file()

        except Exception as e:
            logger.error(f"Failed to load file: {e}")
            return False

    def _load_small_file(self) -> bool:
        """Load small file into memory."""
        try:
            with open(self._file_path, 'rb') as f:
                self._data = bytearray(f.read())
            self._is_mapped = False
            logger.info(f"Loaded small file: {self._file_name} ({self._file_size} bytes)")
            return True
        except Exception as e:
            logger.error(f"Failed to load small file: {e}")
            return False

    def _load_large_file(self) -> bool:
        """Load large file using mmap."""
        try:
            self._file = open(self._file_path, 'rb')
            self._mmap = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
            self._is_mapped = True
            logger.info(f"Memory mapped large file: {self._file_name} ({self._file_size} bytes)")
            return True
        except Exception as e:
            logger.error(f"Failed to memory map file: {e}")
            return False

    def read(self, offset: int, length: int) -> bytes:
        """
        Read bytes from file.

        Args:
            offset: Starting offset
            length: Number of bytes to read

        Returns:
            Bytes read
        """
        if self.is_empty:
            return b''

        # Clamp to file bounds
        offset = max(0, offset)
        if offset >= self._file_size:
            return b''

        length = min(length, self._file_size - offset)

        if self._is_mapped and self._mmap:
            return self._mmap[offset:offset + length]
        else:
            return bytes(self._data[offset:offset + length])

    def read_byte(self, offset: int) -> Optional[int]:
        """
        Read single byte at offset.

        Args:
            offset: Byte offset

        Returns:
            Byte value (0-255) or None if out of bounds
        """
        if offset < 0 or offset >= self._file_size:
            return None

        if self._is_mapped and self._mmap:
            return self._mmap[offset]
        else:
            return self._data[offset]

    def write(self, offset: int, data: bytes) -> int:
        """
        Write bytes to file.

        Args:
            offset: Starting offset
            data: Bytes to write

        Returns:
            Number of bytes written
        """
        if self.is_empty:
            return 0

        if self._is_mapped:
            # For mmap files, we need to use a temp file for modifications
            return self._write_large_file(offset, data)
        else:
            return self._write_small_file(offset, data)

    def _write_small_file(self, offset: int, data: bytes) -> int:
        """Write to small file in memory."""
        if offset < 0:
            offset = 0

        if offset > len(self._data):
            # Pad with zeros
            self._data.extend(b'\x00' * (offset - len(self._data)))

        # Insert or replace data
        data_len = len(data)
        new_len = max(len(self._data), offset + data_len)

        if offset + data_len <= len(self._data):
            # Replace existing data
            self._data[offset:offset + data_len] = data
        else:
            # Need to extend
            old_data = self._data[:offset]
            self._data = bytearray(old_data + data)

        self.file_state = FileState.MODIFIED
        self.data_changed.emit(offset, offset + data_len)
        return data_len

    def _write_large_file(self, offset: int, data: bytes) -> int:
        """Write to large file using copy-on-write."""
        if not self._temp_file:
            # Create temp file
            self._temp_file = tempfile.mktemp(suffix='.hexforge')
            try:
                with open(self._file_path, 'rb') as src:
                    with open(self._temp_file, 'wb') as dst:
                        dst.write(src.read())
            except Exception as e:
                logger.error(f"Failed to create temp file: {e}")
                return 0

        # Reopen mmap on temp file
        if self._mmap:
            self._mmap.close()
            self._file.close()

        try:
            self._file = open(self._temp_file, 'r+b')
            self._mmap = mmap.mmap(self._file.fileno(), 0)

            # Write data
            self._mmap[offset:offset + len(data)] = data

            # Update tracking
            self._is_mapped = False  # Now using copy
            self.file_state = FileState.MODIFIED
            self.data_changed.emit(offset, offset + len(data))

            return len(data)
        except Exception as e:
            logger.error(f"Failed to write to large file: {e}")
            return 0

    def insert(self, offset: int, data: bytes) -> int:
        """
        Insert bytes at offset.

        Args:
            offset: Insertion offset
            data: Bytes to insert

        Returns:
            Number of bytes inserted
        """
        if self._is_mapped:
            # Convert to in-memory for inserts
            self._convert_to_memory()

        data_len = len(data)
        if data_len == 0:
            return 0

        if offset < 0:
            offset = 0
        elif offset > len(self._data):
            offset = len(self._data)

        self._data[offset:offset] = data
        self._file_size = len(self._data)
        self.file_state = FileState.MODIFIED
        self.data_changed.emit(offset, offset + data_len)

        return data_len

    def delete(self, offset: int, length: int) -> int:
        """
        Delete bytes at offset.

        Args:
            offset: Deletion offset
            length: Number of bytes to delete

        Returns:
            Number of bytes deleted
        """
        if self._is_mapped:
            self._convert_to_memory()

        if offset < 0 or offset >= len(self._data):
            return 0

        length = min(length, len(self._data) - offset)
        if length == 0:
            return 0

        del self._data[offset:offset + length]
        self._file_size = len(self._data)
        self.file_state = FileState.MODIFIED
        self.data_changed.emit(offset, offset + length)

        return length

    def _convert_to_memory(self):
        """Convert mmap file to in-memory."""
        if self._mmap:
            self._data = bytearray(self._mmap[:])
            self._mmap.close()
            self._mmap = None
            self._is_mapped = False

            if self._file:
                self._file.close()
                self._file = None

        logger.info("Converted file from mmap to memory")

    def save(self, path: Optional[str] = None) -> bool:
        """
        Save file to disk.

        Args:
            path: Optional new path

        Returns:
            True if successful
        """
        save_path = path or self._file_path
        if not save_path:
            return False

        try:
            # If using temp file (from large file edits), save from there
            source = self._temp_file if self._temp_file else self._file_path

            if self._is_mapped and self._temp_file:
                # Need to close mmap before copying
                pass
            elif not self._is_mapped:
                with open(save_path, 'wb') as f:
                    f.write(self._data)

            # Update state
            self._file_path = save_path
            self._file_name = os.path.basename(save_path)
            self.file_state = FileState.UNCHANGED

            # Clean up temp file
            if self._temp_file:
                try:
                    os.unlink(self._temp_file)
                except:
                    pass
                self._temp_file = None

            logger.info(f"Saved file: {self._file_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return False

    def get_checksum(self, algorithm: str = "sha256") -> str:
        """
        Get file checksum.

        Args:
            algorithm: Hash algorithm (md5, sha1, sha256)

        Returns:
            Hex digest of checksum
        """
        hash_func = hashlib.new(algorithm)
        chunk_size = 8192

        if self._is_mapped and self._temp_file:
            # Read from temp file
            with open(self._temp_file, 'rb') as f:
                for chunk in iter(lambda: f.read(chunk_size), b''):
                    hash_func.update(chunk)
        elif self._is_mapped and self._mmap:
            # Read from mmap
            hash_func.update(self._mmap[:])
        else:
            hash_func.update(self._data)

        return hash_func.hexdigest()

    # Bookmark management
    def add_bookmark(self, offset: int):
        """Add bookmark at offset."""
        if offset not in self._bookmarks:
            self._bookmarks.append(offset)
            self._bookmarks.sort()

    def remove_bookmark(self, offset: int):
        """Remove bookmark at offset."""
        if offset in self._bookmarks:
            self._bookmarks.remove(offset)

    def toggle_bookmark(self, offset: int):
        """Toggle bookmark at offset."""
        if offset in self._bookmarks:
            self._bookmarks.remove(offset)
        else:
            self._bookmarks.append(offset)

    def get_next_bookmark(self, offset: int) -> Optional[int]:
        """Get next bookmark after offset."""
        for bookmark in self._bookmarks:
            if bookmark > offset:
                return bookmark
        return None

    def get_prev_bookmark(self, offset: int) -> Optional[int]:
        """Get previous bookmark before offset."""
        prev = None
        for bookmark in self._bookmarks:
            if bookmark >= offset:
                break
            prev = bookmark
        return prev

    # Jump history
    def add_jump(self, offset: int):
        """Add position to jump history."""
        # Remove if already exists
        if offset in self._jump_history:
            self._jump_history.remove(offset)

        self._jump_history.append(offset)
        self._jump_index = len(self._jump_history) - 1

    def jump_back(self) -> Optional[int]:
        """Go back in jump history."""
        if self._jump_index > 0:
            self._jump_index -= 1
            return self._jump_history[self._jump_index]
        return None

    def jump_forward(self) -> Optional[int]:
        """Go forward in jump history."""
        if self._jump_index < len(self._jump_history) - 1:
            self._jump_index += 1
            return self._jump_history[self._jump_index]
        return None

    def can_jump_back(self) -> bool:
        """Check if can jump back."""
        return self._jump_index > 0

    def can_jump_forward(self) -> bool:
        """Check if can jump forward."""
        return self._jump_index < len(self._jump_history) - 1

    def clear_jump_history(self):
        """Clear jump history."""
        self._jump_history.clear()
        self._jump_index = -1

    def close(self):
        """Clean up resources."""
        if self._mmap:
            self._mmap.close()
            self._mmap = None

        if self._file:
            self._file.close()
            self._file = None

        if self._temp_file:
            try:
                os.unlink(self._temp_file)
            except:
                pass
            self._temp_file = None

        self._data.clear()

    def __del__(self):
        """Destructor."""
        self.close()
