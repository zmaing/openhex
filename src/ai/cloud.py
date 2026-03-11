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

    def configure(self, **kwargs):
        """Configure cloud provider settings."""
        provider_name = kwargs.pop("provider", None)
        if provider_name == "anthropic":
            self._provider = AIProvider.CLOUD_ANTHROPIC
        elif provider_name == "minimax":
            self._provider = AIProvider.CLOUD_MINIMAX
        elif provider_name == "glm":
            self._provider = AIProvider.CLOUD_GLM
        elif provider_name == "openai":
            self._provider = AIProvider.CLOUD_OPENAI
        super().configure(**kwargs)

    @property
    def provider_name(self) -> str:
        if self._provider == AIProvider.CLOUD_OPENAI:
            return "OpenAI"
        if self._provider == AIProvider.CLOUD_ANTHROPIC:
            return "Anthropic"
        if self._provider == AIProvider.CLOUD_MINIMAX:
            return "MiniMax"
        if self._provider == AIProvider.CLOUD_GLM:
            return "GLM"
        return "Cloud API"

    @property
    def provider(self) -> AIProvider:
        return self._provider

    def check_availability(self) -> bool:
        """Check if cloud API is available."""
        if not self._settings.api_key:
            self._is_available = False
            return False

        try:
            if self._is_openai_compatible():
                url = f"{self._normalized_base_url()}/models"
            else:
                base = (self._settings.base_url or "https://api.anthropic.com").rstrip("/")
                url = f"{base}/v1/models"

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

        if self._is_openai_compatible():
            if self._settings.api_key:
                headers["Authorization"] = f"Bearer {self._settings.api_key}"
        else:
            if self._settings.api_key:
                headers["x-api-key"] = self._settings.api_key
            headers["anthropic-version"] = "2023-06-01"

        return headers

    def _is_openai_compatible(self) -> bool:
        """Return whether the active provider uses the OpenAI-compatible wire format."""
        return self._provider in {
            AIProvider.CLOUD_OPENAI,
            AIProvider.CLOUD_MINIMAX,
            AIProvider.CLOUD_GLM,
        }

    def _normalized_base_url(self) -> str:
        """Return the configured or provider-default base URL without a trailing slash."""
        if self._provider == AIProvider.CLOUD_MINIMAX:
            default_base = "https://api.minimaxi.com/v1"
        elif self._provider == AIProvider.CLOUD_GLM:
            default_base = "https://open.bigmodel.cn/api/paas/v4"
        elif self._provider == AIProvider.CLOUD_OPENAI:
            default_base = "https://api.openai.com/v1"
        else:
            default_base = "https://api.anthropic.com"
        return (self._settings.base_url or default_base).rstrip("/")

    def _default_model(self) -> str:
        """Return the provider-specific default model name."""
        if self._provider == AIProvider.CLOUD_MINIMAX:
            return "MiniMax-M2.5"
        if self._provider == AIProvider.CLOUD_GLM:
            return "glm-5"
        if self._provider == AIProvider.CLOUD_ANTHROPIC:
            return "claude-sonnet-4-20250514"
        return "gpt-4o"

    def _get_api_url(self) -> str:
        """Get API URL."""
        if self._is_openai_compatible():
            base = self._normalized_base_url()
            return f"{base}/chat/completions"
        else:
            base = self._normalized_base_url()
            return f"{base}/v1/messages"

    def _format_data_for_ai(self, data: bytes, max_bytes: int = 512) -> str:
        """Format data for AI consumption."""
        data = data[:max_bytes]
        hex_str = ' '.join(f'{b:02x}' for b in data)
        ascii_repr = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        return f"Hex: {hex_str}\nASCII: {ascii_repr}"

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Complete a chat-style request."""
        return self._send_request(messages)

    def _prepare_messages(self, messages: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], str]:
        """Normalize chat messages for providers that are stricter than OpenAI."""
        system_parts: List[str] = []
        normalized: List[Dict[str, str]] = []

        for message in messages:
            role = str(message.get("role", "user")).strip().lower()
            content = str(message.get("content", ""))
            if role == "system":
                system_parts.append(content)
                continue
            normalized.append(
                {
                    "role": role if role in {"user", "assistant", "tool"} else "user",
                    "content": content,
                }
            )

        system_text = "\n\n".join(part for part in system_parts if part.strip()).strip()
        if self._is_openai_compatible() and system_text:
            normalized.insert(0, {"role": "system", "content": system_text})

        return normalized, system_text

    def _normalized_temperature(self) -> float:
        """Return a provider-safe temperature value."""
        try:
            temperature = float(self._settings.temperature)
        except (TypeError, ValueError):
            temperature = 0.7

        if self._provider == AIProvider.CLOUD_MINIMAX:
            if temperature <= 0:
                return 0.01
            return min(temperature, 1.0)
        if self._provider == AIProvider.CLOUD_ANTHROPIC:
            return min(max(temperature, 0.0), 1.0)
        return min(max(temperature, 0.0), 2.0)

    def _build_payload(self, messages: List[Dict[str, str]], stream: bool = False) -> Dict[str, Any]:
        """Build a provider-specific request payload."""
        normalized_messages, system_text = self._prepare_messages(messages)
        payload: Dict[str, Any] = {
            "model": self._settings.model or self._default_model(),
            "messages": normalized_messages,
            "temperature": self._normalized_temperature(),
            "stream": stream,
        }

        max_tokens = max(int(self._settings.max_tokens or 0), 1)
        if self._provider == AIProvider.CLOUD_MINIMAX:
            payload["max_completion_tokens"] = max_tokens
            # MiniMax reasoning models can separate chain-of-thought from answer content.
            payload["reasoning_split"] = True
        else:
            payload["max_tokens"] = max_tokens

        if not self._is_openai_compatible():
            payload["system"] = system_text

        return payload

    def _build_provider_hint(self, status_code: int, response_text: str) -> str:
        """Return a short provider-specific hint for common request failures."""
        if status_code != 400:
            return ""

        lowered = response_text.lower()
        if self._provider == AIProvider.CLOUD_MINIMAX:
            if "temperature" in lowered:
                return "MiniMax requires temperature in the range (0, 1]."
            if "model" in lowered:
                return "Check that the MiniMax model name is valid for your account and region."
            return (
                "MiniMax rejects requests when the API key and base URL region do not match, or"
                " when temperature is outside (0, 1]."
            )

        if self._provider == AIProvider.CLOUD_GLM:
            return (
                "GLM uses the BigModel OpenAI-compatible endpoint"
                " https://open.bigmodel.cn/api/paas/v4 with models such as glm-5."
            )

        return ""

    def _format_http_error(self, error: httpx.HTTPStatusError) -> str:
        """Build a user-facing HTTP error string with response details."""
        response_text = ""
        status_code = 0
        if error.response is not None:
            status_code = error.response.status_code
            try:
                response_text = error.response.text.strip()
            except Exception:
                response_text = ""

        parts = [str(error)]
        if response_text:
            parts.append(f"Response body: {self._truncate_response(response_text, 1200)}")

        hint = self._build_provider_hint(status_code, response_text)
        if hint:
            parts.append(f"Hint: {hint}")

        return "\n".join(parts)

    def _send_request(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Send request to cloud API."""
        self.thinking_started.emit()

        try:
            url = self._get_api_url()
            headers = self._get_headers()
            payload = self._build_payload(messages, stream=stream)

            with httpx.Client(timeout=self._settings.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                if stream:
                    return self._handle_stream(response)
                else:
                    return self._parse_response(response.json())

        except httpx.HTTPStatusError as e:
            error_msg = self._format_http_error(e)
            self.error_occurred.emit(error_msg)
            self.thinking_finished.emit()
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = str(e)
            self.error_occurred.emit(error_msg)
            self.thinking_finished.emit()
            return f"Error: {error_msg}"

    def _parse_response(self, data: Dict[str, Any]) -> str:
        """Parse API response."""
        self.thinking_finished.emit()

        if self._is_openai_compatible():
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

        return self.complete(messages)

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

        return self.complete(messages)

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

        return self.complete(messages)

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

        result = self.complete(messages)

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

        return self.complete(messages)

    def cancel(self):
        """Cancel ongoing request."""
        # Cloud requests can't be cancelled easily
        pass

    def reset(self):
        """Reset AI state."""
        super().reset()
        self._last_response = ""
        self._usage = {}
