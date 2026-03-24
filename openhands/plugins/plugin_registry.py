"""Plugin registry — central management of loaded plugins.

Manages plugin lifecycle and provides lookup for the hook runner.
"""

from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.plugins.plugin_base import OpenHandsPlugin, PluginHook
from openhands.plugins.plugin_loader import PluginLoader


class PluginRegistry:
    """Central registry for managing loaded plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, OpenHandsPlugin] = {}

    def register(self, plugin: OpenHandsPlugin, config: dict[str, Any] | None = None) -> None:
        """Register and initialize a plugin."""
        if not plugin.name:
            logger.warning('Cannot register plugin without a name')
            return

        try:
            plugin.on_load(config or {})
            self._plugins[plugin.name] = plugin
            logger.info(f'Registered plugin: {plugin.name} v{plugin.version}')
        except Exception as e:
            logger.error(f'Failed to load plugin {plugin.name}: {e}')

    def unregister(self, name: str) -> bool:
        """Unregister and cleanup a plugin."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return False

        try:
            plugin.on_unload()
        except Exception as e:
            logger.warning(f'Error unloading plugin {name}: {e}')

        del self._plugins[name]
        return True

    def get(self, name: str) -> OpenHandsPlugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def load_from_loader(
        self,
        loader: PluginLoader,
        configs: dict[str, dict[str, Any]] | None = None,
    ) -> int:
        """Load all plugins from a PluginLoader and register them.

        Args:
            loader: PluginLoader to load from
            configs: Plugin-specific configs keyed by plugin name

        Returns:
            Number of plugins loaded
        """
        configs = configs or {}
        plugins = loader.load_all()
        for plugin in plugins:
            config = configs.get(plugin.name, {})
            self.register(plugin, config)
        return len(self._plugins)

    def get_plugins_for_hook(self, hook: PluginHook) -> list[OpenHandsPlugin]:
        """Get all enabled plugins that implement a specific hook.

        Args:
            hook: The hook to check for

        Returns:
            List of plugins that implement this hook
        """
        method_name = hook.value
        result: list[OpenHandsPlugin] = []

        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            method = getattr(plugin, method_name, None)
            if method is not None and callable(method):
                # Check if the method is overridden from base class
                base_method = getattr(OpenHandsPlugin, method_name, None)
                if method.__func__ is not base_method:
                    result.append(plugin)

        return result

    def get_all_plugins(self) -> list[OpenHandsPlugin]:
        """Get all registered plugins."""
        return list(self._plugins.values())

    @property
    def count(self) -> int:
        return len(self._plugins)

    def unload_all(self) -> None:
        """Unload all plugins."""
        for name in list(self._plugins.keys()):
            self.unregister(name)
