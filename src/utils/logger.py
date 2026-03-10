"""
Logger

Logging utilities.
"""

import sys
import os
from datetime import datetime
from enum import Enum, auto
from typing import Optional, TextIO


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class Logger:
    """
    Simple logger for openhex.
    """

    _instance: Optional['Logger'] = None

    def __init__(self, name: str = "openhex", level: LogLevel = LogLevel.INFO):
        Logger._instance = self
        self._name = name
        self._level = level
        self._log_file: Optional[TextIO] = None

        # Create logs directory
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        os.makedirs(logs_dir, exist_ok=True)

    @classmethod
    def instance(cls) -> 'Logger':
        """Get logger instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_level(self, level: LogLevel):
        """Set log level."""
        self._level = level

    def _format_message(self, level: LogLevel, message: str) -> str:
        """Format log message."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level_name = level.name[:4].upper()
        return f"[{timestamp}] [{level_name}] [{self._name}] {message}"

    def _write(self, level: LogLevel, message: str, *args, **kwargs):
        """Write log message."""
        if level.value < self._level.value:
            return

        formatted = self._format_message(level, message)
        if args:
            formatted = formatted % args
        if kwargs:
            formatted = formatted % kwargs

        print(formatted)

        # Write to file if set
        if self._log_file:
            print(formatted, file=self._log_file)

    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        self._write(LogLevel.DEBUG, message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        self._write(LogLevel.INFO, message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        self._write(LogLevel.WARNING, message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        self._write(LogLevel.ERROR, message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        self._write(LogLevel.CRITICAL, message, *args, **kwargs)

    def log_exception(self, exception: Exception, message: str = "Exception occurred"):
        """Log exception with traceback."""
        import traceback
        self.error(f"{message}: {exception}")
        self.debug(traceback.format_exc())

    def start_file_log(self, filename: str = "openhex.log"):
        """Start logging to file."""
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
        path = os.path.join(logs_dir, filename)
        self._log_file = open(path, 'a', encoding='utf-8')
        self.info(f"Logging to {path}")

    def stop_file_log(self):
        """Stop logging to file."""
        if self._log_file:
            self._log_file.close()
            self._log_file = None


# Global logger instance
logger = Logger.instance()
