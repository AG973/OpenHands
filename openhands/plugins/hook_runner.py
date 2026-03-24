"""Hook runner — execute plugin hooks safely across all registered plugins.

Ensures plugin errors never crash the core system. Ported from OpenClaw's
plugin execution patterns.

Per OPERATING_RULES.md RULE 15: NO silent failures — every exception must be logged.
"""

import time
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.plugins.plugin_base import OpenHandsPlugin, PluginHook
from openhands.plugins.plugin_registry import PluginRegistry


class HookRunner:
    """Execute hooks across all registered plugins safely.

    All plugin hook calls are wrapped in try/except to ensure a buggy
    plugin never crashes the core OpenHands system.
    """

    def __init__(self, registry: PluginRegistry):
        self._registry = registry

    def run_hook(
        self,
        hook: PluginHook,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Run a hook across all plugins that implement it.

        Args:
            hook: The hook to execute
            **kwargs: Arguments to pass to each plugin's hook method

        Returns:
            List of non-None results from plugins
        """
        results: list[dict[str, Any]] = []
        plugins = self._registry.get_plugins_for_hook(hook)

        for plugin in plugins:
            result = self._safe_call(plugin, hook, **kwargs)
            if result is not None:
                results.append(result)

        return results

    def run_hook_chain(
        self,
        hook: PluginHook,
        initial_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Run a hook as a chain — each plugin's output becomes the next plugin's input.

        This is used for hooks like BEFORE_TOOL_CALL where plugins can
        modify arguments that flow to the next plugin.

        Args:
            hook: The hook to execute as chain
            initial_data: Starting data dict

        Returns:
            Final data dict after all plugins have processed it
        """
        data = dict(initial_data)
        plugins = self._registry.get_plugins_for_hook(hook)

        for plugin in plugins:
            result = self._safe_call(plugin, hook, **data)
            if result is not None and isinstance(result, dict):
                data.update(result)

        return data

    def _safe_call(
        self,
        plugin: OpenHandsPlugin,
        hook: PluginHook,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Safely call a plugin hook method, catching all exceptions.

        Args:
            plugin: The plugin to call
            hook: The hook to invoke
            **kwargs: Arguments to pass

        Returns:
            Plugin's return value or None if the call failed
        """
        method = getattr(plugin, hook.value, None)
        if method is None or not callable(method):
            return None

        start_time = time.time()
        try:
            result = method(**kwargs)
            duration_ms = (time.time() - start_time) * 1000

            if duration_ms > 1000:
                logger.warning(
                    f'Plugin {plugin.name} hook {hook.value} took {duration_ms:.0f}ms'
                )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f'Plugin {plugin.name} hook {hook.value} failed after {duration_ms:.0f}ms: {e}'
            )
            # Plugin errors never crash core — log and continue
            return None
