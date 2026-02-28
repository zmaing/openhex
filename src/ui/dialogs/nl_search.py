"""
Natural Language Search Dialog

自然语言搜索对话框
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QProgressBar, QTextEdit,
                             QGroupBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont


class NaturalLanguageSearchWorker(QThread):
    """Background worker for natural language search."""

    progress = pyqtSignal(int, int)  # current, total
    result = pyqtSignal(object)  # SearchHit
    finished = pyqtSignal(list)  # all results
    error = pyqtSignal(str)

    def __init__(self, ai_manager, data, query):
        super().__init__()
        self._ai_manager = ai_manager
        self._data = data
        self._query = query

    def run(self):
        """Run search."""
        try:
            # Import AI search
            from ...ai.search import AISearch

            search = AISearch()
            search.set_provider(self._ai_manager._current_ai)

            # Connect signals
            search.search_progress.connect(self._on_progress)
            search.search_hit.connect(self._on_hit)

            # Run search
            results = search.search(self._query, self._data)
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, current, total):
        self.progress.emit(current, total)

    def _on_hit(self, hit):
        self.result.emit(hit)


class NaturalLanguageSearchDialog(QDialog):
    """
    Natural language search dialog.

    Search using natural language queries.
    """

    def __init__(self, parent=None, ai_manager=None, data=None):
        super().__init__(parent)
        self._ai_manager = ai_manager
        self._data = data
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("Natural Language Search")
        self.resize(600, 500)

        layout = QVBoxLayout()

        # Query input
        layout.addWidget(QLabel("Search Query:"))
        self._query_input = QLineEdit()
        self._query_input.setPlaceholderText('e.g., "find all IP addresses", "search for email addresses"')
        layout.addWidget(self._query_input)

        # Quick suggestions
        suggestions_group = QGroupBox("Quick Suggestions")
        suggestions_layout = QHBoxLayout()

        suggestions = [
            "IP addresses",
            "Email addresses",
            "URLs",
            "Phone numbers",
            "Dates"
        ]

        for suggestion in suggestions:
            btn = QPushButton(suggestion)
            btn.clicked.connect(lambda checked, s=suggestion: self._query_input.setText(s))
            suggestions_layout.addWidget(btn)

        suggestions_layout.addStretch()
        suggestions_group.setLayout(suggestions_layout)
        layout.addWidget(suggestions_group)

        # Search button
        btn_layout = QHBoxLayout()
        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_search)
        btn_layout.addWidget(self._search_btn)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        btn_layout.addWidget(self._progress)

        layout.addLayout(btn_layout)

        # Results
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout()

        self._results_count = QLabel("No results")
        results_layout.addWidget(self._results_count)

        self._results_text = QTextEdit()
        self._results_text.setReadOnly(True)
        self._results_text.setFont(QFont("Monospace", 10))
        results_layout.addWidget(self._results_text)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        # Buttons
        close_layout = QHBoxLayout()
        close_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_layout.addWidget(close_btn)

        layout.addLayout(close_layout)

        self.setLayout(layout)

    def set_data(self, data):
        """Set data to search."""
        self._data = data

    def set_ai_manager(self, ai_manager):
        """Set AI manager."""
        self._ai_manager = ai_manager

    def _on_search(self):
        """Start search."""
        query = self._query_input.text().strip()
        if not query:
            return

        if not self._data or not self._ai_manager:
            self._results_text.setPlainText("AI not configured or no data")
            return

        # Disable search button
        self._search_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._results_text.setPlainText("Searching...")

        # Start worker
        self._worker = NaturalLanguageSearchWorker(self._ai_manager, self._data, query)
        self._worker.progress.connect(self._on_progress)
        self._worker.result.connect(self._on_result)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current, total):
        """Handle progress."""
        if total > 0:
            self._progress.setValue(int(current * 100 / total))

    def _on_result(self, hit):
        """Handle result found."""
        text = self._results_text.toPlainText()
        if text == "Searching...":
            text = ""
        text += f"Found at 0x{hit.offset:X}: {hit.description}\n"
        self._results_text.setPlainText(text)

    def _on_finished(self, results):
        """Handle search finished."""
        self._search_btn.setEnabled(True)
        self._progress.setVisible(False)

        count = len(results) if results else 0
        self._results_count.setText(f"Found {count} result(s)")

        if not results:
            if self._results_text.toPlainText() == "Searching...":
                self._results_text.setPlainText("No results found")

    def _on_error(self, error_msg):
        """Handle error."""
        self._search_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._results_text.setPlainText(f"Error: {error_msg}")
