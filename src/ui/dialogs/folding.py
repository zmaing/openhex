"""
Folding Manager

折叠区域管理器
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import List, Tuple, Optional


class FoldRegion:
    """Represents a foldable region."""

    def __init__(self, start: int, end: int, label: str = ""):
        self.start = start
        self.end = end
        self.label = label
        self.is_folded = False

    @property
    def length(self) -> int:
        return self.end - self.start

    def contains(self, offset: int) -> bool:
        return self.start <= offset < self.end


class FoldingManager(QObject):
    """
    Folding manager.

    Manages foldable regions in hex view.
    """

    # Signals
    folding_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._regions: List[FoldRegion] = []
        self._data_length = 0

    def set_data_length(self, length: int):
        """Set data length for auto-detection."""
        self._data_length = length

    def add_region(self, start: int, end: int, label: str = ""):
        """Add a fold region."""
        # Check for overlap
        for region in self._regions:
            if region.start < end and region.end > start:
                return False  # Overlap detected

        region = FoldRegion(start, end, label)
        self._regions.append(region)
        self._regions.sort(key=lambda r: r.start)
        self.folding_changed.emit()
        return True

    def remove_region(self, start: int, end: int):
        """Remove a fold region."""
        self._regions = [r for r in self._regions
                        if not (r.start == start and r.end == end)]
        self.folding_changed.emit()

    def toggle_region(self, start: int):
        """Toggle fold state at offset."""
        for region in self._regions:
            if region.contains(start):
                region.is_folded = not region.is_folded
                self.folding_changed.emit()
                return True
        return False

    def fold_at(self, offset: int):
        """Fold region containing offset."""
        for region in self._regions:
            if region.contains(offset):
                region.is_folded = True
                self.folding_changed.emit()
                return True
        return False

    def unfold_at(self, offset: int):
        """Unfold region containing offset."""
        for region in self._regions:
            if region.contains(offset):
                region.is_folded = False
                self.folding_changed.emit()
                return True
        return False

    def fold_all(self):
        """Fold all regions."""
        for region in self._regions:
            region.is_folded = True
        self.folding_changed.emit()

    def unfold_all(self):
        """Unfold all regions."""
        for region in self._regions:
            region.is_folded = False
        self.folding_changed.emit()

    def get_regions(self) -> List[FoldRegion]:
        """Get all regions."""
        return self._regions.copy()

    def get_visible_offsets(self) -> List[Tuple[int, int]]:
        """Get visible offset ranges (considering folds)."""
        result = []
        current = 0

        for region in self._regions:
            if region.start > current:
                result.append((current, region.start))

            if not region.is_folded:
                result.append((region.start, region.end))

            current = region.end

        # Add remaining
        if current < self._data_length:
            result.append((current, self._data_length))

        return result

    def auto_detect_regions(self, data: bytes):
        """Auto-detect foldable regions."""
        self._regions.clear()

        if len(data) < 16:
            return

        # Detect string regions (consecutive printable ASCII)
        in_string = False
        string_start = 0

        for i in range(len(data)):
            byte = data[i]
            is_printable = 32 <= byte < 127

            if is_printable and not in_string:
                # Start of potential string
                in_string = True
                string_start = i
            elif not is_printable and in_string:
                # End of string - if long enough, add as region
                if i - string_start >= 4:
                    self.add_region(string_start, i, f"String @ 0x{string_start:X}")
                in_string = False

        # Handle string at end of data
        if in_string and len(data) - string_start >= 4:
            self.add_region(string_start, len(data), f"String @ 0x{string_start:X}")

        self.folding_changed.emit()

    def clear(self):
        """Clear all regions."""
        self._regions.clear()
        self.folding_changed.emit()
