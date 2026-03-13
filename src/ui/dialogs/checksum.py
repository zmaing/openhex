"""
Checksum Dialog

计算文件校验和
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QProgressBar, QCheckBox,
                             QGroupBox, QTextEdit)
from PyQt6.QtCore import QThread, pyqtSignal, Qt

import hashlib
import zlib

from .chrome import create_dialog_header
from ..design_system import build_mono_font


class ChecksumWorker(QThread):
    """Background worker for checksum calculation."""

    progress = pyqtSignal(int, int)  # current, total
    result = pyqtSignal(str, str)  # algorithm, checksum
    finished = pyqtSignal()

    def __init__(self, data, algorithms):
        super().__init__()
        self._data = data
        self._algorithms = algorithms

    def run(self):
        """Calculate checksums."""
        total = len(self._algorithms)
        for i, algo in enumerate(self._algorithms):
            checksum = self._calculate(algo)
            self.result.emit(algo, checksum)
            self.progress.emit(i + 1, total)
        self.finished.emit()

    def _calculate(self, algo):
        """Calculate checksum for algorithm."""
        if algo == "MD5":
            return hashlib.md5(self._data).hexdigest()
        elif algo == "SHA1":
            return hashlib.sha1(self._data).hexdigest()
        elif algo == "SHA256":
            return hashlib.sha256(self._data).hexdigest()
        elif algo == "SHA512":
            return hashlib.sha512(self._data).hexdigest()
        elif algo == "CRC32":
            return format(zlib.crc32(self._data) & 0xFFFFFFFF, '08x')
        return ""


class ChecksumDialog(QDialog):
    """
    Checksum dialog.

    Calculate file checksums.
    """

    def __init__(self, parent=None, file_path=None, file_size=0):
        super().__init__(parent)
        self._file_path = file_path
        self._file_size = file_size
        self._worker = None
        self._results = {}
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("Calculate Checksum")
        self.resize(560, 470)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            create_dialog_header(
                "Calculate Checksum",
                "统一展示文件摘要算法、进度反馈和结果输出，减少传统工具弹窗的割裂感。",
            )
        )

        # File info
        info_group = QGroupBox("File Information")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)

        if self._file_path:
            from pathlib import Path
            filename = Path(self._file_path).name
            info_layout.addWidget(QLabel(f"File: {filename}"))
            info_layout.addWidget(QLabel(f"Size: {self._format_size(self._file_size)}"))
        else:
            info_layout.addWidget(QLabel("No file loaded"))

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Algorithm selection
        algo_group = QGroupBox("Algorithms")
        algo_layout = QVBoxLayout()
        algo_layout.setSpacing(8)

        self._md5_check = QCheckBox("MD5")
        self._md5_check.setChecked(True)
        algo_layout.addWidget(self._md5_check)

        self._sha1_check = QCheckBox("SHA1")
        self._sha1_check.setChecked(True)
        algo_layout.addWidget(self._sha1_check)

        self._sha256_check = QCheckBox("SHA256")
        self._sha256_check.setChecked(True)
        algo_layout.addWidget(self._sha256_check)

        self._sha512_check = QCheckBox("SHA512")
        algo_layout.addWidget(self._sha512_check)

        self._crc32_check = QCheckBox("CRC32")
        self._crc32_check.setChecked(True)
        algo_layout.addWidget(self._crc32_check)

        algo_group.setLayout(algo_layout)
        layout.addWidget(algo_group)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Results
        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setFont(build_mono_font(10))
        layout.addWidget(self._results_text)

        # Buttons
        btn_layout = QHBoxLayout()

        calculate_btn = QPushButton("Calculate")
        calculate_btn.clicked.connect(self._on_calculate)
        btn_layout.addWidget(calculate_btn)

        copy_btn = QPushButton("Copy All")
        copy_btn.clicked.connect(self._on_copy)
        btn_layout.addWidget(copy_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _format_size(self, size):
        """Format file size."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def _on_calculate(self):
        """Calculate checksums."""
        if not self._file_path:
            return

        # Get selected algorithms
        algorithms = []
        if self._md5_check.isChecked():
            algorithms.append("MD5")
        if self._sha1_check.isChecked():
            algorithms.append("SHA1")
        if self._sha256_check.isChecked():
            algorithms.append("SHA256")
        if self._sha512_check.isChecked():
            algorithms.append("SHA512")
        if self._crc32_check.isChecked():
            algorithms.append("CRC32")

        if not algorithms:
            return

        # Read file
        try:
            with open(self._file_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            self._results_text.setPlainText(f"Error reading file: {e}")
            return

        # Disable calculate button
        self._progress.setVisible(True)
        self._progress.setMaximum(len(algorithms))
        self._progress.setValue(0)
        self._results_text.setPlainText("Calculating...")

        # Start worker
        self._worker = ChecksumWorker(data, algorithms)
        self._worker.progress.connect(self._on_progress)
        self._worker.result.connect(self._on_result)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current, total):
        """Handle progress update."""
        self._progress.setValue(current)

    def _on_result(self, algo, checksum):
        """Handle result."""
        self._results[algo] = checksum

    def _on_finished(self):
        """Handle calculation finished."""
        # Display results
        text = ""
        for algo, checksum in self._results.items():
            text += f"{algo}: {checksum}\n"

        self._results_text.setPlainText(text)
        self._progress.setVisible(False)

    def _on_copy(self):
        """Copy all results to clipboard."""
        text = self._results_text.toPlainText()
        clipboard = self.window().clipboard()
        clipboard.setText(text)
