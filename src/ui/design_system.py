"""
Dense desktop editor design tokens and shared QSS helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QFont


@dataclass(frozen=True)
class ChromeTokens:
    """Shared dimensions and colors for the desktop shell."""

    app_bg: str = "#16181C"
    workspace_bg: str = "#1B1D21"
    surface: str = "#1F2126"
    surface_alt: str = "#24272D"
    surface_raised: str = "#2B2F36"
    surface_hover: str = "#31363F"
    border: str = "#31343B"
    border_strong: str = "#3B4049"
    text_primary: str = "#E6EAF2"
    text_secondary: str = "#AEB7C6"
    text_muted: str = "#7F8897"
    accent: str = "#3E8CFF"
    accent_hover: str = "#74ACFF"
    accent_surface: str = "#24364D"
    accent_surface_strong: str = "#35506E"
    success: str = "#5EC7A5"
    warning: str = "#D9B25E"
    danger: str = "#FF8A7A"
    panel_radius: int = 12
    control_radius: int = 7
    chip_radius: int = 7
    toolbar_height: int = 36
    status_bar_height: int = 36
    sidebar_width: int = 240
    right_panel_width: int = 312
    right_panel_horizontal_width: int = 540
    header_height: int = 32
    control_height: int = 24
    row_height: int = 24


CHROME = ChromeTokens()
UI_FONT_FAMILY = '"IBM Plex Sans","SF Pro Text","PingFang SC","Segoe UI","Noto Sans",sans-serif'
MONO_FONT_FAMILIES = ["JetBrains Mono", "Menlo", "Monaco", "Courier New"]
MONO_FONT_FAMILY = '"JetBrains Mono","Menlo","Monaco","Courier New"'


def build_mono_font(point_size: int, weight: int | QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Return a fixed-pitch UI font with explicit fallbacks."""
    font = QFont(MONO_FONT_FAMILIES[0], point_size)
    font.setFamilies(MONO_FONT_FAMILIES)
    font.setFixedPitch(True)
    font.setWeight(weight)
    return font


