"""
Multi-View Manager

多视图管理器 - 同步多个视图
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Optional, Callable


class ViewSyncManager(QObject):
    """
    Multi-view synchronization manager.

    Manages synchronized scrolling between multiple views.
    """

    # Signals
    scroll_changed = pyqtSignal(int, int)  # x, y offset
    cursor_changed = pyqtSignal(int)  # cursor offset

    def __init__(self, parent=None):
        super().__init__(parent)
        self._views: List[QObject] = []
        self._sync_enabled = True
        self._sync_horizontal = True
        self._sync_vertical = True
        self._sync_cursor = True

    def add_view(self, view: QObject):
        """Add a view to synchronize."""
        if view not in self._views:
            self._views.append(view)

    def remove_view(self, view: QObject):
        """Remove a view from synchronization."""
        if view in self._views:
            self._views.remove(view)

    def clear_views(self):
        """Remove all views."""
        self._views.clear()

    @property
    def sync_enabled(self) -> bool:
        """Get sync enabled state."""
        return self._sync_enabled

    @sync_enabled.setter
    def sync_enabled(self, value: bool):
        """Set sync enabled state."""
        self._sync_enabled = value

    @property
    def sync_horizontal(self) -> bool:
        """Get horizontal sync state."""
        return self._sync_horizontal

    @sync_horizontal.setter
    def sync_horizontal(self, value: bool):
        """Set horizontal sync state."""
        self._sync_horizontal = value

    @property
    def sync_vertical(self) -> bool:
        """Get vertical sync state."""
        return self._sync_vertical

    @sync_vertical.setter
    def sync_vertical(self, value: bool):
        """Set vertical sync state."""
        self._sync_vertical = value

    @property
    def sync_cursor(self) -> bool:
        """Get cursor sync state."""
        return self._sync_cursor

    @sync_cursor.setter
    def sync_cursor(self, value: bool):
        """Set cursor sync state."""
        self._sync_cursor = value

    def on_view_scroll(self, source_view: QObject, x: int, y: int):
        """Handle scroll event from a view."""
        if not self._sync_enabled:
            return

        # Notify all other views
        for view in self._views:
            if view is not source_view:
                self._sync_scroll(view, x, y)

    def on_cursor_changed(self, source_view: QObject, offset: int):
        """Handle cursor change from a view."""
        if not self._sync_enabled or not self._sync_cursor:
            return

        # Notify all other views
        for view in self._views:
            if view is not source_view:
                self._sync_cursor(view, offset)

    def _sync_scroll(self, view: QObject, x: int, y: int):
        """Sync scroll to a view."""
        if hasattr(view, 'scroll_to'):
            if self._sync_horizontal and self._sync_vertical:
                view.scroll_to(x, y)
            elif self._sync_vertical:
                view.scroll_to_y(y)
            elif self._sync_horizontal:
                view.scroll_to_x(x)

    def _sync_cursor(self, view: QObject, offset: int):
        """Sync cursor to a view."""
        if hasattr(view, 'go_to_offset'):
            view.go_to_offset(offset)

    @property
    def view_count(self) -> int:
        """Get number of synchronized views."""
        return len(self._views)
