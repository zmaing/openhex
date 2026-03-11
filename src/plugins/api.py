"""
Plugin API

插件 API 接口定义
"""

from .manager import PluginBase, PluginInfo


class HexEditorPlugin(PluginBase):
    """
    Base class for openhex plugins.

    All plugins should inherit from this class.
    """

    def __init__(self, plugin_info: PluginInfo):
        super().__init__(plugin_info)
        self._app = None

    def set_app(self, app):
        """Set application instance."""
        self._app = app

    @property
    def app(self):
        """Get application instance."""
        return self._app

    def get_hex_editor(self):
        """Get hex editor widget."""
        if self._app and hasattr(self._app, '_hex_editor'):
            return self._app._hex_editor
        return None


class MenuPlugin(HexEditorPlugin):
    """Plugin that adds menu items."""

    def get_menu_items(self) -> list:
        """
        Return list of menu items to add.

        Each item is a dict with:
        - 'menu': menu name (e.g., 'File', 'Edit', 'View')
        - 'text': menu item text
        - 'shortcut': optional shortcut
        - 'callback': callback function
        """
        return []


class PanelPlugin(HexEditorPlugin):
    """Plugin that adds a panel."""

    def get_panel_widget(self):
        """Return the panel widget to add."""
        return None

    def get_panel_position(self) -> str:
        """Return panel position: 'left', 'right', 'bottom'"""
        return 'right'


class ToolPlugin(HexEditorPlugin):
    """Plugin that adds a tool."""

    def get_toolbar_items(self) -> list:
        """
        Return list of toolbar items to add.

        Each item is a dict with:
        - 'icon': icon name
        - 'text': tooltip text
        - 'callback': callback function
        """
        return []
