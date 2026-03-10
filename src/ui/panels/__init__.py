"""
Panels Package

Panel components for openhex.
"""

from .file_browser import FileBrowser
from .file_info import FileInfoPanel
from .data_value import DataValuePanel
from .bookmarks import BookmarksPanel
from .structure_view import StructureViewPanel

__all__ = [
    "FileBrowser",
    "FileInfoPanel",
    "DataValuePanel",
    "BookmarksPanel",
    "StructureViewPanel",
]
