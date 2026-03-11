"""
Regression tests for the local AI provider.
"""

from src.ai.local import LocalAI


def test_local_ai_initializes_response_buffer():
    """The local provider should always initialize its response buffer."""
    provider = LocalAI()

    assert provider._last_response == ""


def test_local_ai_error_updates_response_buffer():
    """Local provider errors should be reflected in the response buffer for agent mode."""
    provider = LocalAI()

    provider._handle_error("boom")

    assert provider._last_response == "Error: boom"

    provider._last_response = "old"
    provider.reset()

    assert provider._last_response == ""
