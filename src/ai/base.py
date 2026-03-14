"""
AI Base

Base class and settings for AI integration.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any, List
from enum import Enum, auto
from dataclasses import dataclass, field

from .agent import ProviderCapabilities


class AIProvider(Enum):
    """AI provider enumeration."""
    LOCAL = auto()
    CLOUD_OPENAI = auto()
    CLOUD_ANTHROPIC = auto()
    CLOUD_MINIMAX = auto()
    CLOUD_GLM = auto()


@dataclass
class AISettings:
    """AI settings container."""
    provider: AIProvider = AIProvider.LOCAL
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    local_endpoint: str = "http://localhost:11434"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    system_prompt: str = ""
    enabled: bool = True


class AIBase(QObject):
    """
    Base class for AI providers.

    Defines the interface for AI interactions.
    """

    # Signals
    response_ready = pyqtSignal(str)  # AI response
    response_chunk = pyqtSignal(str)  # Streaming response
    error_occurred = pyqtSignal(str)
    thinking_started = pyqtSignal()
    thinking_finished = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._settings = AISettings()
        self._is_available = False

    @property
    def settings(self) -> AISettings:
        """Get AI settings."""
        return self._settings

    @settings.setter
    def settings(self, value: AISettings):
        """Set AI settings."""
        self._settings = value

    @property
    def is_available(self) -> bool:
        """Check if AI provider is available."""
        return self._is_available

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        raise NotImplementedError

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capability flags."""
        return ProviderCapabilities()

    def configure(self, **kwargs):
        """
        Configure AI settings.

        Args:
            **kwargs: Settings to update
        """
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)

    def check_availability(self) -> bool:
        """
        Check if provider is available.

        Returns:
            True if available
        """
        raise NotImplementedError

    def analyze(self, data: bytes, context: str = "") -> str:
        """
        Analyze binary data.

        Args:
            data: Binary data to analyze
            context: Additional context

        Returns:
            Analysis result
        """
        raise NotImplementedError

    def explain(self, data: bytes, offset: int = 0, length: int = 0) -> str:
        """
        Explain data at offset.

        Args:
            data: Binary data
            offset: Start offset
            length: Data length

        Returns:
            Explanation
        """
        raise NotImplementedError

    def generate_code(self, structure: Dict[str, Any], language: str = "c") -> str:
        """
        Generate parsing code.

        Args:
            structure: Data structure description
            language: Target language

        Returns:
            Generated code
        """
        raise NotImplementedError

    def search_natural_language(self, query: str, data: bytes) -> List[Dict[str, Any]]:
        """
        Natural language search.

        Args:
            query: Search query
            data: Data to search

        Returns:
            Search results
        """
        raise NotImplementedError

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """
        Complete a chat-style list of messages.

        Args:
            messages: Chat messages in role/content form

        Returns:
            Model response text
        """
        raise NotImplementedError

    def complete_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Optionally use provider-native tool calling."""
        return None

    def chat(self, message: str, history: List[Dict[str, str]] = None) -> str:
        """
        Chat with AI.

        Args:
            message: User message
            history: Chat history

        Returns:
            AI response
        """
        raise NotImplementedError

    def cancel(self):
        """Cancel ongoing operation."""
        pass

    def reset(self):
        """Reset AI state."""
        self._is_available = False

    def _format_data_for_ai(self, data: bytes, max_bytes: int = 1024) -> str:
        """Format data for AI consumption."""
        data = data[:max_bytes]
        hex_str = ' '.join(f'{b:02x}' for b in data)
        ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        return f"Hex: {hex_str}\nASCII: {ascii_repr}"

    def _truncate_response(self, response: str, max_length: int = 8192) -> str:
        """Truncate response if too long."""
        if len(response) <= max_length:
            return response
        return response[:max_length] + "\n... (truncated)"
