"""Plugin architecture for OpenHands extensibility.

Provides a hook-based plugin system that allows extending OpenHands
without modifying core code. Ported from OpenClaw's plugin system patterns.
"""

from openhands.plugins.hook_runner import HookRunner
from openhands.plugins.plugin_base import OpenHandsPlugin, PluginHook
from openhands.plugins.plugin_loader import PluginLoader
from openhands.plugins.plugin_registry import PluginRegistry

__all__ = [
    'HookRunner',
    'OpenHandsPlugin',
    'PluginHook',
    'PluginLoader',
    'PluginRegistry',
]
