"""
Auto Parser

AI-powered automatic data structure detection.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum, auto

from .basic import BasicParser, BasicType, Endianness


class PatternType(Enum):
    """Detected pattern types."""
    INTEGER_SEQUENCE = auto()
    FLOAT_SEQUENCE = auto()
    STRING_LITERAL = auto()
    TIMESTAMP = auto()
    NETWORK_ADDRESS = auto()
    BINARY_STRUCTURE = auto()
    ENCODED_DATA = auto()
    UNKNOWN = auto()


class DetectedPattern:
    """Represents a detected pattern."""

    def __init__(self, pattern_type: PatternType, offset: int, length: int,
                 confidence: float, description: str, suggestions: List[str] = None):
        self.pattern_type = pattern_type
        self.offset = offset
        self.length = length
        self.confidence = confidence
        self.description = description
        self.suggestions = suggestions or []

    def __repr__(self):
        return f"DetectedPattern({self.pattern_type.name} @ {self.offset}, conf={self.confidence:.2f})"


class AutoParser(QObject):
    """
    Automatic data structure detection and parsing.

    Uses heuristics and patterns to identify data structures.
    """

    # Signals
    analysis_started = pyqtSignal()
    pattern_detected = pyqtSignal(DetectedPattern)
    analysis_finished = pyqtSignal(object)  # List[DetectedPattern]
    analysis_error = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._basic_parser = BasicParser()

    def analyze(self, data: bytes) -> List[DetectedPattern]:
        """
        Analyze data for patterns.

        Args:
            data: Binary data to analyze

        Returns:
            List of detected patterns
        """
        self.analysis_started.emit()

        patterns = []

        if len(data) < 4:
            self.analysis_finished.emit(patterns)
            return patterns

        # Check for common patterns
        patterns.extend(self._check_integer_sequence(data))
        patterns.extend(self._check_float_sequence(data))
        patterns.extend(self._check_strings(data))
        patterns.extend(self._check_timestamps(data))
        patterns.extend(self._check_network_addresses(data))
        patterns.extend(self._check_endianness(data))

        # Sort by confidence
        patterns.sort(key=lambda p: p.confidence, reverse=True)

        for pattern in patterns:
            self.pattern_detected.emit(pattern)

        self.analysis_finished.emit(patterns)
        return patterns

    def _check_integer_sequence(self, data: bytes) -> List[DetectedPattern]:
        """Check for integer sequences."""
        patterns = []

        if len(data) < 8:
            return patterns

        # Check for common integer patterns
        for size in [4, 2, 8]:
            for offset in range(0, min(len(data) - size * 4, 256), size):
                values = []
                for i in range(4):
                    try:
                        val = int.from_bytes(
                            data[offset + i * size:offset + (i + 1) * size],
                            'little'
                        )
                        values.append(val)
                    except:
                        break

                if len(values) >= 4:
                    # Check for sequential patterns
                    is_sequential = all(values[i] + 1 == values[i + 1] for i in range(len(values) - 1))
                    is_sequential_rev = all(values[i] - 1 == values[i + 1] for i in range(len(values) - 1))

                    if is_sequential or is_sequential_rev:
                        confidence = 0.7 + (len(values) - 4) * 0.05
                        patterns.append(DetectedPattern(
                            PatternType.INTEGER_SEQUENCE,
                            offset,
                            len(values) * size,
                            min(confidence, 0.95),
                            f"{size * 8}-bit integer sequence",
                            [f"Field type: uint{size * 8}", "Possible array/buffer"]
                        ))

        return patterns

    def _check_float_sequence(self, data: bytes) -> List[DetectedPattern]:
        """Check for floating-point sequences."""
        patterns = []

        if len(data) < 8:
            return patterns

        for size in [4, 8]:
            for offset in range(0, min(len(data) - size * 4, 256), size):
                try:
                    import struct
                    values = []
                    for i in range(4):
                        fmt = "<f" if size == 4 else "<d"
                        val = struct.unpack(fmt, data[offset + i * size:offset + (i + 1) * size])[0]
                        if val != val:  # NaN check
                            break
                        values.append(val)

                    if len(values) >= 4:
                        patterns.append(DetectedPattern(
                            PatternType.FLOAT_SEQUENCE,
                            offset,
                            len(values) * size,
                            0.75,
                            f"{size * 8}-bit float sequence"
                        ))
                except:
                    pass

        return patterns

    def _check_strings(self, data: bytes) -> List[DetectedPattern]:
        """Check for string literals."""
        patterns = []

        for offset in range(len(data)):
            if data[offset] < 32 or data[offset] > 126:
                continue

            # ASCII string
            end = offset
            while end < len(data) and 32 <= data[end] <= 126:
                end += 1

            length = end - offset
            if length >= 4:
                try:
                    string = data[offset:end].decode('ascii')
                    if all(c.isprintable() or c.isspace() for c in string):
                        patterns.append(DetectedPattern(
                            PatternType.STRING_LITERAL,
                            offset,
                            length,
                            0.6 + min(length * 0.02, 0.3),
                            f"ASCII string: '{string[:20]}...'",
                            ["Type: char[] or string", "Encoding: ASCII"]
                        ))
                except:
                    pass

            offset = end

        return patterns

    def _check_timestamps(self, data: bytes) -> List[DetectedPattern]:
        """Check for timestamp values."""
        patterns = []

        if len(data) < 8:
            return patterns

        import time

        for size in [4, 8]:
            for offset in range(0, min(len(data) - size, 256), size):
                try:
                    if size == 4:
                        # Unix timestamp
                        ts = int.from_bytes(data[offset:offset + 4], 'little')
                        if 946684800 < ts < 4102444800:  # 2000-2100
                            dt = time.localtime(ts)
                            patterns.append(DetectedPattern(
                                PatternType.TIMESTAMP,
                                offset,
                                size,
                                0.8,
                                f"Unix timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', dt)}",
                                ["Type: uint32_t", "Format: Unix timestamp (seconds)"]
                            ))
                    else:
                        # Windows FILETIME or Unix timestamp
                        ts = int.from_bytes(data[offset:offset + 8], 'little')
                        if 11644473600000000 < ts < 139000000000000000:
                            # Windows FILETIME
                            dt = (ts - 116444736000000000) / 10000000
                            dt = time.localtime(dt)
                            patterns.append(DetectedPattern(
                                PatternType.TIMESTAMP,
                                offset,
                                size,
                                0.85,
                                f"Windows FILETIME: {time.strftime('%Y-%m-%d %H:%M:%S', dt)}",
                                ["Type: uint64_t", "Format: Windows FILETIME"]
                            ))
                except:
                    pass

        return patterns

    def _check_network_addresses(self, data: bytes) -> List[DetectedPattern]:
        """Check for network addresses."""
        patterns = []

        if len(data) < 4:
            return patterns

        for offset in range(0, min(len(data) - 4, 256), 4):
            # IPv4 check
            ip = tuple(data[offset + i] for i in range(4))
            if all(0 <= b <= 255 for b in ip):
                if (ip[0] in [10, 172, 192] or
                    (ip[0] == 127) or
                    (ip[0] == 224) or  # Multicast
                    (0 <= ip[1] <= 255 and 0 <= ip[2] <= 255)):
                    is_private = ip[0] in [10, 127] or (ip[0] == 172 and 16 <= ip[1] <= 31) or (ip[0] == 192 and ip[1] in [168, 169, 170])
                    patterns.append(DetectedPattern(
                        PatternType.NETWORK_ADDRESS,
                        offset,
                        4,
                        0.7 if is_private else 0.5,
                        f"IPv4 address: {'.'.join(map(str, ip))} ({'private' if is_private else 'public'})",
                        ["Type: uint32_t (network byte order)", "Family: AF_INET"]
                    ))

        # IPv6 check
        if len(data) >= 16:
            for offset in range(0, min(len(data) - 16, 256), 16):
                patterns.append(DetectedPattern(
                    PatternType.NETWORK_ADDRESS,
                    offset,
                    16,
                    0.6,
                    f"IPv6 address (possible)",
                    ["Type: uint8_t[16]", "Family: AF_INET6"]
                ))

        return patterns

    def _check_endianness(self, data: bytes) -> List[DetectedPattern]:
        """Check for endianness indicators."""
        patterns = []

        if len(data) < 4:
            return patterns

        # Check for ELF magic (0x7F 0x45 0x4C 0x46)
        if data[:4] == b'\x7fELF':
            endian = "little" if data[5] == 1 else "big"
            patterns.append(DetectedPattern(
                PatternType.BINARY_STRUCTURE,
                0,
                4,
                0.95,
                f"ELF magic number (endianness: {endian})",
                ["Format: ELF executable", f"Endianness: {endian}"]
            ))

        # Check for PE magic (PE\x00\x00)
        if data[:2] == b'MZ':
            patterns.append(DetectedPattern(
                PatternType.BINARY_STRUCTURE,
                0,
                2,
                0.9,
                "DOS MZ header",
                ["Format: PE executable (DOS/Windows)"]
            ))

        # Check for ZIP/JAR magic (PK\x03\x04)
        if data[:4] == b'PK\x03\x04':
            patterns.append(DetectedPattern(
                PatternType.BINARY_STRUCTURE,
                0,
                4,
                0.9,
                "ZIP/JAR archive magic",
                ["Format: ZIP archive", "Content: JAR/DOCX/XLSX etc."]
            ))

        return patterns

    def suggest_structure(self, data: bytes, offset: int = 0) -> Dict[str, Any]:
        """
        Suggest a structure for data at offset.

        Args:
            data: Binary data
            offset: Start offset

        Returns:
            Structure suggestion dict
        """
        if offset >= len(data):
            return {}

        # Analyze patterns at offset
        patterns = self.analyze(data[offset:offset + 1024])

        if not patterns:
            return {"type": "unknown", "confidence": 0.0}

        # Build structure suggestion from patterns
        primary = patterns[0]

        structure = {
            "offset": offset,
            "type": primary.pattern_type.name.lower(),
            "confidence": primary.confidence,
            "description": primary.description,
            "suggestions": primary.suggestions,
            "length": primary.length,
        }

        return structure

    def generate_code(self, structure: Dict[str, Any], language: str = "c") -> str:
        """
        Generate parsing code for structure.

        Args:
            structure: Structure info
            language: Output language (c, python)

        Returns:
            Generated code string
        """
        if language == "c":
            return self._generate_c_code(structure)
        elif language == "python":
            return self._generate_python_code(structure)
        return ""

    def _generate_c_code(self, structure: Dict[str, Any]) -> str:
        """Generate C code."""
        stype = structure.get("type", "unknown")

        if stype == "integer_sequence":
            return """// Parse integer sequence
