"""
AI Manager

Manages AI providers and provides a unified interface for AI operations.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any, List

from .base import AIBase, AISettings, AIProvider
from .local import LocalAI
from .cloud import CloudAI
from .analyzer import AIAnalyzer
from .coder import CodeGenerator
from .search import AISearch


class AIManager(QObject):
    """
    AI Manager.

    Manages AI providers and provides unified interface.
    """

    # Signals
    status_changed = pyqtSignal(str)
    response_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # AI instances
        self._local_ai: Optional[LocalAI] = None
        self._cloud_ai: Optional[CloudAI] = None

        # Current provider
        self._current_ai: Optional[AIBase] = None
        self._current_provider = AIProvider.LOCAL

        # AI features
        self._analyzer = AIAnalyzer(self)
        self._coder = CodeGenerator(self)
        self._search = AISearch(self)

        # Settings
        self._settings = AISettings()

        # Initialize providers
        self._init_providers()

    def _init_providers(self):
        """Initialize AI providers."""
        self._local_ai = LocalAI()
        self._cloud_ai = CloudAI()

        # Default to local
        self._current_ai = self._local_ai
        self._current_provider = AIProvider.LOCAL

    def configure(self, settings: Dict[str, Any]):
        """
        Configure AI manager.

        Args:
            settings: Settings dictionary
        """
        self._settings.enabled = settings.get('enabled', True)

        # Configure provider
        provider = settings.get('provider', 'local')
        if provider == 'local':
            self._use_local()
            local_settings = settings.get('local', {})
            if self._local_ai:
                self._local_ai.configure(
                    endpoint=local_settings.get('endpoint', 'http://localhost:11434'),
                    model=local_settings.get('model', 'qwen:7b'),
                    temperature=local_settings.get('temperature', 0.7),
                    max_tokens=local_settings.get('max_tokens', 4096),
                    timeout=local_settings.get('timeout', 60),
                )
        elif provider == 'openai':
            self._use_cloud()
            cloud_settings = settings.get('cloud', {})
            if self._cloud_ai:
                self._cloud_ai.configure(
                    provider='openai',
                    api_key=cloud_settings.get('api_key', ''),
                    base_url=cloud_settings.get('base_url', 'https://api.openai.com/v1'),
                    model=cloud_settings.get('model', 'gpt-4o'),
                    temperature=cloud_settings.get('temperature', 0.7),
                    max_tokens=cloud_settings.get('max_tokens', 4096),
                )
        elif provider == 'anthropic':
            self._use_cloud()
            cloud_settings = settings.get('cloud', {})
            if self._cloud_ai:
                self._cloud_ai.configure(
                    provider='anthropic',
                    api_key=cloud_settings.get('api_key', ''),
                    base_url=cloud_settings.get('base_url', 'https://api.anthropic.com'),
                    model=cloud_settings.get('model', 'claude-sonnet-4-20250514'),
                    temperature=cloud_settings.get('temperature', 0.7),
                    max_tokens=cloud_settings.get('max_tokens', 4096),
                )

    def _use_local(self):
        """Switch to local provider."""
        self._current_ai = self._local_ai
        self._current_provider = AIProvider.LOCAL
        self.status_changed.emit("Local (Ollama)")

    def _use_cloud(self):
        """Switch to cloud provider."""
        self._current_ai = self._cloud_ai
        self._current_provider = AIProvider.CLOUD_OPENAI
        self.status_changed.emit("Cloud API")

    @property
    def is_available(self) -> bool:
        """Check if current provider is available."""
        if not self._settings.enabled:
            return False
        if self._current_ai:
            return self._current_ai.is_available
        return False

    @property
    def current_provider(self) -> AIProvider:
        """Get current provider."""
        return self._current_provider

    def check_connection(self) -> bool:
        """Check connection to current provider."""
        if self._current_ai:
            return self._current_ai.check_availability()
        return False

    def analyze(self, data: bytes, context: str = "") -> str:
        """
        Analyze binary data.

        Args:
            data: Binary data to analyze
            context: Additional context

        Returns:
            Analysis result
        """
        if not self._settings.enabled:
            return "AI features are disabled"

        if not self._current_ai:
            return "No AI provider configured"

        return self._current_ai.analyze(data, context)

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
        if not self._settings.enabled:
            return "AI features are disabled"

        if not self._current_ai:
            return "No AI provider configured"

        return self._current_ai.explain(data, offset, length)

    def generate_code(self, structure: Dict[str, Any], language: str = "c") -> str:
        """
        Generate parsing code.

        Args:
            structure: Data structure description
            language: Target language

        Returns:
            Generated code
        """
        if not self._settings.enabled:
            return "AI features are disabled"

        if not self._current_ai:
            return "No AI provider configured"

        return self._current_ai.generate_code(structure, language)

    def detect_patterns(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Detect patterns in data.

        Args:
            data: Binary data

        Returns:
            List of detected patterns
        """
        return self._analyzer.analyze(data)

    def chat(self, message: str, history: List[Dict[str, str]] = None) -> str:
        """
        Chat with AI.

        Args:
            message: User message
            history: Chat history

        Returns:
            AI response
        """
        if not self._settings.enabled:
            return "AI features are disabled"

        if not self._current_ai:
            return "No AI provider configured"

        return self._current_ai.chat(message, history)

    def cancel(self):
        """Cancel ongoing operation."""
        if self._current_ai:
            self._current_ai.cancel()
