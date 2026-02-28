"""
Cursor Model

Manages cursor position in hex editor.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Callable


class CursorModel(QObject):
    """
    Cursor model for managing cursor position.

    Tracks cursor position and provides navigation utilities.
    """

    # Signals
    cursor_moved = pyqtSignal(int)  # new offset
    cursor_changed = pyqtSignal(int)  # different cursor position

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._offset: int = 0
        self._byte_index: int = 0  # Index within a row
        self._row: int = 0  # Row in display
        self._column: int = 0  # Column in display
        self._mode: str = "byte"  # "byte" or "ascii"

        # Bounds
        self._max_offset: int = 0
        self._bytes_per_row: int = 16

        # Navigation callbacks
        self._can_move_up: Optional[Callable[[], bool]] = None
        self._can_move_down: Optional[Callable[[], bool]] = None
        self._can_move_left: Optional[Callable[[], bool]] = None
        self._can_move_right: Optional[Callable[[], bool]] = None

    @property
    def offset(self) -> int:
        """Get current offset."""
        return self._offset

    @offset.setter
    def offset(self, value: int):
        """Set offset."""
        value = max(0, min(value, self._max_offset))
        if value != self._offset:
            self._offset = value
            self._update_position_from_offset()
            self.cursor_moved.emit(value)

    @property
    def byte_index(self) -> int:
        """Get byte index within row."""
        return self._byte_index

    @byte_index.setter
    def byte_index(self, value: int):
        """Set byte index within row."""
        value = max(0, min(value, self._bytes_per_row - 1))
        if value != self._byte_index:
            self._byte_index = value
            self._update_offset_from_position()
            self.cursor_changed.emit(self._offset)

    @property
    def row(self) -> int:
        """Get row."""
        return self._row

    @row.setter
    def row(self, value: int):
        """Set row."""
        value = max(0, value)
        if value != self._row:
            self._row = value
            self._update_offset_from_position()
            self.cursor_changed.emit(self._offset)

    @property
    def column(self) -> int:
        """Get column."""
        return self._column

    @column.setter
    def column(self, value: int):
        """Set column."""
        value = max(0, value)
        if value != self._column:
            self._column = value
            self._update_offset_from_position()
            self.cursor_changed.emit(self._offset)

    @property
    def mode(self) -> str:
        """Get cursor mode."""
        return self._mode

    @mode.setter
    def mode(self, value: str):
        """Set cursor mode ('byte' or 'ascii')."""
        if value in ("byte", "ascii"):
            self._mode = value

    @property
    def bytes_per_row(self) -> int:
        """Get bytes per row."""
        return self._bytes_per_row

    @bytes_per_row.setter
    def bytes_per_row(self, value: int):
        """Set bytes per row."""
        value = max(1, value)
        if value != self._bytes_per_row:
            self._bytes_per_row = value
            self._update_position_from_offset()

    @property
    def max_offset(self) -> int:
        """Get max offset."""
        return self._max_offset

    @max_offset.setter
    def max_offset(self, value: int):
        """Set max offset."""
        self._max_offset = max(0, value)

    def _update_position_from_offset(self):
        """Update row/column/byte_index from offset."""
        if self._bytes_per_row > 0:
            self._row = self._offset // self._bytes_per_row
            self._byte_index = self._offset % self._bytes_per_row
            self._column = self._byte_index

    def _update_offset_from_position(self):
        """Update offset from row/column/byte_index."""
        self._offset = self._row * self._bytes_per_row + self._byte_index
        if self._offset > self._max_offset:
            self._offset = self._max_offset

    def move_to(self, offset: int):
        """Move cursor to offset."""
        self.offset = offset

    def move_to_position(self, row: int, column: int):
        """Move cursor to row and column."""
        self._row = max(0, row)
        self._column = max(0, column)
        self._byte_index = min(self._column, self._bytes_per_row - 1)
        self._update_offset_from_position()
        self.cursor_changed.emit(self._offset)

    def move_up(self, rows: int = 1):
        """Move cursor up by rows."""
        if self._can_move_up and not self._can_move_up():
            return
        self.row = self._row - rows

    def move_down(self, rows: int = 1):
        """Move cursor down by rows."""
        if self._can_move_down and not self._can_move_down():
            return
        self.row = self._row + rows

    def move_left(self, bytes_count: int = 1):
        """Move cursor left by bytes."""
        if self._can_move_left and not self._can_move_left():
            return
        new_byte_index = self._byte_index - bytes_count
        if new_byte_index < 0:
            # Move to previous row
            self._row -= 1
            self._byte_index = self._bytes_per_row - 1 + new_byte_index
            self._update_offset_from_position()
        else:
            self._byte_index = new_byte_index
            self._column = self._byte_index
            self._update_offset_from_position()
        self.cursor_changed.emit(self._offset)

    def move_right(self, bytes_count: int = 1):
        """Move cursor right by bytes."""
        if self._can_move_right and not self._can_move_right():
            return
        new_byte_index = self._byte_index + bytes_count
        if new_byte_index >= self._bytes_per_row:
            # Move to next row
            self._row += 1
            self._byte_index = new_byte_index - self._bytes_per_row
            self._update_offset_from_position()
        else:
            self._byte_index = new_byte_index
            self._column = self._byte_index
            self._update_offset_from_position()
        self.cursor_changed.emit(self._offset)

    def move_to_start_of_line(self):
        """Move cursor to start of line."""
        self._byte_index = 0
        self._column = 0
        self._update_offset_from_position()
        self.cursor_changed.emit(self._offset)

    def move_to_end_of_line(self):
        """Move cursor to end of line."""
        self._byte_index = min(self._bytes_per_row - 1, self._max_offset % self._bytes_per_row)
        self._column = self._byte_index
        self._update_offset_from_position()
        self.cursor_changed.emit(self._offset)

    def move_to_start(self):
        """Move cursor to start of file."""
        self.offset = 0

    def move_to_end(self):
        """Move cursor to end of file."""
        self.offset = self._max_offset

    def page_up(self, page_size: int = 16):
        """Move cursor up by page."""
        self.row = self._row - page_size

    def page_down(self, page_size: int = 16):
        """Move cursor down by page."""
        self.row = self._row + page_size

    def set_navigation_callbacks(self, up: Callable[[], bool], down: Callable[[], bool],
                                  left: Callable[[], bool], right: Callable[[], bool]):
        """
        Set navigation callback functions.

        Args:
            up: Callback for can move up
            down: Callback for can move down
            left: Callback for can move left
            right: Callback for can move right
        """
        self._can_move_up = up
        self._can_move_down = down
        self._can_move_left = left
        self._can_move_right = right

    def clear_navigation_callbacks(self):
        """Clear navigation callbacks."""
        self._can_move_up = None
        self._can_move_down = None
        self._can_move_left = None
        self._can_move_right = None

    def copy(self) -> 'CursorModel':
        """Create a copy of this cursor."""
        copy = CursorModel()
        copy._offset = self._offset
        copy._byte_index = self._byte_index
        copy._row = self._row
        copy._column = self._column
        copy._mode = self._mode
        copy._max_offset = self._max_offset
        copy._bytes_per_row = self._bytes_per_row
        return copy

    def serialize(self) -> dict:
        """Serialize cursor state."""
        return {
            "offset": self._offset,
            "row": self._row,
            "column": self._column,
            "mode": self._mode,
        }

    def deserialize(self, data: dict):
        """Deserialize cursor state."""
        self._offset = data.get("offset", 0)
        self._row = data.get("row", 0)
        self._column = data.get("column", 0)
        self._mode = data.get("mode", "byte")
        self._update_position_from_offset()