uint32_t* data = (uint32_t*)(buffer + offset);
for (int i = 0; i < count; i++) {
    printf("Value[%d] = %u\\n", i, data[i]);
}
"""
        elif stype == "string_literal":
            return """// Parse string
char* str = (char*)(buffer + offset);
// String is null-terminated
printf("String: %s\\n", str);
"""
        elif stype == "timestamp":
            return """// Parse timestamp (Unix time)
uint32_t timestamp = *(uint32_t*)(buffer + offset);
time_t t = timestamp;
printf("Date: %s", ctime(&t));
"""
        else:
            return """// Unknown structure type
// Manual analysis required
uint8_t* data = buffer + offset;
"""

    def _generate_python_code(self, structure: Dict[str, Any]) -> str:
        """Generate Python code."""
        stype = structure.get("type", "unknown")

        if stype == "integer_sequence":
            return """# Parse integer sequence
import struct

def parse_integers(data, offset=0, count=4):
    values = []
    for i in range(count):
        val = struct.unpack('<I', data[offset + i*4:offset + (i+1)*4])[0]
        values.append(val)
    return values
"""
        elif stype == "string_literal":
            return """# Parse string
def parse_string(data, offset=0):
    end = offset
    while end < len(data) and 32 <= data[end] < 127:
        end += 1
    return data[offset:end].decode('ascii')
"""
        elif stype == "timestamp":
            return """# Parse Unix timestamp
import time

def parse_timestamp(data, offset=0):
    timestamp = int.from_bytes(data[offset:offset+4], 'little')
    return time.ctime(timestamp)
"""
        else:
            return """# Unknown structure
# Manual analysis required
def parse_unknown(data, offset=0):
    return data[offset:]
"""
