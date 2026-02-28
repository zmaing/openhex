"""
Test Search Engine

Tests for search functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.search_engine import SearchEngine, SearchMode, SearchResult


def test_search_hex():
    """Test hex search."""
    engine = SearchEngine()
    data = b'\x48\x65\x6c\x6c\x6f\x20\x57\x6f\x72\x6c\x64'
    engine.set_data(data)

    # Search for "48 65 6C" - hex mode expects a hex string pattern
    result = engine.search('48656c', SearchMode.HEX)

    assert result is not None
    assert result.offset == 0
    assert result.length == 3

    print("✓ test_search_hex passed")


def test_search_text():
    """Test text search."""
    engine = SearchEngine()
    data = b'Hello World'
    engine.set_data(data)

    # Search for "World"
    result = engine.search('World', SearchMode.TEXT)

    assert result is not None
    assert result.offset == 6
    assert result.length == 5

    print("✓ test_search_text passed")


def test_search_regex():
    """Test regex search."""
    engine = SearchEngine()
    data = b'123-456-7890'
    engine.set_data(data)

    # Search for pattern
    result = engine.search(r'\d{3}-\d{3}-\d{4}', SearchMode.REGEX)

    assert result is not None
    assert result.offset == 0

    print("✓ test_search_regex passed")


def test_search_not_found():
    """Test search when pattern not found."""
    engine = SearchEngine()
    data = b'Hello World'
    engine.set_data(data)

    result = engine.search('xyz', SearchMode.TEXT)

    assert result is None

    print("✓ test_search_not_found passed")


def test_search_all():
    """Test search all results."""
    engine = SearchEngine()
    data = b'Hello World Hello World Hello'
    engine.set_data(data)

    # Search all occurrences of "Hello"
    results = engine.search_all('Hello', SearchMode.TEXT)

    assert len(results) == 3
    assert results[0].offset == 0
    assert results[1].offset == 12
    assert results[2].offset == 24

    print("✓ test_search_all passed")


def test_search_backward():
    """Test backward search."""
    from src.core.search_engine import SearchDirection
    engine = SearchEngine()
    data = b'Hello World'
    engine.set_data(data)

    # Search backward from end
    result = engine.search('World', SearchMode.TEXT, SearchDirection.BACKWARD)

    assert result is not None
    assert result.offset == 6

    print("✓ test_search_backward passed")


def test_search_result_equality():
    """Test search result equality."""
    r1 = SearchResult(100, 5, "test")
    r2 = SearchResult(100, 5, "test")
    r3 = SearchResult(200, 5, "test")

    assert r1 == r2
    assert r1 != r3

    print("✓ test_search_result_equality passed")


def run_all_tests():
    """Run all tests."""
    print("Running SearchEngine tests...")
    test_search_hex()
    test_search_text()
    test_search_regex()
    test_search_not_found()
    test_search_all()
    test_search_backward()
    test_search_result_equality()
    print("\nAll SearchEngine tests passed!")


if __name__ == "__main__":
    run_all_tests()
