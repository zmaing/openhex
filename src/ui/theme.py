"""
Theme

Theme management for openhex.
"""

from PyQt6.QtCore import QObject
from typing import Dict, Any
from enum import Enum, auto


class ThemeType(Enum):
    """Theme type enumeration."""
    DARK = auto()
    LIGHT = auto()
    SYSTEM = auto()


class Theme:
    """
    Theme management.
    """

    DARK = {
        "name": "Dark",
        "colors": {
            "background": "#1e1e1e",
            "foreground": "#d4d4d4",
            "selection": "#264f78",
            "selection_text": "#ffffff",
            "caret": "#d4d4d4",
            "line_number": "#858585",
            "line_number_bg": "#1e1e1e",
            "offset": "#569cd6",
            "hex": "#ce9178",
            "ascii": "#a9b7c6",
            "header_bg": "#252526",
            "header_fg": "#cccccc",
            "sidebar_bg": "#252526",
            "sidebar_fg": "#cccccc",
            "panel_bg": "#1e1e1e",
            "panel_fg": "#d4d4d4",
            "border": "#3c3c3c",
            "hover": "#2a2d2e",
            "toolbar_bg": "#3c3c3c",
            "tooltip_bg": "#3c3c3c",
            "tooltip_fg": "#cccccc",
        },
        "syntax": {
            "comment": "#6a9955",
            "string": "#ce9178",
            "number": "#b5cea8",
            "keyword": "#569cd6",
            "function": "#dcdcaa",
            "type": "#4ec9b0",
            "variable": "#9cdcfe",
        }
    }

    LIGHT = {
        "name": "Light",
        "colors": {
            "background": "#ffffff",
            "foreground": "#333333",
            "selection": "#add6ff",
            "selection_text": "#000000",
            "caret": "#333333",
            "line_number": "#2b91af",
            "line_number_bg": "#ffffff",
            "offset": "#0000ff",
            "hex": "#a31515",
            "ascii": "#333333",
            "header_bg": "#f0f0f0",
            "header_fg": "#333333",
            "sidebar_bg": "#f0f0f0",
            "sidebar_fg": "#333333",
            "panel_bg": "#ffffff",
            "panel_fg": "#333333",
            "border": "#cccccc",
            "hover": "#e8e8e8",
            "toolbar_bg": "#f0f0f0",
            "tooltip_bg": "#ffffb0",
            "tooltip_fg": "#000000",
        },
        "syntax": {
            "comment": "#008000",
            "string": "#a31515",
            "number": "#098658",
            "keyword": "#0000ff",
            "function": "#795e26",
            "type": "#267f99",
            "variable": "#001080",
        }
    }

    def __init__(self, theme_type: ThemeType = ThemeType.DARK):
        self._theme_type = theme_type
        self._current = self.DARK

    @property
    def theme_type(self) -> ThemeType:
        """Get theme type."""
        return self._theme_type

    @theme_type.setter
    def theme_type(self, value: ThemeType):
        """Set theme type."""
        self._theme_type = value
        if value == ThemeType.DARK:
            self._current = self.DARK
        else:
            self._current = self.LIGHT

    @property
    def name(self) -> str:
        """Get theme name."""
        return self._current["name"]

    @property
    def colors(self) -> Dict[str, str]:
        """Get theme colors."""
        return self._current["colors"].copy()

    @property
    def syntax(self) -> Dict[str, str]:
        """Get syntax colors."""
        return self._current["syntax"].copy()

    def get_color(self, name: str) -> str:
        """Get color by name."""
        return self._current["colors"].get(name, "#000000")

    def get_syntax_color(self, name: str) -> str:
        """Get syntax color by name."""
        return self._current["syntax"].get(name, "#000000")

    def apply_to_stylesheet(self) -> str:
        """Generate stylesheet from theme."""
        colors = self._current["colors"]
        syntax = self._current["syntax"]

        return f"""
            QMainWindow, QWidget {{
                background-color: {colors['background']};
                color: {colors['foreground']};
            }}

            QMenuBar {{
                background-color: {colors['toolbar_bg']};
                color: {colors['foreground']};
            }}

            QMenuBar::item:selected {{
                background-color: {colors['selection']};
            }}

            QMenu {{
                background-color: {colors['panel_bg']};
                color: {colors['foreground']};
                border: 1px solid {colors['border']};
            }}

            QMenu::item:selected {{
                background-color: {colors['selection']};
            }}

            QToolBar {{
                background-color: {colors['toolbar_bg']};
                border-bottom: 1px solid {colors['border']};
            }}

            QStatusBar {{
                background-color: {colors['toolbar_bg']};
                color: {colors['foreground']};
            }}

            QSplitter::handle {{
                background-color: {colors['border']};
            }}

            QScrollBar {{
                background-color: {colors['background']};
            }}

            QScrollBar::handle {{
                background-color: {colors['toolbar_bg']};
            }}

            QScrollBar::add-line, QScrollBar::sub-line {{
                background-color: {colors['toolbar_bg']};
            }}

            QTabWidget::pane {{
                background-color: {colors['background']};
                border: 1px solid {colors['border']};
            }}

            QTabBar::tab {{
                background-color: {colors['panel_bg']};
                color: {colors['foreground']};
                padding: 5px 10px;
            }}

            QTabBar::tab:selected {{
                background-color: {colors['background']};
            }}

            QLineEdit, QTextEdit, QPlainTextEdit {{
                background-color: {colors['panel_bg']};
                color: {colors['foreground']};
                border: 1px solid {colors['border']};
            }}

            QComboBox {{
                background-color: {colors['panel_bg']};
                color: {colors['foreground']};
                border: 1px solid {colors['border']};
                padding: 3px 5px;
            }}

            QPushButton {{
                background-color: {colors['panel_bg']};
                color: {colors['foreground']};
                border: 1px solid {colors['border']};
                padding: 5px 10px;
            }}

            QPushButton:hover {{
                background-color: {colors['hover']};
            }}

            QPushButton:pressed {{
                background-color: {colors['selection']};
            }}
        """

    def apply_to_qss(self) -> str:
        """Generate QSS from theme."""
        return self.apply_to_stylesheet()
