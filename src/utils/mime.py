"""
MIME Type Detector

File type detection based on magic bytes.
"""

import os
from typing import Optional, Dict, Tuple


class MimeTypeDetector:
    """
    MIME type detector using magic bytes.
    """

    # Magic byte signatures
    SIGNATURES: Dict[bytes, Tuple[str, str]] = {
        b'\x7fELF': ('elf', 'application/x-executable'),
        b'MZ': ('pe', 'application/x-dosexec'),
        b'\x89PNG\r\n\x1a\n': ('png', 'image/png'),
        b'\xff\xd8\xff': ('jpeg', 'image/jpeg'),
        b'GIF87a': ('gif', 'image/gif'),
        b'GIF89a': ('gif', 'image/gif'),
        b'%PDF': ('pdf', 'application/pdf'),
        b'PK\x03\x04': ('zip', 'application/zip'),
        b'PK\x05\x06': ('zip', 'application/zip'),
        b'\x1f\x8b': ('gzip', 'application/gzip'),
        b'Rar!\x1a\x07': ('rar', 'application/x-rar-compressed'),
        b'\x1f\x9d': ('compress', 'application/x-compress'),
        b'\x1fa\x8b': ('compress', 'application/x-compress'),
        b'<!DOCTYPE': ('html', 'text/html'),
        b'<html': ('html', 'text/html'),
        b'{\\r\\n"': ('json', 'application/json'),
        b'{\\n"': ('json', 'application/json'),
        b'<?xml': ('xml', 'application/xml'),
        b'<': ('xml', 'application/xml'),
        b'<?php': ('php', 'application/x-php'),
        b'\xca\xfe\xba\xbe': ('java', 'application/java'),
        b'dex\n': ('dex', 'application/x-dex'),
        b'\x00\x00\x00': ('mp4', 'video/mp4'),  # MP4 with extra check
        b'ftyp': ('mp4', 'video/mp4'),
        b'OggS': ('ogg', 'audio/ogg'),
        b'ID3': ('mp3', 'audio/mpeg'),  # ID3v2 tag
        b'\xff\xfb': ('mp3', 'audio/mpeg'),  # MP3 frame
        b'\xff\xfa': ('mp3', 'audio/mpeg'),
        b'\xff\xf3': ('mp3', 'audio/mpeg'),
        b'\xff\xf2': ('mp3', 'audio/mpeg'),
        b'SQLite format 3': ('sqlite', 'application/x-sqlite3'),
    }

    @classmethod
    def detect(cls, data: bytes) -> Tuple[str, str]:
        """
        Detect MIME type from data.

        Args:
            data: File content

        Returns:
            (file_type, mime_type)
        """
        if not data:
            return ('empty', 'application/octet-stream')

        # Check signatures
        for signature, (file_type, mime_type) in cls.SIGNATURES.items():
            if data.startswith(signature):
                return (file_type, mime_type)

        # Additional checks for specific formats
        if len(data) >= 8:
            # MP4 check
            if data[4:8] == b'ftyp':
                return ('mp4', 'video/mp4')

            # Check for RIFF
            if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                return ('webp', 'image/webp')

        # Text detection
        if cls._is_text(data):
            return ('text', 'text/plain')

        return ('binary', 'application/octet-stream')

    @classmethod
    def detect_path(cls, path: str) -> Tuple[str, str]:
        """
        Detect MIME type from file path.

        Args:
            path: File path

        Returns:
            (file_type, mime_type)
        """
        try:
            with open(path, 'rb') as f:
                header = f.read(512)
            return cls.detect(header)
        except:
            ext = os.path.splitext(path)[1].lower()
            return cls._extension_to_mime(ext)

    @classmethod
    def _is_text(cls, data: bytes) -> bool:
        """Check if data is likely text."""
        if not data:
            return False

        # Count printable characters
        printable = sum(1 for b in data if 32 <= b < 127 or b in (9, 10, 13))
        ratio = printable / len(data)
        return ratio > 0.7

    @classmethod
    def _extension_to_mime(cls, ext: str) -> Tuple[str, str]:
        """Convert extension to MIME type."""
        mime_map = {
            '.txt': ('text', 'text/plain'),
            '.py': ('python', 'text/x-python'),
            '.c': ('c', 'text/x-c'),
            '.cpp': ('cpp', 'text/x-c++'),
            '.h': ('c', 'text/x-c'),
            '.hpp': ('cpp', 'text/x-c++'),
            '.js': ('javascript', 'application/javascript'),
            '.html': ('html', 'text/html'),
            '.css': ('css', 'text/css'),
            '.json': ('json', 'application/json'),
            '.xml': ('xml', 'application/xml'),
            '.md': ('markdown', 'text/markdown'),
            '.sh': ('shell', 'application/x-sh'),
            '.exe': ('pe', 'application/x-dosexec'),
            '.dll': ('pe', 'application/x-dll'),
            '.so': ('elf', 'application/x-sharedlib'),
            '.dylib': ('macho', 'application/x-dylib'),
        }

        return mime_map.get(ext, ('unknown', 'application/octet-stream'))

    @classmethod
    def is_executable(cls, file_type: str) -> bool:
        """Check if file type is executable."""
        return file_type in ('elf', 'pe', 'macho')

    @classmethod
    def is_archive(cls, file_type: str) -> bool:
        """Check if file type is archive."""
        return file_type in ('zip', 'rar', 'gzip', 'compress')
