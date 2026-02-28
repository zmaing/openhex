"""
Local AI

Local LLM integration using Ollama or similar.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from typing import Optional, Dict, Any, List
import json
import httpx

from .base import AIBase, AISettings, AIProvider


class LocalAIWorker(QThread):
    """Worker for local AI requests."""

    response = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, endpoint: str, prompt: str, settings: AISettings):
        super().__init__()
        self._endpoint = endpoint
        self._prompt = prompt
        self._settings = settings
        self._should_stop = False

    def run(self):
        """Run AI request."""
        try:
            url = f"{self._endpoint}/api/generate"

            payload = {
                "model": self._settings.model or "qwen:7b",
                "prompt": self._prompt,
                "stream": False,
                "options": {
                    "temperature": self._settings.temperature,
                    "num_predict": self._settings.max_tokens,
                }
            }

            with httpx.Client(timeout=self._settings.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                result = data.get("response", "")
                self.response.emit(result)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

    def stop(self):
        """Signal worker to stop."""
        self._should_stop = True


class LocalAI(AIBase):
    """
    Local LLM provider using Ollama or compatible APIs.

    Supports Ollama, LM Studio, and LocalAI.
    """

    # Signals
    availability_checked = pyqtSignal(bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._worker: Optional[LocalAIWorker] = None
        self._endpoint = "http://localhost:11434"

    @property
    def provider_name(self) -> str:
        return "Local LLM"

    @property
    def endpoint(self) -> str:
        """Get API endpoint."""
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: str):
        """Set API endpoint."""
        self._endpoint = value.rstrip('/')
        self._settings.local_endpoint = self._endpoint

    def check_availability(self) -> bool:
        """Check if local LLM is available."""
        try:
            url = f"{self._endpoint}/api/tags"
            with httpx.Client(timeout=5) as client:
                response = client.get(url)
                if response.status_code == 200:
                    self._is_available = True
                    self.availability_checked.emit(True)
                    return True
        except Exception:
            pass

        self._is_available = False
        self.availability_checked.emit(False)
        return False

    def _get_default_system_prompt(self) -> str:
        """Get default system prompt."""
        return """You are a binary data analysis expert. You help users understand and analyze binary data formats, structures, and patterns. You can:
- Identify binary formats (ELF, PE, Mach-O, etc.)
- Explain data structures and fields
- Generate parsing code in C, Python, and other languages
- Detect patterns in binary data
- Provide insights about file formats and protocols

Be concise and technical in your responses."""

    def analyze(self, data: bytes, context: str = "") -> str:
        """Analyze binary data."""
        if not self._is_available:
            return "Local LLM not available. Please check your Ollama/LM Studio installation."

        data_repr = self._format_data_for_ai(data)

        prompt = f"""{self._settings.system_prompt or self._get_default_system_prompt()}

Analyze the following binary data:

{data_repr}

{context}

Provide:
1. Data type identification
2. Potential structure/format
3. Key observations
4. Any concerning patterns

If this is part of a larger file, note that only a sample was provided.
"""

        return self._send_request(prompt)

    def explain(self, data: bytes, offset: int = 0, length: int = 0) -> str:
        """Explain data at offset."""
        if not self._is_available:
            return "Local LLM not available."

        if length == 0:
            length = len(data)

        sample = data[:min(length, 512)]
        data_repr = self._format_data_for_ai(sample)

        prompt = f"""{self._settings.system_prompt or self._get_default_system_prompt()}

Explain the binary data at offset {offset}:

{data_repr}

Provide a detailed explanation of:
1. What this data represents
2. The data type and encoding
3. Any recognizable patterns or structures
"""

        return self._send_request(prompt)

    def generate_code(self, structure: Dict[str, Any], language: str = "c") -> str:
        """Generate parsing code."""
        if not self._is_available:
            return "Local LLM not available."

        prompt = f"""Generate {language} code to parse this data structure:

{json.dumps(structure, indent=2)}

Requirements:
- Use standard libraries only
- Include error handling
- Add comments explaining each step
- Make it standalone and compilable

Provide only the code with brief comments."""

        return self._send_request(prompt)

    def search_natural_language(self, query: str, data: bytes) -> List[Dict[str, Any]]:
        """Natural language search."""
        if not self._is_available:
            return []

        data_repr = self._format_data_for_ai(data, 512)

        prompt = f"""{self._get_default_system_prompt()}

Search for: "{query}"

In this data:
{data_repr}

Find all occurrences matching this description. Return results as JSON:
{{
    "results": [
        {{"offset": 0, "description": "...", "confidence": 0.9}}
    ],
    "count": 1
}}

If no matches, return {{"results": [], "count": 0}}"""

        result = self._send_request(prompt)

        try:
            # Try to parse as JSON
            return json.loads(result)
        except:
            return [{"raw": result, "error": "Could not parse response"}]

    def chat(self, message: str, history: List[Dict[str, str]] = None) -> str:
        """Chat with AI."""
        if not self._is_available:
            return "Local LLM not available. Please start Ollama or LM Studio."

        prompt_parts = []

        # System prompt
        system = self._settings.system_prompt or self._get_default_system_prompt()
        prompt_parts.append(f"System: {system}")

        # History
        if history:
            for msg in history[-10:]:  # Limit history
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role.capitalize()}: {content}")

        # Current message
        prompt_parts.append(f"User: {message}")

        prompt_parts.append("Assistant:")

        prompt = "\n\n".join(prompt_parts)

        return self._send_request(prompt)

    def _send_request(self, prompt: str) -> str:
        """Send request to local LLM."""
        self.thinking_started.emit()

        self._worker = LocalAIWorker(self._endpoint, prompt, self._settings)
        self._worker.response.connect(self._handle_response)
        self._worker.error.connect(self._handle_error)
        self._worker.finished.connect(self._handle_finished)
        self._worker.start()

        # Wait for completion (simplified - could be async)
        self._worker.wait()

        return self._last_response or "No response from AI"

    def _handle_response(self, response: str):
        """Handle AI response."""
        self._last_response = response
        self.response_ready.emit(response)

    def _handle_error(self, error: str):
        """Handle AI error."""
        self.error_occurred.emit(error)

    def _handle_finished(self):
        """Handle worker finished."""
        self.thinking_finished.emit()

    def cancel(self):
        """Cancel ongoing request."""
        if self._worker:
            self._worker.stop()
            self._worker.wait()
            self._worker = None

    def reset(self):
        """Reset AI state."""
        super().reset()
        self._worker = None
