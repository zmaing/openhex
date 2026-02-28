"""
Encoding Detector

Text encoding detection utilities.
"""

from typing import Optional, List, Tuple

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False


class EncodingDetector:
    """
    Text encoding detector.
    """

    # Common encodings to check
    COMMON_ENCODINGS = [
        'utf-8',
        'utf-16le',
        'utf-16be',
        'latin-1',
        'cp1252',
        'iso-8859-1',
        'ascii',
        'shift_jis',
        'euc-kr',
        'gbk',
        'big5',
    ]

    @staticmethod
    def detect(data: bytes) -> Tuple[str, float]:
        """
        Detect encoding of bytes.

        Args:
            data: Input bytes

        Returns:
            (encoding, confidence)
        """
        if not data:
            return ('utf-8', 1.0)

        # Use chardet if available
        if HAS_CHARDET:
            try:
                result = chardet.detect(data)
                return result.get('encoding', 'utf-8'), result.get('confidence', 0.0)
            except:
                pass

        # Fallback: check for BOM
        if data.startswith(b'\xef\xbb\xbf'):
            return ('utf-8', 1.0)
        elif data.startswith(b'\xff\xfe'):
            return ('utf-16le', 1.0)
        elif data.startswith(b'\xfe\xff'):
            return ('utf-16be', 1.0)

        return ('utf-8', 0.0)

    @staticmethod
    def decode(data: bytes, encoding: Optional[str] = None) -> str:
        """
        Decode bytes to string.

        Args:
            data: Input bytes
            encoding: Specific encoding or auto-detect

        Returns:
            Decoded string
        """
        if encoding:
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                pass

        # Auto-detect
        enc, _ = EncodingDetector.detect(data)
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            # Fallback to latin-1 which never fails
            return data.decode('latin-1')

    @staticmethod
    def is_text(data: bytes, threshold: float = 0.7) -> bool:
        """
        Check if bytes are likely text.

        Args:
            data: Input bytes
            threshold: Minimum printable ratio

        Returns:
            True if likely text
        """
        if not data:
            return False

        printable = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
        ratio = printable / len(data)
        return ratio >= threshold

    @staticmethod
    def get_common_encodings() -> List[str]:
        """Get list of common encodings."""
        return EncodingDetector.COMMON_ENCODINGS.copy()
