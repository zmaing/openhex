"""
Jump History

跳转历史记录
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class JumpEntry:
    """Jump history entry."""
    offset: int
    description: str = ""


class JumpHistory(QObject):
    """
    Jump history manager.

    Tracks navigation history for back/forward functionality.
    """

    # Signals
    history_changed = pyqtSignal()

    def __init__(self, parent=None, max_size: int = 100):
        super().__init__(parent)
        self._history: List[JumpEntry] = []
        self._current_index: int = -1
        self._max_size = max_size

    @property
    def can_go_back(self) -> bool:
        """Check if can go back."""
        return self._current_index > 0

    @property
    def can_go_forward(self) -> bool:
        """Check if can go forward."""
        return self._current_index < len(self._history) - 1

    @property
    def current_offset(self) -> Optional[int]:
        """Get current offset."""
        if 0 <= self._current_index < len(self._history):
            return self._history[self._current_index].offset
        return None

    def push(self, offset: int, description: str = ""):
        """
        Add new jump to history.

        Args:
            offset: Jump offset
            description: Description of jump
        """
        # Clear forward history if we're not at the end
        if self._current_index < len(self._history) - 1:
            self._history = self._history[:self._current_index + 1]

        # Add new entry
        entry = JumpEntry(offset, description)
        self._history.append(entry)

        # Move to new position
        self._current_index = len(self._history) - 1

        # Limit history size
        while len(self._history) > self._max_size:
            self._history.pop(0)
            self._current_index -= 1

        self.history_changed.emit()

    def go_back(self) -> Optional[int]:
        """
        Go back in history.

        Returns:
            Offset to jump to, or None
        """
        if not self.can_go_back:
            return None

        self._current_index -= 1
        self.history_changed.emit()
        return self.current_offset

    def go_forward(self) -> Optional[int]:
        """
        Go forward in history.

        Returns:
            Offset to jump to, or None
        """
        if not self.can_go_forward:
            return None

        self._current_index += 1
        self.history_changed.emit()
        return self.current_offset

    def clear(self):
        """Clear history."""
        self._history.clear()
        self._current_index = -1
        self.history_changed.emit()

    def get_history(self) -> List[JumpEntry]:
        """Get full history."""
        return self._history.copy()
