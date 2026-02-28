"""
Data Model

Manages data display and arrangement modes.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum, auto
import mmap


class ArrangementMode(Enum):
    """Arrangement mode enumeration."""
    EQUAL_FRAME = auto()
    HEADER_LENGTH = auto()
    CUSTOM = auto()


class DisplayMode(Enum):
    """Display mode enumeration."""
    HEX = auto()
    BINARY = auto()
    ASCII = auto()
    OCTAL = auto()


class Frame:
    """Represents a data frame in the display."""

    def __init__(self, offset: int, length: int, header: bytes = b'', data: bytes = b''):
        self.offset = offset
        self.length = length
        self.header = header
        self.data = data

    @property
    def total_length(self) -> int:
        """Get total length including header."""
        return len(self.header) + self.length

    def __repr__(self):
        return f"Frame(offset={self.offset}, length={self.length}, header_len={len(self.header)})"


class DataModel(QObject):
    """
    Data model for managing display and arrangement of binary data.

    Handles different arrangement modes (equal frame, header length, custom)
    and display modes (hex, binary, ascii, octal).
    """

    # Signals
    data_changed = pyqtSignal()  # Data arrangement changed
    display_mode_changed = pyqtSignal(DisplayMode)
    arrangement_mode_changed = pyqtSignal(ArrangementMode)
    frame_changed = pyqtSignal(Frame)  # Current frame changed

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._display_mode: DisplayMode = DisplayMode.HEX
        self._arrangement_mode: ArrangementMode = ArrangementMode.EQUAL_FRAME

        # For EQUAL_FRAME mode
        self._bytes_per_frame: int = 32
        self._header_length: int = 0

        # For HEADER_LENGTH mode
        self._header_lengths: List[int] = [4, 8, 16]  # Common header lengths

        # For CUSTOM mode
        self._custom_frames: List[Frame] = []

        # Data access
        self._data: Optional[bytearray] = None
        self._mmap: Optional[mmap.mmap] = None
        self._file_size: int = 0

    @property
    def display_mode(self) -> DisplayMode:
        """Get display mode."""
        return self._display_mode

    @display_mode.setter
    def display_mode(self, mode: DisplayMode):
        """Set display mode."""
        if mode != self._display_mode:
            self._display_mode = mode
            self.display_mode_changed.emit(mode)

    @property
    def arrangement_mode(self) -> ArrangementMode:
        """Get arrangement mode."""
        return self._arrangement_mode

    @arrangement_mode.setter
    def arrangement_mode(self, mode: ArrangementMode):
        """Set arrangement mode."""
        if mode != self._arrangement_mode:
            self._arrangement_mode = mode
            self.arrangement_mode_changed.emit(mode)

    @property
    def bytes_per_frame(self) -> int:
        """Get bytes per frame for EQUAL_FRAME mode."""
        return self._bytes_per_frame

    @bytes_per_frame.setter
    def bytes_per_frame(self, value: int):
        """Set bytes per frame for EQUAL_FRAME mode (1-65535)."""
        value = max(1, min(65535, value))
        if value != self._bytes_per_frame:
            self._bytes_per_frame = value
            self.data_changed.emit()

    @property
    def header_length(self) -> int:
        """Get header length for HEADER_LENGTH mode."""
        return self._header_length

    @header_length.setter
    def header_length(self, value: int):
        """Set header length for HEADER_LENGTH mode (1-8)."""
        value = max(1, min(8, value))
        if value != self._header_length:
            self._header_length = value
            self.data_changed.emit()

    @property
    def header_lengths(self) -> List[int]:
        """Get header lengths for HEADER_LENGTH mode."""
        return self._header_lengths.copy()

    @header_lengths.setter
    def header_lengths(self, lengths: List[int]):
        """Set header lengths."""
        self._header_lengths = sorted(set(max(0, l) for l in lengths))
        self.data_changed.emit()

    def set_data(self, data: bytes):
        """Set data to display."""
        self._data = bytearray(data)
        self._file_size = len(data)
        self._mmap = None
        self.data_changed.emit()

    def set_mmap(self, m: mmap.mmap):
        """Set memory mapped data."""
        self._mmap = m
        self._data = None
        self._file_size = len(m)
        self.data_changed.emit()

    def clear_data(self):
        """Clear data."""
        self._data = None
        self._mmap = None
        self._file_size = 0
        self.data_changed.emit()

    def read(self, offset: int, length: int) -> bytes:
        """Read bytes from data."""
        if self._data is not None:
            end = min(offset + length, len(self._data))
            return bytes(self._data[offset:end])
        elif self._mmap is not None:
            end = min(offset + length, len(self._mmap))
            return self._mmap[offset:end]
        return b''

    def read_byte(self, offset: int) -> Optional[int]:
        """Read single byte."""
        if self._data is not None:
            if 0 <= offset < len(self._data):
                return self._data[offset]
        elif self._mmap is not None:
            if 0 <= offset < len(self._mmap):
                return self._mmap[offset]
        return None

    def get_frame_count(self) -> int:
        """Get number of frames (rows in display)."""
        if self._file_size == 0:
            return 0

        if self._arrangement_mode == ArrangementMode.EQUAL_FRAME:
            # 等长帧：每行固定字节数
            bytes_per_row = self._bytes_per_frame
            return (self._file_size + bytes_per_row - 1) // bytes_per_row

        elif self._arrangement_mode == ArrangementMode.HEADER_LENGTH:
            # 头长度：需要逐行计算
            count = 0
            offset = 0
            header_len = self._header_length
            while offset < self._file_size:
                # 读取头部的长度值
                if offset + header_len > self._file_size:
                    break
                header_bytes = self.read(offset, header_len)
                # 将头部作为整数解析（默认大端序）
                data_len = int.from_bytes(header_bytes, byteorder='big')
                # 移动到下一行
                offset += header_len + data_len
                count += 1
            return count

        elif self._arrangement_mode == ArrangementMode.CUSTOM:
            return len(self._custom_frames)

        return 0

    def get_frame(self, frame_index: int) -> Optional[Frame]:
        """Get frame at index (row in display)."""
        if frame_index < 0:
            return None

        if self._arrangement_mode == ArrangementMode.EQUAL_FRAME:
            return self._get_equal_frame(frame_index)

        elif self._arrangement_mode == ArrangementMode.HEADER_LENGTH:
            return self._get_header_frame(frame_index)

        elif self._arrangement_mode == ArrangementMode.CUSTOM:
            if frame_index < len(self._custom_frames):
                return self._custom_frames[frame_index]

        return None

    def _get_equal_frame(self, frame_index: int) -> Optional[Frame]:
        """Get frame in EQUAL_FRAME mode - fixed bytes per row."""
        data_len = self._bytes_per_frame
        frame_offset = frame_index * data_len

        if frame_offset >= self._file_size:
            return None

        # Read data
        remaining = self._file_size - frame_offset
        actual_len = min(data_len, remaining)
        data = self.read(frame_offset, actual_len)

        return Frame(frame_offset, actual_len, b'', data)

    def _get_header_frame(self, frame_index: int) -> Optional[Frame]:
        """Get frame in HEADER_LENGTH mode - header indicates data length."""
        header_len = self._header_length
        offset = 0

        # Find the start offset of the requested frame
        for i in range(frame_index):
            if offset >= self._file_size:
                return None
            # Read header to get data length
            if offset + header_len > self._file_size:
                return None
            header_bytes = self.read(offset, header_len)
            data_len = int.from_bytes(header_bytes, byteorder='big')
            offset += header_len + data_len

        # Now read the requested frame
        if offset >= self._file_size:
            return None

        if offset + header_len > self._file_size:
            # Not enough data for header
            return None

        # Read header
        header = self.read(offset, header_len)

        # Parse header as data length
        data_len = int.from_bytes(header, byteorder='big')

        # Read data
        data_offset = offset + header_len
        if data_offset + data_len > self._file_size:
            # Not enough data, read what's available
            actual_data_len = self._file_size - data_offset
        else:
            actual_data_len = data_len

        data = self.read(data_offset, actual_data_len)

        return Frame(offset, actual_data_len, header, data)

    def offset_to_position(self, offset: int) -> Tuple[int, int]:
        """
        Convert file offset to frame and byte position.

        Args:
            offset: File offset

        Returns:
            (frame_index, byte_index)
        """
        if self._file_size == 0:
            return (0, 0)

        header_len = self._header_length
        total_per_frame = self._bytes_per_frame + header_len

        frame_index = offset // total_per_frame
        byte_index = offset % total_per_frame

        if byte_index < header_len:
            byte_index = header_len

        return (frame_index, byte_index - header_len)

    def position_to_offset(self, frame_index: int, byte_index: int) -> int:
        """
        Convert frame and byte position to file offset.

        Args:
            frame_index: Frame index
            byte_index: Byte index within frame

        Returns:
            File offset
        """
        header_len = self._header_length
        total_per_frame = self._bytes_per_frame + header_len
        return frame_index * total_per_frame + header_len + byte_index

    def format_byte(self, byte: int) -> str:
        """Format single byte according to display mode."""
        if self._display_mode == DisplayMode.HEX:
            return f"{byte:02X}"
        elif self._display_mode == DisplayMode.BINARY:
            return f"{byte:08b}"
        elif self._display_mode == DisplayMode.ASCII:
            if 32 <= byte < 127:
                return chr(byte)
            return '.'
        elif self._display_mode == DisplayMode.OCTAL:
            return f"{byte:03o}"
        return f"{byte:02X}"

    def format_data(self, data: bytes) -> str:
        """Format data according to display mode."""
        if self._display_mode == DisplayMode.ASCII:
            return ''.join(self.format_byte(b) for b in data)
        elif self._display_mode == DisplayMode.BINARY:
            return ' '.join(self.format_byte(b) for b in data)
        else:
            return ' '.join(self.format_byte(b) for b in data)

    def get_bytes_per_row(self) -> int:
        """Get bytes per row for display."""
        return self._bytes_per_frame
