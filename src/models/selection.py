"""
Selection Model

Manages byte range selection in hex editor.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List, Tuple, Dict


class SelectionModel(QObject):
    """
    Selection model for managing byte range selections.

    Supports multiple selection ranges and provides utilities
    for working with selections.
    """

    # Signals
    selection_changed = pyqtSignal()  # Selection changed
    selection_cleared = pyqtSignal()  # Selection cleared
    selection_added = pyqtSignal(int, int)  # start, end of new selection

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._selections: List[Tuple[int, int]] = []  # List of (start, end) ranges
        self._anchor: int = -1  # Anchor position for shift-click selection
        self._caret: int = -1  # Caret position (end of selection)

    @property
    def selections(self) -> List[Tuple[int, int]]:
        """Get all selections."""
        return self._selections.copy()

    @property
    def anchor(self) -> int:
        """Get anchor position."""
        return self._anchor

    @property
    def caret(self) -> int:
        """Get caret position."""
        return self._caret

    @property
    def has_selection(self) -> bool:
        """Check if any selection exists."""
        return len(self._selections) > 0

    @property
    def selection_count(self) -> int:
        """Get number of selections."""
        return len(self._selections)

    @property
    def primary_selection(self) -> Optional[Tuple[int, int]]:
        """Get primary (first) selection."""
        if self._selections:
            return self._selections[0]
        return None

    @property
    def start_offset(self) -> int:
        """Get start offset of primary selection."""
        sel = self.primary_selection
        if sel:
            return min(sel[0], sel[1])
        return -1

    @property
    def end_offset(self) -> int:
        """Get end offset of primary selection."""
        sel = self.primary_selection
        if sel:
            return max(sel[0], sel[1])
        return -1

    @property
    def length(self) -> int:
        """Get length of primary selection."""
        sel = self.primary_selection
        if sel:
            return abs(sel[1] - sel[0]) + 1
        return 0

    @property
    def is_empty(self) -> bool:
        """Check if selection is empty (single cursor position)."""
        return not self._selections or (
            len(self._selections) == 1 and
            self._selections[0][0] == self._selections[0][1]
        )

    def clear(self):
        """Clear all selections."""
        if self._selections:
            self._selections.clear()
            self._anchor = -1
            self._caret = -1
            self.selection_cleared.emit()

    def select(self, start: int, end: int):
        """
        Set selection range.

        Args:
            start: Start offset
            end: End offset
        """
        # Normalize (start <= end)
        start, end = (start, end) if start <= end else (end, start)

        # Check if same as current
        if (len(self._selections) == 1 and
            self._selections[0][0] == start and
            self._selections[0][1] == end):
            return

        self._selections = [(start, end)]
        self._anchor = start
        self._caret = end
        self.selection_changed.emit()

    def select_single(self, offset: int):
        """
        Set single cursor position (no selection).

        Args:
            offset: Cursor offset
        """
        self._selections = [(offset, offset)]
        self._anchor = offset
        self._caret = offset
        self.selection_changed.emit()

    def set_anchor(self, offset: int):
        """
        Set anchor position for shift-click selection.

        Args:
            offset: Anchor offset
        """
        self._anchor = offset
        # Update selection to extend from anchor to caret
        if self._anchor != self._caret:
            self.select(self._anchor, self._caret)

    def extend_to(self, offset: int):
        """
        Extend selection to offset.

        Args:
            offset: New offset
        """
        self._caret = offset
        if self._anchor >= 0:
            self.select(self._anchor, offset)

    def add_selection(self, start: int, end: int):
        """
        Add additional selection range.

        Args:
            start: Start offset
            end: End offset
        """
        start, end = (start, end) if start <= end else (end, start)
        self._selections.append((start, end))
        self._anchor = start
        self._caret = end
        self.selection_added.emit(start, end)
        self.selection_changed.emit()

    def remove_selection(self, index: int) -> bool:
        """
        Remove selection at index.

        Args:
            index: Selection index

        Returns:
            True if removed
        """
        if 0 <= index < len(self._selections):
            self._selections.pop(index)
            self.selection_changed.emit()
            return True
        return False

    def contains(self, offset: int) -> bool:
        """
        Check if offset is within any selection.

        Args:
            offset: Offset to check

        Returns:
            True if offset is selected
        """
        for start, end in self._selections:
            if start <= offset <= end:
                return True
        return False

    def get_selection_at(self, offset: int) -> Optional[Tuple[int, int]]:
        """
        Get selection containing offset.

        Args:
            offset: Offset to check

        Returns:
            Selection range or None
        """
        for start, end in self._selections:
            if start <= offset <= end:
                return (start, end)
        return None

    def get_selection_index(self, offset: int) -> int:
        """
        Get index of selection containing offset.

        Args:
            offset: Offset to check

        Returns:
            Selection index or -1
        """
        for i, (start, end) in enumerate(self._selections):
            if start <= offset <= end:
                return i
        return -1

    def select_all(self, size: int):
        """
        Select all bytes.

        Args:
            size: Total size
        """
        self.select(0, size - 1)

    def select_none(self):
        """Clear selection to single cursor."""
        if self._caret >= 0:
            self.select_single(self._caret)

    def invert(self, size: int):
        """
        Invert selection.

        Args:
            size: Total size
        """
        new_selections = []
        current_start = 0

        for start, end in self._selections:
            if current_start < start:
                new_selections.append((current_start, start - 1))
            current_start = end + 1

        if current_start <= size - 1:
            new_selections.append((current_start, size - 1))

        self._selections = new_selections
        if self._selections:
            self._anchor = self._selections[0][0]
            self._caret = self._selections[-1][1]
        else:
            self._anchor = -1
            self._caret = -1

        self.selection_changed.emit()

    def expand_word(self, offset: int, delimiters: bytes = b' \t\n\r\x00') -> Tuple[int, int]:
        """
        Expand selection to word at offset.

        Args:
            offset: Offset within word
            delimiters: Word delimiters

        Returns:
            (start, end) of word
        """
        # This would need access to file data
        # Return current selection if no data access
        if self._selections:
            return self._selections[0]
        return (offset, offset)

    def expand_line(self, offset: int, line_starts: List[int], line_ends: List[int]) -> Tuple[int, int]:
        """
        Expand selection to line at offset.

        Args:
            offset: Offset within line
            line_starts: List of line start offsets
            line_ends: List of line end offsets

        Returns:
            (start, end) of line
        """
        # This would need access to file data
        if self._selections:
            return self._selections[0]
        return (offset, offset)

    def serialize(self) -> List[Dict[str, int]]:
        """Serialize selections to JSON-compatible format."""
        return [{"start": s, "end": e} for s, e in self._selections]

    def deserialize(self, data: List[Dict[str, int]]):
        """Deserialize selections from JSON-compatible format."""
        self._selections = [(d["start"], d["end"]) for d in data]
        if self._selections:
            self._anchor = self._selections[0][0]
            self._caret = self._selections[-1][1]
        self.selection_changed.emit()
