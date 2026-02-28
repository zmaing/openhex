"""
Format Utilities

Formatting functions for sizes, offsets, etc.
"""

from typing import Optional


class FormatUtils:
    """Formatting utilities."""

    SIZE_SUFFIXES = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']

    @staticmethod
    def format_size(size: int, precision: int = 2) -> str:
        """
        Format byte size to human-readable string.

        Args:
            size: Size in bytes
            precision: Decimal places

        Returns:
            Formatted size string
        """
        if size < 0:
            return "0 B"

        for suffix in FormatUtils.SIZE_SUFFIXES:
            if size < 1024:
                if suffix == 'B':
                    return f"{size} {suffix}"
                return f"{size:.{precision}f} {suffix}"
            size /= 1024

        return f"{size:.{precision}f} PB"

    @staticmethod
    def parse_size(size_str: str) -> int:
        """
        Parse size string to bytes.

        Args:
            size_str: Size string (e.g., "1.5 MB")

        Returns:
            Size in bytes
        """
        size_str = size_str.strip().upper()

        parts = size_str.split()
        if len(parts) == 1:
            parts.append('B')

        value = float(parts[0])
        suffix = parts[1]

        suffixes = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4,
            'PB': 1024 ** 5,
        }

        multiplier = suffixes.get(suffix, 1)
        return int(value * multiplier)

    @staticmethod
    def format_offset(offset: int, uppercase: bool = True) -> str:
        """
        Format offset as hex.

        Args:
            offset: Byte offset
            uppercase: Use uppercase hex

        Returns:
            Formatted offset string
        """
        prefix = "0x" if uppercase else "0x"
        fmt = "X" if uppercase else "x"
        return f"{prefix}{offset:{fmt}}"

    @staticmethod
    def format_hex(data: bytes, group_size: int = 2,
                   groups_per_line: int = 8) -> str:
        """
        Format bytes as hex string.

        Args:
            data: Bytes to format
            group_size: Bytes per group
            groups_per_line: Groups per line

        Returns:
            Formatted hex string
        """
        hex_chars = data.hex()
        if group_size == 2:
            # Standard hex with spaces
            hex_str = ' '.join(hex_chars[i:i+2] for i in range(0, len(hex_chars), 2))
        else:
            # Custom grouping
            hex_str = ' '.join(hex_chars[i:i+group_size] for i in range(0, len(hex_chars), group_size))

        # Add line breaks
        groups = hex_str.split(' ')
        lines = [' '.join(groups[i:i+groups_per_line]) for i in range(0, len(groups), groups_per_line)]

        return '\n'.join(lines)

    @staticmethod
    def format_ascii(data: bytes, non_printable: str = '.') -> str:
        """
        Format bytes as ASCII representation.

        Args:
            data: Bytes to format
            non_printable: Character for non-printable bytes

        Returns:
            ASCII string
        """
        return ''.join(
            chr(b) if 32 <= b < 127 else non_printable
            for b in data
        )

    @staticmethod
    def format_binary(data: bytes, group_size: int = 4) -> str:
        """
        Format bytes as binary string.

        Args:
            data: Bytes to format
            group_size: Bits per group

        Returns:
            Formatted binary string
        """
        binary = ''.join(f'{b:08b}' for b in data)
        return ' '.join(
            binary[i:i+group_size]
            for i in range(0, len(binary), group_size)
        )

    @staticmethod
    def format_percent(value: float, total: float,
                       precision: int = 1) -> str:
        """
        Format as percentage.

        Args:
            value: Current value
            total: Total value
            precision: Decimal places

        Returns:
            Percentage string
        """
        if total == 0:
            return "0%"
        percent = (value / total) * 100
        return f"{percent:.{precision}f}%"

    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 0.001:
            return f"{seconds * 1000000:.0f} μs"
        elif seconds < 1:
            return f"{seconds * 1000:.0f} ms"
        elif seconds < 60:
            return f"{seconds:.2f} s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    @staticmethod
    def format_rate(bytes_per_second: float) -> str:
        """
        Format transfer rate.

        Args:
            bytes_per_second: Rate in bytes/second

        Returns:
            Formatted rate string
        """
        return f"{FormatUtils.format_size(int(bytes_per_second))}/s"