def build_application_stylesheet() -> str:
    """Return the shared desktop chrome stylesheet."""
    t = CHROME
    return f"""
        QMainWindow {{
            background-color: {t.app_bg};
        }}

        QWidget {{
            color: {t.text_primary};
            selection-background-color: {t.accent};
            selection-color: {t.text_primary};
        }}

        QWidget#hexEditorWorkspace {{
            background-color: {t.workspace_bg};
            border-radius: 16px;
        }}

        QWidget#editorCenterColumn,
        QWidget#rightPanelShell {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 16px;
        }}

        QMenuBar {{
            background-color: {t.workspace_bg};
            color: {t.text_secondary};
            border: none;
            padding: 2px 6px;
            spacing: 0px;
        }}

        QMenuBar::item {{
            background: transparent;
            border-radius: 4px;
            padding: 4px 6px 3px 6px;
            margin: 0 1px;
            color: {t.text_muted};
        }}

        QMenuBar::item:selected {{
            background-color: transparent;
            color: {t.text_primary};
        }}

        QMenuBar::item:pressed {{
            background-color: {t.surface};
            color: {t.text_primary};
        }}

        QMenu {{
            background-color: {t.surface_alt};
            color: {t.text_primary};
            border: 1px solid {t.border_strong};
            border-radius: 12px;
            padding: 6px;
        }}

        QMenu::item {{
            background-color: transparent;
            border-radius: 8px;
            padding: 7px 14px;
            margin: 1px 0;
        }}

        QMenu::item:selected {{
            background-color: {t.surface_hover};
        }}

        QMenu::item:disabled {{
            color: {t.text_muted};
            background-color: transparent;
        }}

        QMenu::item:checked {{
            background-color: {t.accent_surface};
        }}

        QMenu::item:checked:selected {{
            background-color: {t.accent_surface_strong};
        }}

        QMenu::separator {{
            height: 1px;
            margin: 6px 4px;
            background-color: {t.border};
        }}

        QStatusBar {{
            background-color: {t.workspace_bg};
            color: {t.text_muted};
            border: none;
            border-top: 1px solid {t.border};
            padding: 0 8px;
            min-height: 22px;
            font-size: 10px;
        }}

        QStatusBar::item {{
            border: none;
            padding: 0 4px;
        }}

        QToolTip {{
            background-color: {t.surface_alt};
            color: {t.text_primary};
            border: 1px solid {t.border_strong};
            border-radius: 8px;
            padding: 4px 6px;
        }}

        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 4px 2px 4px 0;
        }}

        QScrollBar::handle:vertical {{
            background: {t.border_strong};
            border-radius: 4px;
            min-height: 24px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {t.text_muted};
        }}

        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
            margin: 0 4px 2px 4px;
        }}

        QScrollBar::handle:horizontal {{
            background: {t.border_strong};
            border-radius: 4px;
            min-width: 24px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background: {t.text_muted};
        }}

        QScrollBar::add-line,
        QScrollBar::sub-line,
        QScrollBar::add-page,
        QScrollBar::sub-page {{
            background: transparent;
            border: none;
        }}

        QLineEdit,
        QTextEdit,
        QPlainTextEdit,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox {{
            background-color: {t.surface_alt};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {t.control_radius}px;
            padding: 5px 8px;
        }}

        QLineEdit:hover,
        QTextEdit:hover,
        QPlainTextEdit:hover,
        QComboBox:hover,
        QSpinBox:hover,
        QDoubleSpinBox:hover {{
            border-color: {t.border_strong};
        }}

        QLineEdit:focus,
        QTextEdit:focus,
        QPlainTextEdit:focus,
        QComboBox:focus,
        QSpinBox:focus,
        QDoubleSpinBox:focus {{
            border-color: {t.accent};
        }}

        QLineEdit[invalid="true"] {{
            background-color: #2A171C;
            border-color: {t.danger};
        }}

        QPushButton {{
            background-color: {t.surface_alt};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {t.control_radius}px;
            padding: 5px 10px;
            min-height: 26px;
        }}

        QPushButton:hover {{
            background-color: {t.surface_hover};
            border-color: {t.border_strong};
        }}

        QPushButton:pressed {{
            background-color: {t.surface_raised};
        }}

        QPushButton:default {{
            background-color: {t.accent_surface};
            border-color: {t.accent_surface_strong};
            color: {t.text_primary};
            font-weight: 700;
        }}

        QDialog,
        QMessageBox,
        QInputDialog {{
            background-color: {t.workspace_bg};
            color: {t.text_primary};
        }}

        QDialog QLabel,
        QMessageBox QLabel,
        QInputDialog QLabel {{
            color: {t.text_secondary};
        }}

        QFrame#dialogHeaderCard {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 14px;
        }}

        QLabel#dialogHeroTitle {{
            color: {t.text_primary};
            font-size: 15px;
            font-weight: 700;
        }}

        QLabel#dialogHeroSubtitle {{
            color: {t.text_muted};
            font-size: 11px;
            line-height: 1.4;
        }}

        QDialog QGroupBox,
        QMessageBox QGroupBox,
        QInputDialog QGroupBox {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 12px;
            margin-top: 12px;
            padding: 12px 10px 10px 10px;
            font-weight: 700;
            color: {t.text_primary};
        }}

        QDialog QGroupBox::title,
        QMessageBox QGroupBox::title,
        QInputDialog QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: {t.text_secondary};
        }}

        QDialog QListWidget,
        QDialog QTextEdit,
        QDialog QPlainTextEdit,
        QDialog QComboBox,
        QDialog QLineEdit,
        QDialog QSpinBox,
        QDialog QDoubleSpinBox {{
            background-color: {t.surface_alt};
        }}

        QDialog QListWidget,
        QMessageBox QListWidget,
        QInputDialog QListWidget {{
            border: 1px solid {t.border};
            border-radius: 10px;
            padding: 4px;
        }}

        QDialog QListWidget::item,
        QMessageBox QListWidget::item,
        QInputDialog QListWidget::item {{
            padding: 6px 10px;
            border-radius: 8px;
        }}

        QDialog QListWidget::item:selected,
        QMessageBox QListWidget::item:selected,
        QInputDialog QListWidget::item:selected {{
            background-color: {t.accent_surface};
            color: {t.text_primary};
        }}

        QDialog QTabWidget::pane,
        QMessageBox QTabWidget::pane,
        QInputDialog QTabWidget::pane {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 12px;
            margin-top: 8px;
        }}

        QDialog QTabBar::tab,
        QMessageBox QTabBar::tab,
        QInputDialog QTabBar::tab {{
            background-color: {t.surface_alt};
            color: {t.text_muted};
            padding: 6px 10px;
            margin-right: 4px;
            border: 1px solid {t.border};
            border-radius: 8px;
            font-weight: 600;
        }}

        QDialog QTabBar::tab:selected,
        QMessageBox QTabBar::tab:selected,
        QInputDialog QTabBar::tab:selected {{
            background-color: {t.accent_surface};
            color: {t.text_primary};
            border-color: {t.accent_surface_strong};
        }}

        QDialog QTabBar::tab:hover:!selected,
        QMessageBox QTabBar::tab:hover:!selected,
        QInputDialog QTabBar::tab:hover:!selected {{
            background-color: {t.surface_hover};
            color: {t.text_primary};
        }}

        QDialog QRadioButton,
        QDialog QCheckBox,
        QMessageBox QRadioButton,
        QMessageBox QCheckBox,
        QInputDialog QRadioButton,
        QInputDialog QCheckBox {{
            color: {t.text_secondary};
            spacing: 8px;
            font-weight: 600;
        }}

        QDialog QRadioButton::indicator,
        QMessageBox QRadioButton::indicator,
        QInputDialog QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 8px;
            border: 1px solid {t.border_strong};
            background-color: {t.surface_alt};
        }}

        QDialog QRadioButton::indicator:checked,
        QMessageBox QRadioButton::indicator:checked,
        QInputDialog QRadioButton::indicator:checked {{
            background-color: {t.accent};
            border-color: {t.accent};
        }}

        QDialog QCheckBox::indicator,
        QMessageBox QCheckBox::indicator,
        QInputDialog QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {t.border_strong};
            background-color: {t.surface_alt};
        }}

        QDialog QCheckBox::indicator:checked,
        QMessageBox QCheckBox::indicator:checked,
        QInputDialog QCheckBox::indicator:checked {{
            background-color: {t.accent};
            border-color: {t.accent};
        }}

        QDialog QProgressBar,
        QMessageBox QProgressBar,
        QInputDialog QProgressBar {{
            background-color: {t.surface_alt};
            border: 1px solid {t.border};
            border-radius: 7px;
            min-height: 12px;
            color: {t.text_secondary};
        }}

        QDialog QProgressBar::chunk,
        QMessageBox QProgressBar::chunk,
        QInputDialog QProgressBar::chunk {{
            background-color: {t.accent};
            border-radius: 7px;
        }}

        QSplitter::handle {{
            background: transparent;
        }}
    """


