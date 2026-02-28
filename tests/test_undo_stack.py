"""
Test Undo Stack

Tests for undo/redo functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.undo_stack import UndoStack, ReplaceCommand, InsertCommand, DeleteCommand


def test_undo_stack_basic():
    """Test basic undo/redo operations."""
    stack = UndoStack(max_size=10)

    # Initially no undo/redo
    assert not stack.can_undo
    assert not stack.can_redo

    # Push a command
    cmd = ReplaceCommand(0, b'\x00\x01\x02', b'\x03\x04\x05')
    stack.push(cmd)

    # Now we can undo
    assert stack.can_undo
    assert not stack.can_redo

    print("✓ test_undo_stack_basic passed")


def test_undo_stack_undo_redo():
    """Test undo and redo."""
    stack = UndoStack()

    # Push commands at different offsets (not adjacent to avoid merging)
    cmd1 = ReplaceCommand(0, b'\x00', b'\x01')
    cmd2 = ReplaceCommand(10, b'\x00', b'\x02')  # Offset 10, not adjacent to 0
    stack.push(cmd1)
    stack.push(cmd2)

    # Verify commands pushed
    assert stack.can_undo
    assert stack.undo_count == 2

    # Undo
    undone = stack.undo()
    assert undone is not None
    assert stack.can_redo
    assert stack.undo_count == 1

    # Redo
    redone = stack.redo()
    assert redone is not None
    assert stack.can_undo
    assert stack.redo_count == 0

    print("✓ test_undo_stack_undo_redo passed")


def test_undo_stack_merge():
    """Test command merging."""
    stack = UndoStack()

    # Push adjacent commands (cmd1 ends at offset 3, cmd2 starts at 3)
    cmd1 = ReplaceCommand(0, b'\x00\x00\x00', b'\x01\x02\x03')  # length 3
    cmd2 = ReplaceCommand(3, b'\x00', b'\x04')  # starts at 3

    stack.push(cmd1)
    stack.push(cmd2)

    # Should be merged
    assert stack.undo_count == 1

    print("✓ test_undo_stack_merge passed")


def test_undo_stack_limit():
    """Test stack size limit."""
    stack = UndoStack(max_size=3)

    # Push more commands than limit (use large offsets to avoid merging)
    for i in range(5):
        cmd = ReplaceCommand(i * 100, b'\x00', bytes([i]))  # Offset 0, 100, 200, 300, 400
        stack.push(cmd)

    # Should be limited to max_size or less (after merging checks)
    assert stack.undo_count <= 3

    print("✓ test_undo_stack_limit passed")


def test_replace_command():
    """Test replace command."""
    cmd = ReplaceCommand(0, b'\x00\x01\x02', b'\x03\x04\x05')

    # Undo should return original data
    undo_action = cmd.undo()
    assert undo_action[0] == "replace"
    assert undo_action[1] == 0
    assert undo_action[2] == b'\x00\x01\x02'

    # Redo should return new data
    redo_action = cmd.redo()
    assert redo_action[0] == "replace"
    assert redo_action[1] == 0
    assert redo_action[2] == b'\x03\x04\x05'

    print("✓ test_replace_command passed")


def test_insert_command():
    """Test insert command."""
    cmd = InsertCommand(10, b'\x01\x02\x03')

    # Undo should delete
    undo_action = cmd.undo()
    assert undo_action[0] == "delete"
    assert undo_action[1] == 10

    # Redo should insert
    redo_action = cmd.redo()
    assert redo_action[0] == "insert"
    assert redo_action[1] == 10
    assert redo_action[2] == b'\x01\x02\x03'

    print("✓ test_insert_command passed")


def test_delete_command():
    """Test delete command."""
    cmd = DeleteCommand(10, 5, b'\x01\x02\x03\x04\x05')

    # Undo should insert
    undo_action = cmd.undo()
    assert undo_action[0] == "insert"
    assert undo_action[1] == 10

    # Redo should delete
    redo_action = cmd.redo()
    assert redo_action[0] == "delete"
    assert redo_action[1] == 10

    print("✓ test_delete_command passed")


def run_all_tests():
    """Run all tests."""
    print("Running UndoStack tests...")
    test_undo_stack_basic()
    test_undo_stack_undo_redo()
    test_undo_stack_merge()
    test_undo_stack_limit()
    test_replace_command()
    test_insert_command()
    test_delete_command()
    print("\nAll UndoStack tests passed!")


if __name__ == "__main__":
    run_all_tests()
