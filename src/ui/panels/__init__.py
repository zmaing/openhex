"""
Panels Package

Panel components for openhex.
"""

from .file_browser import FileBrowser
from .file_info import FileInfoPanel
from .data_value import DataValuePanel
from .bookmarks import BookmarksPanel
from .structure_view import StructureViewPanel
from .ai_agent import AIAgentPanel

__all__ = [
    "FileBrowser",
    "FileInfoPanel",
    "DataValuePanel",
    "BookmarksPanel",
    "StructureViewPanel",
    "AIAgentPanel",
]
