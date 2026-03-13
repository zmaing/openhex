"""
openhex Application

QApplication singleton management and global application state.
"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSettings, QCoreApplication
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
from pathlib import Path

import os
import sys
import tempfile
import PyQt6

from .utils.logger import logger
from .utils.i18n import set_language
from .ui.design_system import CHROME, build_application_stylesheet


class OpenHexApp(QApplication):
    """openhex Application singleton."""

    _instance = None

    def __init__(self, argv):
        self._configure_qt_plugin_path()
        super().__init__(argv)
        OpenHexApp._instance = self
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
        self.setApplicationName("openhex")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("openhex")
        self.setOrganizationDomain("openhex.io")

        # High DPI support - check if attribute exists
        if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
            self.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
            self.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

        # Load settings
        self._settings = self._create_settings()

        # Load language setting
        self._load_language()

        # Set default font
        self._set_default_font()

        # Set application palette
        self._set_default_palette()
        self.setStyleSheet(build_application_stylesheet())

        logger.info("openhex application initialized")

    def _create_settings(self) -> QSettings:
        """Create application settings storage."""
        if "PYTEST_CURRENT_TEST" in os.environ:
            settings_dir = Path(tempfile.gettempdir()) / "openhex-pytest"
            settings_dir.mkdir(parents=True, exist_ok=True)
            return QSettings(str(settings_dir / "settings.ini"), QSettings.Format.IniFormat)
        return QSettings("openhex", "openhex")

    def _configure_qt_plugin_path(self):
        """Prefer the platform plugins bundled with the active PyQt6 install."""
        if os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
            return

        plugin_dir = Path(PyQt6.__file__).resolve().parent / "Qt6" / "plugins" / "platforms"
        if plugin_dir.exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_dir)

    def _set_default_font(self):
        """Set default font for the application."""
        font = QFont("Segoe UI", 10)
        if sys.platform == "win32":
            font = QFont("Segoe UI", 10)
        elif sys.platform == "darwin":
            font = QFont("PingFang SC", 12)
        else:
            font = QFont("Noto Sans", 10)
        self.setFont(font)

    def _set_default_palette(self):
        """Set default color palette."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(CHROME.app_bg))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(CHROME.text_primary))
        palette.setColor(QPalette.ColorRole.Base, QColor(CHROME.surface))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(CHROME.surface_alt))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(CHROME.surface_alt))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(CHROME.text_primary))
        palette.setColor(QPalette.ColorRole.Text, QColor(CHROME.text_primary))
        palette.setColor(QPalette.ColorRole.Button, QColor(CHROME.surface_alt))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(CHROME.text_primary))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(CHROME.text_primary))
        palette.setColor(QPalette.ColorRole.Link, QColor(CHROME.accent))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(CHROME.accent))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(CHROME.text_primary))
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
