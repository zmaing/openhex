"""
Document Model

Manages multiple open files and their state.
"""

import os

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Optional, List, Dict, Any

from .file_handle import FileHandle, FileState


def _normalize_document_path(path: str | None) -> str:
    """Return a normalized absolute path for document lookups."""
    if not path:
        return ""
    return os.path.abspath(path)


def _paths_match(left: str | None, right: str | None) -> bool:
    """Check whether two paths refer to the same on-disk file."""
    if not left or not right:
        return False

    try:
        return os.path.samefile(left, right)
    except (FileNotFoundError, OSError, ValueError):
        return _normalize_document_path(left) == _normalize_document_path(right)


class DocumentModel(QObject):
    """
    Document model for managing multiple open files.

    Acts as a collection of FileHandle objects with tab-based organization.
    """

    # Signals
    document_opened = pyqtSignal(FileHandle)
    document_closed = pyqtSignal(FileHandle)
    document_changed = pyqtSignal(FileHandle)  # Current document changed
    document_modified = pyqtSignal(FileHandle)  # Document was modified
    documents_changed = pyqtSignal()  # Documents list changed

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._documents: List[FileHandle] = []
        self._current_index: int = -1
        self._modified_count: int = 0

    @property
    def documents(self) -> List[FileHandle]:
        """Get list of all documents."""
        return self._documents.copy()

    @property
    def current_document(self) -> Optional[FileHandle]:
        """Get current document."""
        if 0 <= self._current_index < len(self._documents):
            return self._documents[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        """Get current document index."""
        return self._current_index

    @property
    def document_count(self) -> int:
        """Get number of open documents."""
        return len(self._documents)

    @property
    def modified_count(self) -> int:
        """Get number of modified documents."""
        return self._modified_count

    @property
    def has_unsaved_changes(self) -> bool:
        """Check if any document has unsaved changes."""
        return self._modified_count > 0

    def open_document(self, path: str) -> Optional[FileHandle]:
        """
        Open a document from path.

        Args:
            path: File path to open

        Returns:
            FileHandle if successful, None otherwise
        """
        normalized_path = _normalize_document_path(path)

        # Check if already open
        for doc in self._documents:
            if _paths_match(doc.file_path, normalized_path):
                self.set_current_document(doc)
                return doc

        # Create new document
        handle = FileHandle()
        if not handle.load_from_path(normalized_path):
            return None

        # Connect signals
        handle.data_changed.connect(self._on_document_data_changed)
        handle.state_changed.connect(self._on_document_state_changed)

        self._documents.append(handle)
        self._current_index = len(self._documents) - 1

        self.documents_changed.emit()
        self.document_opened.emit(handle)
        self.document_changed.emit(handle)

        return handle

    def close_document(self, index: int) -> bool:
        """
        Close document at index.

        Args:
            index: Document index

        Returns:
            True if closed, False if cancelled
        """
        if index < 0 or index >= len(self._documents):
            return True

        doc = self._documents[index]

        # Check for unsaved changes
        if doc.file_state == FileState.MODIFIED:
            from PyQt6.QtWidgets import QMessageBox, QApplication

            reply = QMessageBox.question(
                None,
                "Save Changes",
                f"Save changes to '{doc.file_name}' before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return False
            elif reply == QMessageBox.StandardButton.Yes:
                if not doc.save():
                    return False

        # Clean up
        doc.close()
        self._documents.pop(index)

        # Adjust current index
        if len(self._documents) == 0:
            self._current_index = -1
        elif self._current_index > index:
            self._current_index -= 1
        elif self._current_index >= len(self._documents):
            self._current_index = len(self._documents) - 1

        self.documents_changed.emit()
        self.document_closed.emit(doc)

        if 0 <= self._current_index < len(self._documents):
            self.document_changed.emit(self._documents[self._current_index])

        return True

    def close_document_handle(self, document: Optional[FileHandle]) -> bool:
        """Close the requested document instance if it is still open."""
        if document is None:
            return True

        try:
            index = self._documents.index(document)
        except ValueError:
            return True

        return self.close_document(index)

    def close_current_document(self) -> bool:
        """Close current document."""
        return self.close_document(self._current_index)

    def close_all_documents(self) -> bool:
        """
        Close all documents.

        Returns:
            True if all closed, False if cancelled
        """
        while self._documents:
            if not self.close_document(0):
                return False
        return True

    def set_current_document(self, document: FileHandle):
        """
        Set current document.

        Args:
            document: Document to set as current
        """
        try:
            index = self._documents.index(document)
            if index != self._current_index:
                self._current_index = index
                self.document_changed.emit(document)
        except ValueError:
            pass

    def set_current_index(self, index: int):
        """
        Set current document by index.

        Args:
            index: Document index
        """
        if 0 <= index < len(self._documents):
            self._current_index = index
            self.document_changed.emit(self._documents[index])

    def get_document(self, index: int) -> Optional[FileHandle]:
        """
        Get document at index.

        Args:
            index: Document index

        Returns:
            FileHandle or None
        """
        if 0 <= index < len(self._documents):
            return self._documents[index]
        return None

    def get_document_by_path(self, path: str) -> Optional[FileHandle]:
        """
        Get document by file path.

        Args:
            path: File path

        Returns:
            FileHandle or None
        """
        normalized_path = _normalize_document_path(path)
        for doc in self._documents:
            if _paths_match(doc.file_path, normalized_path):
                return doc
        return None

    def save_current_document(self, path: Optional[str] = None) -> bool:
        """
        Save current document.

        Args:
            path: Optional new path

        Returns:
            True if successful
        """
        doc = self.current_document
        if not doc:
            return False
        return doc.save(path)

    def new_document(self) -> FileHandle:
        """
        Create new empty document.

        Returns:
            New FileHandle
        """
        handle = FileHandle()
        handle.file_path = None
        handle.file_name = "Untitled"
        handle.file_state = FileState.NEW

        # Connect signals
        handle.data_changed.connect(self._on_document_data_changed)
        handle.state_changed.connect(self._on_document_state_changed)

        self._documents.append(handle)
        self._current_index = len(self._documents) - 1

        self.documents_changed.emit()
        self.document_opened.emit(handle)
        self.document_changed.emit(handle)

        return handle

    def move_document(self, from_index: int, to_index: int) -> bool:
        """
        Move document from one position to another.

        Args:
            from_index: Source index
            to_index: Destination index

        Returns:
            True if successful
        """
        if not (0 <= from_index < len(self._documents)):
            return False
        if not (0 <= to_index < len(self._documents)):
            return False

        doc = self._documents.pop(from_index)
        self._documents.insert(to_index, doc)

        if self._current_index == from_index:
            self._current_index = to_index

        self.documents_changed.emit()
        return True

    def get_modified_documents(self) -> List[FileHandle]:
        """Get list of modified documents."""
        return [doc for doc in self._documents if doc.file_state == FileState.MODIFIED]

    def save_all(self) -> bool:
        """
        Save all modified documents.

        Returns:
            True if all saved successfully
        """
        success = True
        for doc in self.get_modified_documents():
            if not doc.save():
                success = False
        return success

    def _on_document_data_changed(self, start: int, end: int):
        """Handle document data change."""
        doc = self.sender()
        if doc:
            self.document_modified.emit(doc)

    def _on_document_state_changed(self, state: FileState):
        """Handle document state change."""
        doc = self.sender()
        if not doc:
            return

        # Update modified count
        if state == FileState.MODIFIED:
            self._modified_count += 1
        elif state == FileState.UNCHANGED:
            self._modified_count = max(0, self._modified_count - 1)

        self.document_modified.emit(doc)

    def clear(self):
        """Clear all documents."""
        for doc in self._documents:
            doc.close()
        self._documents.clear()
        self._current_index = -1
        self._modified_count = 0
        self.documents_changed.emit()

    def __len__(self):
        """Return number of documents."""
        return len(self._documents)

    def __getitem__(self, index: int) -> FileHandle:
        """Get document at index."""
        return self._documents[index]

    def __iter__(self):
        """Iterate over documents."""
        return iter(self._documents)
