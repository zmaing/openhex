"""
Plugin System

插件系统基础架构
"""

from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, List, Optional, Any
import importlib.util
import os
import json


class PluginInfo:
    """Plugin information."""

    def __init__(self, name: str, version: str, author: str = "", description: str = ""):
        self.name = name
        self.version = version
        self.author = author
        self.description = description
        self.enabled = False


class PluginBase:
    """Base class for plugins."""

    def __init__(self, plugin_info: PluginInfo):
        self.info = plugin_info
        self._enabled = False

    def initialize(self) -> bool:
        """Initialize plugin."""
        raise NotImplementedError

    def shutdown(self):
        """Shutdown plugin."""
        pass

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        """Enable plugin."""
        self._enabled = True

    def disable(self):
        """Disable plugin."""
        self._enabled = False


class PluginManager(QObject):
    """
    Plugin manager.

    Manages plugin loading, enabling, and lifecycle.
    """

    # Signals
    plugin_loaded = pyqtSignal(str)  # plugin name
    plugin_enabled = pyqtSignal(str)
    plugin_disabled = pyqtSignal(str)
    plugin_error = pyqtSignal(str, str)  # plugin name, error

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plugins: Dict[str, PluginBase] = {}
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._plugin_paths: List[str] = []

        # Default plugin directory
        self.add_plugin_path(os.path.join(os.path.dirname(__file__), "..", "..", "plugins"))

    def add_plugin_path(self, path: str):
        """Add plugin search path."""
        if os.path.isdir(path):
            self._plugin_paths.append(path)

    def discover_plugins(self) -> List[str]:
        """Discover available plugins."""
        discovered = []

        for plugin_path in self._plugin_paths:
            if not os.path.isdir(plugin_path):
                continue

            for entry in os.listdir(plugin_path):
                plugin_dir = os.path.join(plugin_path, entry)
                if os.path.isdir(plugin_dir):
                    # Check for plugin.py
                    plugin_file = os.path.join(plugin_dir, "plugin.py")
                    if os.path.exists(plugin_file):
                        discovered.append(entry)

        return discovered

    def load_plugin(self, name: str) -> bool:
        """Load a plugin by name."""
        # Try to find plugin
        plugin_file = None
        for plugin_path in self._plugin_paths:
            candidate = os.path.join(plugin_path, name, "plugin.py")
            if os.path.exists(candidate):
                plugin_file = candidate
                break

        if not plugin_file:
            self.plugin_error.emit(name, "Plugin not found")
            return False

        try:
            # Load module
            spec = importlib.util.spec_from_file_location(f"plugins.{name}", plugin_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get plugin class
            if not hasattr(module, 'Plugin'):
                self.plugin_error.emit(name, "Plugin class not found")
                return False

            plugin_class = module.Plugin

            # Create plugin instance
            plugin = plugin_class()

            # Initialize
            if not plugin.initialize():
                self.plugin_error.emit(name, "Initialization failed")
                return False

            # Store
            self._plugins[name] = plugin
            self.plugin_loaded.emit(name)

            return True

        except Exception as e:
            self.plugin_error.emit(name, str(e))
            return False

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin."""
        if name not in self._plugins:
            return False

        plugin = self._plugins[name]
        plugin.shutdown()

        del self._plugins[name]
        return True

    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin."""
        if name not in self._plugins:
            return False

        plugin = self._plugins[name]
        plugin.enable()
        self.plugin_enabled.emit(name)
        return True

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin."""
        if name not in self._plugins:
            return False

        plugin = self._plugins[name]
        plugin.disable()
        self.plugin_disabled.emit(name)
        return True

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """Get plugin by name."""
        return self._plugins.get(name)

    def get_all_plugins(self) -> Dict[str, PluginBase]:
        """Get all loaded plugins."""
        return self._plugins.copy()

    def is_plugin_loaded(self, name: str) -> bool:
        """Check if plugin is loaded."""
        return name in self._plugins

    def is_plugin_enabled(self, name: str) -> bool:
        """Check if plugin is enabled."""
        plugin = self._plugins.get(name)
        return plugin.enabled if plugin else False
