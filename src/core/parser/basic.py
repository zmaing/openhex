"""
Basic Parser

Basic type parsing for binary data.
"""

from PyQt6.QtCore import QObject
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum, auto


class Endianness(Enum):
    """Endianness enumeration."""
    LITTLE = auto()
    BIG = auto()


class BasicType(Enum):
    """Basic data types."""
    UINT8 = auto()
    UINT16 = auto()
    UINT32 = auto()
    UINT64 = auto()
    INT8 = auto()
    INT16 = auto()
    INT32 = auto()
    INT64 = auto()
    FLOAT32 = auto()
    FLOAT64 = auto()
    CHAR = auto()
    BYTE = auto()
    BOOL = auto()
    STRING = auto()
    RAW = auto()


class ParsedField:
    """Represents a parsed field."""

    def __init__(self, name: str, type: BasicType, value: Any,
                 offset: int, length: int, endianness: Endianness = Endianness.LITTLE):
        self.name = name
        self.type = type
        self.value = value
        self.offset = offset
        self.length = length
        self.endianness = endianness

    def __repr__(self):
        return f"ParsedField({self.name}={self.value} @ {self.offset})"


class BasicParser(QObject):
    """
    Parser for basic data types.

    Supports integer, float, char, and string types with configurable endianness.
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._endianness: Endianness = Endianness.LITTLE

    @property
    def endianness(self) -> Endianness:
        """Get current endianness."""
        return self._endianness

    @endianness.setter
    def endianness(self, value: Endianness):
        """Set endianness."""
        self._endianness = value

    def set_big_endian(self):
        """Set big endian."""
        self._endianness = Endianness.BIG

    def set_little_endian(self):
        """Set little endian."""
        self._endianness = Endianness.LITTLE

    def parse(self, data: bytes, fields: List[Dict[str, Any]]) -> List[ParsedField]:
        """
        Parse data according to field definitions.

        Args:
            data: Binary data
            fields: List of field definitions with name, type, and optionally length

        Returns:
            List of parsed fields
        """
        results = []
        offset = 0

        for field_def in fields:
            name = field_def.get("name", f"field_{len(results)}")
            type_str = field_def.get("type", "uint8")
            length = field_def.get("length", 0)
            type_enum = self._parse_type_string(type_str)

            if offset >= len(data):
                break

            field = self._parse_field(data, offset, type_enum, length)
            if field:
                results.append(field)
                offset += field.length

        return results

    def _parse_type_string(self, type_str: str) -> BasicType:
        """Convert type string to BasicType."""
        type_map = {
            "uint8": BasicType.UINT8,
            "uint16": BasicType.UINT16,
            "uint32": BasicType.UINT32,
            "uint64": BasicType.UINT64,
            "int8": BasicType.INT8,
            "int16": BasicType.INT16,
            "int32": BasicType.INT32,
            "int64": BasicType.INT64,
            "float32": BasicType.FLOAT32,
            "float64": BasicType.FLOAT64,
            "char": BasicType.CHAR,
            "byte": BasicType.BYTE,
            "bool": BasicType.BOOL,
            "string": BasicType.STRING,
            "raw": BasicType.RAW,
        }
        return type_map.get(type_str.lower(), BasicType.BYTE)

    def _parse_field(self, data: bytes, offset: int, type: BasicType,
                     length: int = 0) -> Optional[ParsedField]:
        """Parse a single field."""
        remaining = len(data) - offset
        endian = self._endianness

        if type == BasicType.UINT8:
            if remaining < 1:
                return None
            value = data[offset]
            return ParsedField("uint8", type, value, offset, 1, endian)

        elif type == BasicType.INT8:
            if remaining < 1:
                return None
            value = data[offset]
            if value > 127:
                value -= 256
            return ParsedField("int8", type, value, offset, 1, endian)

        elif type == BasicType.UINT16:
            if remaining < 2:
                return None
            value = int.from_bytes(data[offset:offset + 2], endian.value == "little")
            return ParsedField("uint16", type, value, offset, 2, endian)

        elif type == BasicType.INT16:
            if remaining < 2:
                return None
            value = int.from_bytes(data[offset:offset + 2], endian.value == "little", signed=True)
            return ParsedField("int16", type, value, offset, 2, endian)

        elif type == BasicType.UINT32:
            if remaining < 4:
                return None
            value = int.from_bytes(data[offset:offset + 4], endian.value == "little")
            return ParsedField("uint32", type, value, offset, 4, endian)

        elif type == BasicType.INT32:
            if remaining < 4:
                return None
            value = int.from_bytes(data[offset:offset + 4], endian.value == "little", signed=True)
            return ParsedField("int32", type, value, offset, 4, endian)

        elif type == BasicType.UINT64:
            if remaining < 8:
                return None
            value = int.from_bytes(data[offset:offset + 8], endian.value == "little")
            return ParsedField("uint64", type, value, offset, 8, endian)

        elif type == BasicType.INT64:
            if remaining < 8:
                return None
            value = int.from_bytes(data[offset:offset + 8], endian.value == "little", signed=True)
            return ParsedField("int64", type, value, offset, 8, endian)

        elif type == BasicType.FLOAT32:
            if remaining < 4:
                return None
            import struct
            fmt = "<f" if endian == Endianness.LITTLE else ">f"
            value = struct.unpack(fmt, data[offset:offset + 4])[0]
            return ParsedField("float32", type, value, offset, 4, endian)

        elif type == BasicType.FLOAT64:
            if remaining < 8:
                return None
            import struct
            fmt = "<d" if endian == Endianness.LITTLE else ">d"
            value = struct.unpack(fmt, data[offset:offset + 8])[0]
            return ParsedField("float64", type, value, offset, 8, endian)

        elif type == BasicType.CHAR:
            if remaining < 1:
                return None
            value = chr(data[offset]) if data[offset] < 128 else '?'
            return ParsedField("char", type, value, offset, 1, endian)

        elif type == BasicType.BYTE:
            if remaining < 1:
                return None
            value = data[offset]
            return ParsedField("byte", type, value, offset, 1, endian)

        elif type == BasicType.BOOL:
            if remaining < 1:
                return None
            value = data[offset] != 0
            return ParsedField("bool", type, value, offset, 1, endian)

        elif type == BasicType.STRING or type == BasicType.RAW:
            if length > 0:
                data_len = min(length, remaining)
            else:
                # Find null terminator
                data_len = 0
                for i in range(remaining):
                    if data[offset + i] == 0:
                        data_len = i
                        break
                if data_len == 0:
                    data_len = remaining
            value = data[offset:offset + data_len]
            if type == BasicType.STRING:
                try:
                    value = value.decode('utf-8').rstrip('\x00')
                except:
                    value = value.decode('latin-1')
            return ParsedField("string", type, value, offset, data_len, endian)

        return None

    def parse_uint8(self, data: bytes, offset: int) -> Optional[int]:
        """Parse uint8."""
        if offset + 1 > len(data):
            return None
        return data[offset]

    def parse_uint16(self, data: bytes, offset: int) -> Optional[int]:
        """Parse uint16."""
        if offset + 2 > len(data):
            return None
        return int.from_bytes(data[offset:offset + 2],
                              self._endianness == Endianness.LITTLE)

    def parse_uint32(self, data: bytes, offset: int) -> Optional[int]:
        """Parse uint32."""
        if offset + 4 > len(data):
            return None
        return int.from_bytes(data[offset:offset + 4],
                              self._endianness == Endianness.LITTLE)

    def parse_uint64(self, data: bytes, offset: int) -> Optional[int]:
        """Parse uint64."""
        if offset + 8 > len(data):
            return None
        return int.from_bytes(data[offset:offset + 8],
                              self._endianness == Endianness.LITTLE)

    def parse_int8(self, data: bytes, offset: int) -> Optional[int]:
        """Parse int8."""
        value = self.parse_uint8(data, offset)
        if value is not None and value > 127:
            return value - 256
        return value

    def parse_float32(self, data: bytes, offset: int) -> Optional[float]:
        """Parse float32."""
        import struct
        if offset + 4 > len(data):
            return None
        fmt = "<f" if self._endianness == Endianness.LITTLE else ">f"
        return struct.unpack(fmt, data[offset:offset + 4])[0]

    def parse_float64(self, data: bytes, offset: int) -> Optional[float]:
        """Parse float64."""
        import struct
        if offset + 8 > len(data):
            return None
        fmt = "<d" if self._endianness == Endianness.LITTLE else ">d"
        return struct.unpack(fmt, data[offset:offset + 8])[0]

    def parse_string(self, data: bytes, offset: int, length: int = 0,
                    encoding: str = "utf-8") -> Optional[str]:
        """Parse string."""
        if offset >= len(data):
            return None

        if length > 0:
            end = min(offset + length, len(data))
        else:
            end = len(data)
            for i in range(offset, len(data)):
                if data[i] == 0:
                    end = i
                    break

        try:
            return data[offset:end].decode(encoding).rstrip('\x00')
        except:
            return data[offset:end].decode('latin-1').rstrip('\x00')

    def parse_bytes(self, data: bytes, offset: int, length: int) -> Optional[bytes]:
        """Parse raw bytes."""
        if offset + length > len(data):
            return None
        return data[offset:offset + length]
