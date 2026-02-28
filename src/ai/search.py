"""
AI Search

Natural language and pattern-based search functionality.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QThread
from typing import Optional, Dict, Any, List

from .base import AIBase, AIProvider
from .local import LocalAI
from .cloud import CloudAI


class SearchHit:
    """Search hit container."""

    def __init__(self, offset: int, length: int, description: str, confidence: float):
        self.offset = offset
        self.length = length
        self.description = description
        self.confidence = confidence

    def __repr__(self):
        return f"SearchHit(@{self.offset}, conf={self.confidence:.2f})"


class AISearch(QObject):
    """
    AI-powered search functionality.

    Provides natural language and pattern-based search.
    """

    # Signals
    search_started = pyqtSignal(str)  # Query
    search_progress = pyqtSignal(int, int)  # Current, Total
    search_hit = pyqtSignal(SearchHit)  # Found hit
    search_finished = pyqtSignal(object)  # All results (use object for list)
    search_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._ai_provider: Optional[AIBase] = None
        self._results: List[SearchHit] = []
        self._is_searching = False

    @property
    def is_searching(self) -> bool:
        """Check if searching."""
        return self._is_searching

    def set_provider(self, provider: AIBase):
        """Set AI provider."""
        self._ai_provider = provider

    def search(self, query: str, data: bytes, chunk_size: int = 4096) -> List[SearchHit]:
        """
        Search using natural language.

        Args:
            query: Search query
            data: Binary data to search
            chunk_size: Size of chunks to analyze

        Returns:
            List of search hits
        """
        self._results = []
        self._is_searching = True
        self.search_started.emit(query)

        try:
            provider = self._ai_provider or LocalAI()

            if not provider.is_available:
                self.search_error.emit("AI provider not available")
                return []

            # Process data in chunks
            chunks = self._split_data(data, chunk_size)
            total = len(chunks)

            for i, chunk in enumerate(chunks):
                self.search_progress.emit(i + 1, total)

                # Analyze chunk
                hit = self._search_chunk(query, chunk, i * chunk_size, provider)
                if hit:
                    self._results.append(hit)
                    self.search_hit.emit(hit)

        except Exception as e:
            self.search_error.emit(str(e))

        self._is_searching = False
        self.search_finished.emit(self._results)
        return self._results

    def _split_data(self, data: bytes, chunk_size: int) -> List[bytes]:
        """Split data into chunks."""
        chunks = []
        for i in range(0, len(data), chunk_size):
            chunks.append(data[i:i + chunk_size])
        return chunks

    def _search_chunk(self, query: str, chunk: bytes, base_offset: int,
                      provider: AIBase) -> Optional[SearchHit]:
        """Search within a chunk."""
        # Convert query to search patterns
        patterns = self._query_to_patterns(query)

        if not patterns:
            # Use AI to search
            return self._ai_search_chunk(query, chunk, base_offset, provider)

        # Pattern-based search
        for pattern in patterns:
            offset = chunk.find(pattern)
            if offset >= 0:
                return SearchHit(
                    base_offset + offset,
                    len(pattern),
                    f"Pattern match: {pattern[:20].hex()}",
                    0.9
                )

        return None

    def _query_to_patterns(self, query: str) -> List[bytes]:
        """Convert query to search patterns."""
        patterns = []

        # Check for hex pattern
        import re
        hex_pattern = re.search(r'(?:0x)?([0-9a-fA-F\s-]+)', query)
        if hex_pattern:
            hex_str = hex_pattern.group(1).replace('-', '').replace(' ', '')
            if len(hex_str) % 2 == 0:
                try:
                    patterns.append(bytes.fromhex(hex_str))
                except:
                    pass

        # Check for string pattern
        string_pattern = re.search(r'"([^"]+)"', query)
        if string_pattern:
            patterns.append(string_pattern.group(1).encode('utf-8'))

        return patterns

    def _ai_search_chunk(self, query: str, chunk: bytes, base_offset: int,
                         provider: AIBase) -> Optional[SearchHit]:
        """Use AI to search chunk."""
        data_repr = provider._format_data_for_ai(chunk)

        response = provider.chat(
            f"Search for '{query}' in this data. Is there a match? "
            f"If yes, where (offset within this chunk)? Respond with just the offset or 'none'."
        )

        try:
            offset = int(response.strip())
            if 0 <= offset < len(chunk):
                return SearchHit(
                    base_offset + offset,
                    len(query),
                    f"AI match for '{query}'",
                    0.8
                )
        except:
            pass

        return None

    def find_similar(self, data: bytes, reference_offset: int, reference_length: int,
                      threshold: float = 0.8) -> List[SearchHit]:
        """
        Find similar data patterns.

        Args:
            data: Data to search
            reference_offset: Reference pattern offset
            reference_length: Reference pattern length
            threshold: Similarity threshold

        Returns:
            List of similar locations
        """
        if reference_offset + reference_length > len(data):
            return []

        reference = data[reference_offset:reference_offset + reference_length]

        # Find similar patterns using sliding window
        results = []
        window_size = reference_length

        for offset in range(0, len(data) - window_size + 1):
            window = data[offset:offset + window_size]
            similarity = self._calculate_similarity(reference, window)

            if similarity >= threshold:
                results.append(SearchHit(
                    offset,
                    window_size,
                    f"Similar pattern ({similarity:.1%})",
                    similarity
                ))

        return results

    def _calculate_similarity(self, a: bytes, b: bytes) -> float:
        """Calculate similarity between two byte sequences."""
        if len(a) != len(b):
            return 0.0

        matches = sum(1 for x, y in zip(a, b) if x == y)
        return matches / len(a)

    def cancel(self):
        """Cancel search."""
        self._is_searching = False
        if self._ai_provider:
            self._ai_provider.cancel()
