"""
Undo Stack

Implements undo/redo functionality for hex editing.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List, Any, Callable
from enum import Enum, auto


class UndoCommand:
    """Base class for undo commands."""

    def __init__(self, description: str = ""):
        self._description = description
        self._merged: bool = False

    @property
    def description(self) -> str:
        """Get command description."""
        return self._description

    def undo(self):
        """Perform undo."""
        raise NotImplementedError

    def redo(self):
        """Perform redo."""
        raise NotImplementedError

    def merge(self, other: 'UndoCommand') -> bool:
        """
        Try to merge with another command.

        Args:
            other: Another command to merge

        Returns:
            True if merged
        """
        return False

    def __repr__(self):
        return f"UndoCommand({self._description})"


class ReplaceCommand(UndoCommand):
    """Command for replacing bytes."""

    def __init__(self, offset: int, old_data: bytes, new_data: bytes):
        super().__init__(f"Replace {len(old_data)} bytes at offset {offset}")
        self._offset = offset
        self._old_data = old_data
        self._new_data = new_data

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def old_data(self) -> bytes:
        return self._old_data

    @property
    def new_data(self) -> bytes:
        return self._new_data

    def undo(self):
        """Undo the replace."""
        return ("replace", self._offset, self._old_data)

    def redo(self):
        """Redo the replace."""
        return ("replace", self._offset, self._new_data)

    def merge(self, other: 'ReplaceCommand') -> bool:
        """Merge with another replace command."""
        if isinstance(other, ReplaceCommand):
            # Check if adjacent or overlapping
            other_end = other._offset + len(other._new_data)
            self_end = self._offset + len(self._new_data)

            if other._offset == self_end or other_end == self._offset:
                # Adjacent - can merge
                if other._offset == self_end:
                    # other is after self
                    self._new_data = self._new_data + other._new_data
                else:
                    # other is before self
                    self._new_data = other._new_data + self._new_data
                    self._offset = other._offset
                self._description = f"Replace {len(self._new_data)} bytes at offset {self._offset}"
                return True
        return False


class InsertCommand(UndoCommand):
    """Command for inserting bytes."""

    def __init__(self, offset: int, data: bytes):
        super().__init__(f"Insert {len(data)} bytes at offset {offset}")
        self._offset = offset
        self._data = data

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def data(self) -> bytes:
        return self._data

    def undo(self):
        """Undo the insert."""
        return ("delete", self._offset, len(self._data))

    def redo(self):
        """Redo the insert."""
        return ("insert", self._offset, self._data)

    def merge(self, other: 'InsertCommand') -> bool:
        """Merge with another insert command."""
        if isinstance(other, InsertCommand):
            # Check if adjacent
            if other._offset == self._offset + len(self._data):
                # other is after self
                self._data = self._data + other._data
                self._description = f"Insert {len(self._data)} bytes at offset {self._offset}"
                return True
        return False


class DeleteCommand(UndoCommand):
    """Command for deleting bytes."""

    def __init__(self, offset: int, length: int, deleted_data: bytes):
        super().__init__(f"Delete {length} bytes at offset {offset}")
        self._offset = offset
        self._length = length
        self._deleted_data = deleted_data

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def length(self) -> int:
        return self._length

    @property
    def deleted_data(self) -> bytes:
        return self._deleted_data

    def undo(self):
        """Undo the delete."""
        return ("insert", self._offset, self._deleted_data)

    def redo(self):
        """Redo the delete."""
        return ("delete", self._offset, self._length)


class FillCommand(UndoCommand):
    """Command for filling bytes."""

    def __init__(self, offset: int, old_data: bytes, fill_pattern: bytes):
        super().__init__(f"Fill {len(old_data)} bytes at offset {offset}")
        self._offset = offset
        self._old_data = old_data
        self._fill_pattern = fill_pattern

    def undo(self):
        """Undo the fill."""
        return ("replace", self._offset, self._old_data)

    def redo(self):
        """Redo the fill."""
        return ("fill", self._offset, self._fill_pattern, len(self._old_data))


class UndoStack(QObject):
    """
    Undo stack for managing undo/redo operations.

    Implements a command pattern for tracking changes.
    """

    # Signals
    can_undo_changed = pyqtSignal(bool)
    can_redo_changed = pyqtSignal(bool)
    undo_description_changed = pyqtSignal(str)
    redo_description_changed = pyqtSignal(str)
    stack_changed = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None, max_size: int = 100):
        super().__init__(parent)
        self._undo_stack: List[UndoCommand] = []
        self._redo_stack: List[UndoCommand] = []
        self._max_size = max_size
        self._index = 0

    @property
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str:
        """Get description of next undo."""
        if self.can_undo:
            return self._undo_stack[self._index - 1].description
        return ""

    @property
    def redo_description(self) -> str:
        """Get description of next redo."""
        if self.can_redo:
            return self._redo_stack[-1].description
        return ""

    @property
    def undo_count(self) -> int:
        """Get number of undoable operations."""
        return self._index

    @property
    def redo_count(self) -> int:
        """Get number of redoable operations."""
        return len(self._redo_stack)

    @property
    def is_clean(self) -> bool:
        """Check if stack is at clean state."""
        return self._index == 0 and len(self._redo_stack) == 0

    def push(self, command: UndoCommand):
        """
        Push a command onto the stack.

        Args:
            command: Command to push
        """
        # Try to merge with previous command
        if self._index > 0 and self._undo_stack:
            last_command = self._undo_stack[self._index - 1]
            if last_command.merge(command):
                self._emit_changes()
                return

        # Clear redo stack
        self._redo_stack = self._redo_stack[:self._index]

        # Add new command
        self._undo_stack.append(command)
        self._index += 1

        # Limit stack size
        while len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)
            self._index -= 1

        self._emit_changes()

    def undo(self) -> Optional[UndoCommand]:
        """
        Undo the last command.

        Returns:
            The undone command, or None if nothing to undo
        """
        if not self.can_undo:
            return None

        self._index -= 1
        command = self._undo_stack[self._index]
        self._redo_stack.append(command)

        self._emit_changes()
        return command

    def redo(self) -> Optional[UndoCommand]:
        """
        Redo the last undone command.

        Returns:
            The redone command, or None if nothing to redo
        """
        if not self.can_redo:
            return None

        command = self._redo_stack.pop()
        self._undo_stack.append(command)
        self._index += 1

        self._emit_changes()
        return command

    def undo_n(self, count: int) -> List[UndoCommand]:
        """
        Undo multiple commands.

        Args:
            count: Number of commands to undo

        Returns:
            List of undone commands
        """
        commands = []
        for _ in range(count):
            cmd = self.undo()
            if cmd:
                commands.append(cmd)
            else:
                break
        return commands

    def redo_n(self, count: int) -> List[UndoCommand]:
        """
        Redo multiple commands.

        Args:
            count: Number of commands to redo

        Returns:
            List of redone commands
        """
        commands = []
        for _ in range(count):
            cmd = self.redo()
            if cmd:
                commands.append(cmd)
            else:
                break
        return commands

    def clear(self):
        """Clear the stack."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._index = 0
        self._emit_changes()

    def set_clean(self):
        """
        Mark the current state as clean.

        All subsequent undos will be relative to this state.
        """
        # Trim stack to current index
        self._undo_stack = self._undo_stack[:self._index]
        self._redo_stack.clear()
        self._emit_changes()

    def snapshot(self) -> int:
        """
        Get current state index for later comparison.

        Returns:
            Current index
        """
        return self._index

    def is_clean_at(self, index: int) -> bool:
        """
        Check if stack is clean at index.

        Args:
            index: Index to check

        Returns:
            True if clean at index
        """
        return index == 0 and len(self._redo_stack) == 0

    def _emit_changes(self):
        """Emit change signals."""
        self.can_undo_changed.emit(self.can_undo)
        self.can_redo_changed.emit(self.can_redo)
        self.undo_description_changed.emit(self.undo_description)
        self.redo_description_changed.emit(self.redo_description)
        self.stack_changed.emit()

    def get_commands(self) -> List[UndoCommand]:
        """Get all commands in stack (for debugging)."""
        return self._undo_stack.copy()
