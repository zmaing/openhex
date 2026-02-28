"""
Test Jump History

Tests for navigation history functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.jump_history import JumpHistory, JumpEntry


def test_jump_history_basic():
    """Test basic jump history."""
    history = JumpHistory(max_size=10)

    # Initially empty
    assert not history.can_go_back
    assert not history.can_go_forward

    print("✓ test_jump_history_basic passed")


def test_jump_history_push():
    """Test pushing jumps."""
    history = JumpHistory()

    # Push some jumps
    history.push(100, "Jump 1")
    history.push(200, "Jump 2")
    history.push(300, "Jump 3")

    # Should be at position 3
    assert history.current_offset == 300
    assert history.can_go_back
    assert not history.can_go_forward

    print("✓ test_jump_history_push passed")


def test_jump_history_go_back():
    """Test going back."""
    history = JumpHistory()
    history.push(100)
    history.push(200)
    history.push(300)

    # Go back
    offset = history.go_back()
    assert offset == 200
    assert history.can_go_back
    assert history.can_go_forward

    offset = history.go_back()
    assert offset == 100
    assert not history.can_go_back

    print("✓ test_jump_history_go_back passed")


def test_jump_history_go_forward():
    """Test going forward."""
    history = JumpHistory()
    history.push(100)
    history.push(200)
    history.push(300)

    # Go back then forward
    history.go_back()
    history.go_back()

    offset = history.go_forward()
    assert offset == 200

    offset = history.go_forward()
    assert offset == 300
    assert not history.can_go_forward

    print("✓ test_jump_history_go_forward passed")


def test_jump_history_clear():
    """Test clearing history."""
    history = JumpHistory()
    history.push(100)
    history.push(200)

    history.clear()

    assert not history.can_go_back
    assert not history.can_go_forward

    print("✓ test_jump_history_clear passed")


def test_jump_history_limit():
    """Test history size limit."""
    history = JumpHistory(max_size=3)

    # Push more than limit
    for i in range(5):
        history.push(i * 100)

    # Should be limited
    assert history.can_go_back

    print("✓ test_jump_history_limit passed")


def run_all_tests():
    """Run all tests."""
    print("Running JumpHistory tests...")
    test_jump_history_basic()
    test_jump_history_push()
    test_jump_history_go_back()
    test_jump_history_go_forward()
    test_jump_history_clear()
    test_jump_history_limit()
    print("\nAll JumpHistory tests passed!")


if __name__ == "__main__":
    run_all_tests()
