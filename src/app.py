"""
HexForge Application

QApplication singleton management and global application state.
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings, QCoreApplication
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

import os
import sys

from .utils.logger import logger
from .utils.i18n import set_language


class HexForgeApp(QApplication):
    """HexForge Application singleton."""

    _instance = None

    def __init__(self, argv):
        super().__init__(argv)
        HexForgeApp._instance = self
        self._init_application()

    @classmethod
    def instance(cls):
        """Get the application singleton instance."""
        if cls._instance is None:
            cls._instance = cls(sys.argv)
        return cls._instance

    def _init_application(self):
        """Initialize application settings and appearance."""
        # Application metadata
        self.setApplicationName("HexForge")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("HexForge")
        self.setOrganizationDomain("hexforge.io")

        # High DPI support - check if attribute exists
        if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
            self.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
            self.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

        # Load settings
        self._settings = QSettings("HexForge", "HexForge")

        # Load language setting
        self._load_language()

        # Set default font
        self._set_default_font()

        # Set application palette
        self._set_default_palette()

        logger.info("HexForge application initialized")

    def _set_default_font(self):
        """Set default font for the application."""
        font = QFont("Menlo", 11)  # Monospace for hex editing
        if sys.platform == "win32":
            font = QFont("Consolas", 10)
        elif sys.platform == "darwin":
            font = QFont("SF Mono", 11)
        self.setFont(font)

    def _set_default_palette(self):
        """Set default color palette."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#d4d4d4"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#252526"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2d2d2d"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#3c3c3c"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#cccccc"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#3c3c3c"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Link, QColor("#3794ff"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#264f78"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)

    def _load_language(self):
        """Load language setting."""
        # Force sync to ensure we read latest value
        self._settings.sync()
        language = self._settings.value("language", "en", type=str)
        set_language(language)
        logger.info(f"Language set to: {language} (from settings)")

    @property
    def settings(self) -> QSettings:
        """Get application settings."""
        return self._settings

    def save_settings(self):
        """Save application settings."""
        self._settings.sync()
        logger.info("Application settings saved")
