"""
Styles

Stylesheet definitions for openhex.
"""

from .theme import Theme


class Styles:
    """
    Stylesheet definitions.
    """

    @staticmethod
    def get_default() -> str:
        """Get default stylesheet."""
        theme = Theme(Theme.theme_type.DARK)
        return theme.apply_to_stylesheet()

    @staticmethod
    def get_hex_view() -> str:
        """Get hex view specific styles."""
        return """
            HexView {
                font-family: 'Menlo', 'Monaco', 'Courier New';
                font-size: 11px;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
        """

    @staticmethod
    def get_line_numbers() -> str:
        """Get line number styling."""
        return """
            LineNumber {
                background-color: #1e1e1e;
                color: #858585;
                font-family: 'Menlo', 'Monaco', 'Courier New';
                font-size: 11px;
            }
        """

    @staticmethod
    def get_status_bar() -> str:
        """Get status bar styling."""
        return """
            QStatusBar {
                background-color: #252526;
                color: #cccccc;
                border-top: 1px solid #3c3c3c;
            }
        """

    @staticmethod
    def get_toolbar() -> str:
        """Get toolbar styling."""
        return """
            QToolBar {
                background-color: #3c3c3c;
                border-bottom: 1px solid #2d2d2d;
                spacing: 4px;
                padding: 2px;
            }

            QToolBar::separator {
                background-color: #505050;
                width: 1px;
                margin: 2px;
            }
        """

    @staticmethod
    def get_menu_bar() -> str:
        """Get menu bar styling."""
        return """
            QMenuBar {
                background-color: #3c3c3c;
                color: #d4d4d4;
                border-bottom: 1px solid #2d2d2d;
            }

            QMenuBar::item:selected {
                background-color: #264f78;
            }
        """

    @staticmethod
    def get_menu() -> str:
        """Get menu styling."""
        return """
            QMenu {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }

            QMenu::item:selected {
                background-color: #264f78;
            }

            QMenu::separator {
                background-color: #3c3c3c;
                height: 1px;
                margin: 2px;
            }
        """

    @staticmethod
    def get_tab_widget() -> str:
        """Get tab widget styling."""
        return """
            QTabWidget::pane {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
            }

            QTabBar::tab {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
            }

            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }

            QTabBar::tab:hover:!selected {
                background-color: #3c3c3c;
            }
        """

    @staticmethod
    def get_panel() -> str:
        """Get side panel styling."""
        return """
            Panel {
                background-color: #252526;
                color: #cccccc;
                border-right: 1px solid #3c3c3c;
            }

            PanelTitle {
                background-color: #2d2d2d;
                color: #cccccc;
                font-weight: bold;
                padding: 4px;
            }
        """

    @staticmethod
    def get_tree_view() -> str:
        """Get tree view styling."""
        return """
            QTreeView {
                background-color: #252526;
                color: #cccccc;
                border: none;
                alternate-background-color: #2d2d2d;
            }

            QTreeView::item:selected {
                background-color: #264f78;
                color: #ffffff;
            }

            QTreeView::item:hover {
                background-color: #2a2d2e;
            }
        """

    @staticmethod
    def get_dialog() -> str:
        """Get dialog styling."""
        return """
            QDialog {
                background-color: #1e1e1e;
                color: #d4d4d4;
            }

            QDialogButtonBox {
                background-color: #1e1e1e;
            }
        """

    @staticmethod
    def get_tooltip() -> str:
        """Get tooltip styling."""
        return """
            QToolTip {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #505050;
                padding: 4px;
            }
        """

    @staticmethod
    def get_full() -> str:
        """Get complete application stylesheet."""
        parts = [
            Styles.get_default(),
            Styles.get_hex_view(),
            Styles.get_line_numbers(),
            Styles.get_status_bar(),
            Styles.get_toolbar(),
            Styles.get_menu_bar(),
            Styles.get_menu(),
            Styles.get_tab_widget(),
            Styles.get_panel(),
            Styles.get_tree_view(),
            Styles.get_dialog(),
            Styles.get_tooltip(),
        ]
        return '\n'.join(parts)
