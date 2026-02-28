"""
Cloud AI

Cloud API integration for OpenAI and Anthropic.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any, List
import httpx

from .base import AIBase, AISettings, AIProvider


class CloudAI(AIBase):
    """
    Cloud AI provider (OpenAI/Anthropic).

    Provides access to cloud-based language models.
    """

    # Signals
    usage_reported = pyqtSignal(dict)  # Token usage

    def __init__(self, parent: Optional[QObject] = None, provider: AIProvider = AIProvider.CLOUD_OPENAI):
        super().__init__(parent)
        self._provider = provider
        self._last_response = ""
        self._usage = {}

    @property
    def provider_name(self) -> str:
        if self._provider == AIProvider.CLOUD_OPENAI:
            return "OpenAI"
        return "Anthropic"

    @property
    def provider(self) -> AIProvider:
        return self._provider

    def check_availability(self) -> bool:
        """Check if cloud API is available."""
        if not self._settings.api_key:
            self._is_available = False
            return False

        try:
            if self._provider == AIProvider.CLOUD_OPENAI:
                url = "https://api.openai.com/v1/models"
            else:
                url = "https://api.anthropic.com/v1/models"

            headers = self._get_headers()

            with httpx.Client(timeout=5) as client:
                response = client.get(url, headers=headers)
                if response.status_code == 200:
                    self._is_available = True
                    return True
        except Exception:
            pass

        self._is_available = False
        return False

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
        }

        if self._provider == AIProvider.CLOUD_OPENAI:
            if self._settings.api_key:
                headers["Authorization"] = f"Bearer {self._settings.api_key}"
        else:
            if self._settings.api_key:
                headers["x-api-key"] = self._settings.api_key
            headers["anthropic-version"] = "2023-06-01"

        return headers

    def _get_api_url(self) -> str:
        """Get API URL."""
        if self._provider == AIProvider.CLOUD_OPENAI:
            base = self._settings.base_url or "https://api.openai.com/v1"
            return f"{base}/chat/completions"
        else:
            base = self._settings.base_url or "https://api.anthropic.com"
            return f"{base}/v1/messages"

    def _format_data_for_ai(self, data: bytes, max_bytes: int = 512) -> str:
        """Format data for AI consumption."""
        data = data[:max_bytes]
        hex_str = ' '.join(f'{b:02x}' for b in data)
        ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        return f"Hex: {hex_str}\nASCII: {ascii_repr}"

    def _send_request(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Send request to cloud API."""
        self.thinking_started.emit()

        try:
            url = self._get_api_url()
            headers = self._get_headers()

            if self._provider == AIProvider.CLOUD_OPENAI:
                payload = {
                    "model": self._settings.model or "gpt-4",
                    "messages": messages,
                    "temperature": self._settings.temperature,
                    "max_tokens": self._settings.max_tokens,
                    "stream": stream,
                }
            else:
                payload = {
                    "model": self._settings.model or "claude-sonnet-4-20250514",
                    "messages": messages,
                    "temperature": self._settings.temperature,
                    "max_tokens": self._settings.max_tokens,
                    "stream": stream,
                }

            with httpx.Client(timeout=self._settings.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                if stream:
                    return self._handle_stream(response)
                else:
                    return self._parse_response(response.json())

        except Exception as e:
            error_msg = str(e)
            self.error_occurred.emit(error_msg)
            self.thinking_finished.emit()
            return f"Error: {error_msg}"

    def _parse_response(self, data: Dict[str, Any]) -> str:
        """Parse API response."""
        self.thinking_finished.emit()

        if self._provider == AIProvider.CLOUD_OPENAI:
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")

            # Track usage
            if "usage" in data:
                self._usage = data["usage"]
                self.usage_reported.emit(data["usage"])

            self._last_response = content
            return content
        else:
            content = data.get("content", "")
            if isinstance(content, list):
                content = "".join(c.get("text", "") for c in content)

            if "usage" in data:
                self._usage = data["usage"]
                self.usage_reported.emit(data["usage"])

            self._last_response = content
            return content

    def _handle_stream(self, response) -> str:
        """Handle streaming response."""
        content = ""
        for chunk in response.iter_lines():
            if chunk:
                # Parse SSE format
                pass  # Simplified

        self.thinking_finished.emit()
        return content

    def analyze(self, data: bytes, context: str = "") -> str:
        """Analyze binary data."""
        data_repr = self._format_data_for_ai(data)

        system_prompt = self._settings.system_prompt or """You are a binary data analysis expert. Help users understand binary data formats, structures, and patterns. Be concise and technical."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""Analyze this binary data:

{data_repr}

{context}

Provide:
1. Data type identification
2. Potential structure/format
3. Key observations
4. Any concerning patterns"""}
        ]

        return self._send_request(messages)

    def explain(self, data: bytes, offset: int = 0, length: int = 0) -> str:
        """Explain data at offset."""
        sample = data[:min(length or 256, 512)]
        data_repr = self._format_data_for_ai(sample)

        messages = [
            {"role": "system", "content": "You are a binary data expert."},
            {"role": "user", "content": f"""Explain this binary data at offset {offset}:

{data_repr}

Provide:
1. What this data represents
2. The data type and encoding
3. Any recognizable patterns"""}
        ]

        return self._send_request(messages)

    def generate_code(self, structure: Dict[str, Any], language: str = "c") -> str:
        """Generate parsing code."""
        import json
        structure_str = json.dumps(structure, indent=2)

        messages = [
            {"role": "system", "content": "You are an expert programmer."},
            {"role": "user", "content": f"""Generate {language} code to parse this structure:

{structure_str}

Requirements:
- Use standard libraries
- Include error handling
- Add comments
- Make it standalone and compilable

Return only the code."""}
        ]

        return self._send_request(messages)

    def search_natural_language(self, query: str, data: bytes) -> List[Dict[str, Any]]:
        """Natural language search."""
        import json
        data_repr = self._format_data_for_ai(data, 256)

        messages = [
            {"role": "system", "content": "You are a binary data search expert."},
            {"role": "user", "content": f"""Search for "{query}" in this binary data:

{data_repr}

Return results as JSON:
{{
    "results": [
        {{"offset": 0, "description": "...", "confidence": 0.9}}
    ],
    "count": 1
}}"""}
        ]

        result = self._send_request(messages)

        try:
            # Try to extract JSON
            start = result.find('{')
            end = result.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(result[start:end])
        except:
            pass

        return [{"raw": result}]

    def chat(self, message: str, history: List[Dict[str, str]] = None) -> str:
        """Chat with AI."""
        messages = []

        # System prompt
        system = self._settings.system_prompt or "You are a helpful assistant for binary data analysis."
        messages.append({"role": "system", "content": system})

        # History
        if history:
            for msg in history[-10:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # Current message
        messages.append({"role": "user", "content": message})

        return self._send_request(messages)

    def cancel(self):
        """Cancel ongoing request."""
        # Cloud requests can't be cancelled easily
        pass

    def reset(self):
        """Reset AI state."""
        super().reset()
        self._last_response = ""
        self._usage = {}