def panel_surface_qss(selector: str) -> str:
    """Return the base panel card styling."""
    t = CHROME
    return f"""
        {selector} {{
            background-color: {t.surface};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {t.panel_radius}px;
        }}

        {selector} QLabel {{
            background: transparent;
            color: {t.text_secondary};
            border: none;
        }}
    """


def input_surface_qss(selector: str) -> str:
    """Return shared input field styling for a panel scope."""
    t = CHROME
    return f"""
        {selector} QLineEdit,
        {selector} QComboBox,
        {selector} QPlainTextEdit {{
            background-color: {t.surface_alt};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {t.control_radius}px;
            padding: 6px 10px;
        }}

        {selector} QLineEdit:hover,
        {selector} QComboBox:hover,
        {selector} QPlainTextEdit:hover {{
            border-color: {t.border_strong};
        }}

        {selector} QLineEdit:focus,
        {selector} QComboBox:focus,
        {selector} QPlainTextEdit:focus {{
            border-color: {t.accent};
        }}
    """


def table_surface_qss(selector: str) -> str:
    """Return shared table styling for a panel scope."""
    t = CHROME
    return f"""
        {selector} QTableWidget {{
            background-color: {t.surface_alt};
            color: {t.text_primary};
            alternate-background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 10px;
            gridline-color: {t.border};
        }}

        {selector} QHeaderView::section {{
            background-color: {t.surface_raised};
            color: {t.text_secondary};
            padding: 6px 8px;
            border: none;
            border-bottom: 1px solid {t.border};
            font-weight: 600;
        }}
    """


def ghost_tool_button_qss(selector: str) -> str:
    """Return compact ghost-button styling."""
    t = CHROME
    return f"""
        {selector} {{
            background-color: transparent;
            color: {t.text_secondary};
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 4px;
        }}

        {selector}:hover {{
            background-color: {t.surface_hover};
            color: {t.text_primary};
            border-color: {t.border};
        }}

        {selector}:checked {{
            background-color: {t.accent_surface};
            color: {t.text_primary};
            border-color: {t.accent_surface_strong};
        }}
    """


def metric_label_qss(selector: str) -> str:
    """Return capsule styling for read-only metric labels."""
    t = CHROME
    return f"""
        {selector} {{
            background-color: {t.surface_alt};
            color: {t.text_primary};
            border: 1px solid {t.border};
            border-radius: {t.control_radius}px;
            padding: 6px 8px;
        }}
    """


def status_label_qss(color: str) -> str:
    """Return compact semantic label styling."""
    return f"color: {color}; font-weight: 700;"
