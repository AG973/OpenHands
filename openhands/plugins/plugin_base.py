"""Plugin base — abstract interface for OpenHands plugins.

Defines the plugin lifecycle and hook points that plugins can implement.
Ported from OpenClaw's plugin SDK patterns.

Per OPERATING_RULES.md RULE 5: Plugin errors are caught and logged, never crash core.
"""

from abc import ABC
from enum import Enum
from typing import Any


class PluginHook(Enum):
    """Available hook points in the OpenHands lifecycle."""

    # Session lifecycle
    ON_SESSION_START = 'on_session_start'
    ON_SESSION_END = 'on_session_end'
    ON_SESSION_PAUSE = 'on_session_pause'
    ON_SESSION_RESUME = 'on_session_resume'

    # Agent step lifecycle
    BEFORE_AGENT_STEP = 'before_agent_step'
    AFTER_AGENT_STEP = 'after_agent_step'

    # Tool call lifecycle
    BEFORE_TOOL_CALL = 'before_tool_call'
    AFTER_TOOL_CALL = 'after_tool_call'

    # LLM call lifecycle
    BEFORE_LLM_CALL = 'before_llm_call'
    AFTER_LLM_CALL = 'after_llm_call'

    # Memory lifecycle
    ON_MEMORY_ADD = 'on_memory_add'
    ON_MEMORY_SEARCH = 'on_memory_search'

    # Error handling
    ON_ERROR = 'on_error'
    ON_RECOVERY = 'on_recovery'

    # Message lifecycle
    ON_USER_MESSAGE = 'on_user_message'
    ON_AGENT_MESSAGE = 'on_agent_message'


class OpenHandsPlugin(ABC):
    """Base class for OpenHands plugins.

    Plugins extend OpenHands by hooking into lifecycle events.
    All hook methods are optional — only implement what you need.

    Plugins are loaded from:
    - ~/.openhands/plugins/
    - .openhands/plugins/ in workspace root

    Example plugin:

        class MyPlugin(OpenHandsPlugin):
            name = 'my-plugin'
            version = '1.0.0'
            description = 'Does something useful'

            def on_load(self, config: dict) -> None:
                self.api_key = config.get('api_key', '')

            def after_agent_step(self, **kwargs) -> dict | None:
                # Log each agent step
                action = kwargs.get('action')
                if action:
                    self.logger.info(f'Agent performed: {action}')
                return None
    """

    # Plugin identity — override in subclass
    name: str = ''
    version: str = '1.0.0'
    description: str = ''

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._enabled: bool = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    # ── Lifecycle ─────────────────────────────────────────────────────

    def on_load(self, config: dict[str, Any]) -> None:
        """Called when the plugin is loaded. Override to initialize resources.

        Args:
            config: Plugin-specific configuration dict
        """
        self._config = config

    def on_unload(self) -> None:
        """Called when the plugin is unloaded. Override to cleanup resources."""
        pass

    # ── Session hooks ─────────────────────────────────────────────────

    def on_session_start(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when a new session starts.

        kwargs: session_id, user_id, workspace_dir
        """
        return None

    def on_session_end(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when a session ends.

        kwargs: session_id, reason, duration_ms
        """
        return None

    def on_session_pause(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when a session is paused."""
        return None

    def on_session_resume(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when a session is resumed."""
        return None

    # ── Agent step hooks ──────────────────────────────────────────────

    def before_agent_step(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called before the agent processes a step.

        kwargs: state, iteration
        Return dict to modify the state, or None to pass through.
        """
        return None

    def after_agent_step(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called after the agent completes a step.

        kwargs: action, observation, state, iteration
        """
        return None

    # ── Tool call hooks ───────────────────────────────────────────────

    def before_tool_call(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called before a tool is invoked.

        kwargs: tool_name, args
        Return dict with modified args, or None to pass through.
        """
        return None

    def after_tool_call(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called after a tool completes.

        kwargs: tool_name, args, result, duration_ms
        Return dict with modified result, or None to pass through.
        """
        return None

    # ── LLM call hooks ────────────────────────────────────────────────

    def before_llm_call(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called before an LLM request is made.

        kwargs: messages, model, temperature
        Return dict with modified parameters, or None to pass through.
        """
        return None

    def after_llm_call(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called after an LLM response is received.

        kwargs: messages, response, model, duration_ms, tokens_used
        """
        return None

    # ── Memory hooks ──────────────────────────────────────────────────

    def on_memory_add(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when a new memory entry is added.

        kwargs: entry_id, memory_type, title, content
        """
        return None

    def on_memory_search(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when memory is searched.

        kwargs: query, results_count
        """
        return None

    # ── Error hooks ───────────────────────────────────────────────────

    def on_error(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when an error occurs.

        kwargs: error, classification, category, severity
        """
        return None

    def on_recovery(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when recovery from an error succeeds.

        kwargs: error, recovery_action, attempt
        """
        return None

    # ── Message hooks ─────────────────────────────────────────────────

    def on_user_message(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when a user message is received.

        kwargs: message, source
        """
        return None

    def on_agent_message(self, **kwargs: Any) -> dict[str, Any] | None:
        """Called when the agent sends a message.

        kwargs: message, action_type
        """
        return None
