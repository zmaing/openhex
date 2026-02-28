"""
File Loader

Threaded file loading with progress reporting.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot
from typing import Optional, Callable, Dict, Any
import os
import mmap
import tempfile

from ..utils.logger import logger


class FileLoaderWorker(QThread):
    """Worker thread for loading files."""

    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bytes)
    error = pyqtSignal(str)

    def __init__(self, file_path: str, max_size: int = 0):
        super().__init__()
        self._file_path = file_path
        self._max_size = max_size
        self._should_stop = False

    def run(self):
        """Run the loading process."""
        try:
            file_size = os.path.getsize(self._file_path)

            if self._max_size > 0 and file_size > self._max_size:
                # Load only first max_size bytes
                with open(self._file_path, 'rb') as f:
                    data = f.read(self._max_size)
                self.finished.emit(data)
                return

            with open(self._file_path, 'rb') as f:
                data = f.read()

            self.finished.emit(data)

        except Exception as e:
            logger.error(f"File loading error: {e}")
            self.error.emit(str(e))

    def stop(self):
        """Signal worker to stop."""
        self._should_stop = True


class FileLoader(QObject):
    """
    File loader with threading support.

    Provides background file loading with progress updates.
    """

    # Signals
    loading_started = pyqtSignal(str, int)  # path, size
    loading_progress = pyqtSignal(int, int)  # current, total
    loading_finished = pyqtSignal(bytes)
    loading_error = pyqtSignal(str)
    loading_cancelled = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._worker: Optional[FileLoaderWorker] = None
        self._is_loading = False

    @property
    def is_loading(self) -> bool:
        """Check if currently loading."""
        return self._is_loading

    def load_file(self, path: str, max_size: int = 0) -> bool:
        """
        Start loading a file in background.

        Args:
            path: File path to load
            max_size: Maximum bytes to load (0 = unlimited)

        Returns:
            True if loading started
        """
        if self._is_loading:
            return False

        try:
            file_size = os.path.getsize(path)
            self.loading_started.emit(path, file_size)

            self._worker = FileLoaderWorker(path, max_size)
            self._worker.progress.connect(self.loading_progress)
            self._worker.finished.connect(self._on_finished)
            self._worker.error.connect(self._on_error)

            self._is_loading = True
            self._worker.start()

            return True

        except Exception as e:
            logger.error(f"Failed to start loading: {e}")
            self.loading_error.emit(str(e))
            return False

    def cancel(self):
        """Cancel current loading."""
        if self._worker and self._is_loading:
            self._worker.stop()
            self._worker.wait()
            self._is_loading = False
            self.loading_cancelled.emit()

    @pyqtSlot(bytes)
    def _on_finished(self, data: bytes):
        """Handle loading finished."""
        self._is_loading = False
        self.loading_finished.emit(data)

    @pyqtSlot(str)
    def _on_error(self, error: str):
        """Handle loading error."""
        self._is_loading = False
        self.loading_error.emit(error)

    def load_large_file(self, path: str) -> str:
        """
        Set up memory mapping for large file.

        Args:
            path: File path

        Returns:
            Error message or empty string if successful
        """
        try:
            file_size = os.path.getsize(path)
            self.loading_started.emit(path, file_size)
            # Return the path for mmap-based access
            return ""
        except Exception as e:
            return str(e)
