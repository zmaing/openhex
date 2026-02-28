"""
AI Analyzer

High-level AI data analysis functionality.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any, List
from enum import Enum, auto

from .base import AIBase, AISettings, AIProvider
from .local import LocalAI
from .cloud import CloudAI


class AnalysisType(Enum):
    """Analysis type enumeration."""
    PATTERN = auto()
    STRUCTURE = auto()
    ANOMALY = auto()
    FULL = auto()


class AnalysisResult:
    """Analysis result container."""

    def __init__(self):
        self.summary: str = ""
        self.patterns: List[Dict[str, Any]] = []
        self.structure: Optional[Dict[str, Any]] = None
        self.anomalies: List[Dict[str, Any]] = []
        self.suggestions: List[str] = []
        self.code_samples: Dict[str, str] = {}
        self.confidence: float = 0.0
        self.execution_time: float = 0.0


class AIAnalyzer(QObject):
    """
    AI-powered data analyzer.

    Provides high-level analysis functions combining multiple AI capabilities.
    """

    # Signals
    analysis_started = pyqtSignal(AnalysisType)
    analysis_progress = pyqtSignal(str)  # Status message
    analysis_finished = pyqtSignal(AnalysisResult)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._ai_provider: Optional[AIBase] = None
        self._default_provider: AIProvider = AIProvider.LOCAL
        self._result = AnalysisResult()

    def set_provider(self, provider: AIBase):
        """Set AI provider."""
        self._ai_provider = provider

    def get_provider(self, provider_type: AIProvider = None) -> AIBase:
        """Get AI provider of specified type."""
        if provider_type is None:
            provider_type = self._default_provider

        if self._ai_provider and type(self._ai_provider).__name__.lower().endswith(provider_type.name.lower()):
            return self._ai_provider

        if provider_type == AIProvider.LOCAL:
            return LocalAI()
        else:
            return CloudAI(provider=provider_type)

    def analyze(self, data: bytes, analysis_type: AnalysisType = AnalysisType.FULL,
                context: str = "") -> AnalysisResult:
        """
        Perform comprehensive analysis.

        Args:
            data: Binary data
            analysis_type: Type of analysis
            context: Additional context

        Returns:
            AnalysisResult
        """
        import time
        start_time = time.time()

        self._result = AnalysisResult()
        self.analysis_started.emit(analysis_type)

        try:
            provider = self.get_provider()

            if not provider.is_available:
                self._result.summary = "AI provider not available. Please configure AI settings."
                self.error_occurred.emit("Provider not available")
                return self._result

            if analysis_type in (AnalysisType.PATTERN, AnalysisType.FULL):
                self._analyze_patterns(data, provider)

            if analysis_type in (AnalysisType.STRUCTURE, AnalysisType.FULL):
                self._analyze_structure(data, provider)

            if analysis_type in (AnalysisType.ANOMALY, AnalysisType.FULL):
                self._detect_anomalies(data, provider)

            self._result.summary = self._generate_summary()
            self._result.execution_time = time.time() - start_time

        except Exception as e:
            self._result.summary = f"Analysis error: {str(e)}"
            self.error_occurred.emit(str(e))

        self.analysis_finished.emit(self._result)
        return self._result

    def _analyze_patterns(self, data: bytes, provider: AIBase):
        """Analyze data patterns."""
        self.analysis_progress.emit("Analyzing patterns...")

        response = provider.analyze(data, "Identify any patterns in this data. List all recognizable patterns.")

        self._result.patterns = [
            {
                "type": "general",
                "description": response,
                "offset": 0,
                "length": len(data)
            }
        ]

    def _analyze_structure(self, data: bytes, provider: AIBase):
        """Analyze data structure."""
        self.analysis_progress.emit("Analyzing structure...")

        response = provider.explain(data, 0, min(len(data), 1024))

        self._result.structure = {
            "explanation": response,
            "sample_size": min(len(data), 1024),
            "total_size": len(data)
        }

        # Generate code samples
        self.analysis_progress.emit("Generating code samples...")

        c_code = provider.generate_code(self._result.structure, "c")
        self._result.code_samples["c"] = c_code

        py_code = provider.generate_code(self._result.structure, "python")
        self._result.code_samples["python"] = py_code

    def _detect_anomalies(self, data: bytes, provider: AIBase):
        """Detect anomalies in data."""
        self.analysis_progress.emit("Detecting anomalies...")

        anomalies = []

        # Check for suspicious patterns
        if len(data) > 0:
            null_count = data.count(b'\x00')
            null_ratio = null_count / len(data)

            if null_ratio > 0.5:
                anomalies.append({
                    "type": "high_null_ratio",
                    "description": f"High null byte ratio ({null_ratio:.1%})",
                    "severity": "low"
                })

            # Check for repeated patterns
            chunk_size = 256
            for i in range(0, min(len(data), 4096), chunk_size):
                chunk = data[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    continue

                # Check for repeating sequences
                for size in [4, 8, 16]:
                    if size * 3 > len(chunk):
                        continue
                    seq = chunk[:size]
                    repeated = True
                    for j in range(size, len(chunk), size):
                        if chunk[j:j + size] != seq:
                            repeated = False
                            break
                    if repeated:
                        anomalies.append({
                            "type": "repeating_pattern",
                            "description": f"Repeating {size}-byte pattern detected",
                            "offset": i,
                            "severity": "info"
                        })
                        break

        # AI-based anomaly detection
        response = provider.analyze(data, "Are there any suspicious or anomalous patterns in this data?")

        anomalies.append({
            "type": "ai_analysis",
            "description": response,
            "severity": "info"
        })

        self._result.anomalies = anomalies

    def _generate_summary(self) -> str:
        """Generate analysis summary."""
        parts = []

        if self._result.patterns:
            parts.append(f"Found {len(self._result.patterns)} pattern(s)")

        if self._result.anomalies:
            anomaly_types = set(a.get("severity", "info") for a in self._result.anomalies)
            parts.append(f"Detected {len(self._result.anomalies)} anomaly/ies")

        if self._result.code_samples:
            parts.append("Generated parsing code samples")

        if not parts:
            return "No significant patterns detected."

        return "; ".join(parts)

    def quick_analyze(self, data: bytes) -> str:
        """
        Quick analysis for status bar.

        Args:
            data: Binary data

        Returns:
            Brief analysis summary
        """
        if len(data) < 16:
            return "Data too small"

        # Quick heuristics
        if data[:4] == b'\x7fELF':
            return "ELF executable"
        elif data[:2] == b'MZ':
            return "PE/DOS executable"
        elif data[:4] == b'PK\x03\x04':
            return "ZIP archive"
        elif data[:4] == b'\x89PNG':
            return "PNG image"
        elif data[:3] == b'\xff\xd8\xff':
            return "JPEG image"
        elif data[:6] == b'\x1f\x8b\x08':
            return "GZIP archive"

        # Check for text
        text_ratio = sum(1 for b in data[:256] if 32 <= b < 127) / min(len(data), 256)
        if text_ratio > 0.8:
            return "Text/JSON/XML data"

        return "Binary data (unknown format)"
