"""Plugin loader — discover and load plugins from filesystem directories.

Loads plugins from:
1. Global plugins: ~/.openhands/plugins/
2. Workspace plugins: .openhands/plugins/ in the workspace root
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path

from openhands.core.logger import openhands_logger as logger
from openhands.plugins.plugin_base import OpenHandsPlugin

GLOBAL_PLUGINS_DIR = os.path.join(str(Path.home()), '.openhands', 'plugins')


class PluginLoader:
    """Discover and load OpenHands plugins from directories."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        global_plugins_dir: str = GLOBAL_PLUGINS_DIR,
        extra_dirs: list[str] | None = None,
    ):
        self._workspace_dir = workspace_dir
        self._global_plugins_dir = global_plugins_dir
        self._extra_dirs = extra_dirs or []

    def load_all(self) -> list[OpenHandsPlugin]:
        """Load plugins from all configured directories.

        Returns:
            List of instantiated plugin objects
        """
        plugins: list[OpenHandsPlugin] = []

        # Global plugins
        plugins.extend(self._load_from_dir(self._global_plugins_dir))

        # Workspace plugins
        if self._workspace_dir:
            workspace_plugins = os.path.join(
                self._workspace_dir, '.openhands', 'plugins'
            )
            plugins.extend(self._load_from_dir(workspace_plugins))

        # Extra directories
        for extra_dir in self._extra_dirs:
            plugins.extend(self._load_from_dir(extra_dir))

        logger.info(f'Loaded {len(plugins)} plugins')
        return plugins

    def _load_from_dir(self, directory: str) -> list[OpenHandsPlugin]:
        """Load all plugins from a directory."""
        plugins: list[OpenHandsPlugin] = []

        if not os.path.isdir(directory):
            return plugins

        for entry in sorted(os.listdir(directory)):
            entry_path = os.path.join(directory, entry)

            # Single .py file plugin
            if entry.endswith('.py') and os.path.isfile(entry_path):
                plugin = self._load_plugin_file(entry_path)
                if plugin is not None:
                    plugins.append(plugin)
                continue

            # Directory-based plugin (must have __init__.py or plugin.py)
            if os.path.isdir(entry_path):
                init_path = os.path.join(entry_path, '__init__.py')
                plugin_path = os.path.join(entry_path, 'plugin.py')

                if os.path.isfile(plugin_path):
                    plugin = self._load_plugin_file(plugin_path)
                    if plugin is not None:
                        plugins.append(plugin)
                elif os.path.isfile(init_path):
                    plugin = self._load_plugin_file(init_path)
                    if plugin is not None:
                        plugins.append(plugin)

        return plugins

    def _load_plugin_file(self, filepath: str) -> OpenHandsPlugin | None:
        """Load a single plugin from a Python file.

        Looks for classes that subclass OpenHandsPlugin.
        """
        try:
            module_name = f'openhands_plugin_{os.path.basename(filepath).replace(".py", "")}'

            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                logger.warning(f'Cannot load plugin spec from {filepath}')
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find OpenHandsPlugin subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, OpenHandsPlugin)
                    and attr is not OpenHandsPlugin
                    and not getattr(attr, '__abstractmethods__', set())
                ):
                    instance = attr()
                    if instance.name:
                        logger.debug(f'Loaded plugin: {instance.name} from {filepath}')
                        return instance
                    else:
                        logger.warning(
                            f'Plugin class {attr_name} in {filepath} has no name set'
                        )

            return None

        except Exception as e:
            # Plugin errors must never crash the core
            logger.warning(f'Failed to load plugin from {filepath}: {e}')
            return None
