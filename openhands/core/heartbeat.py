"""Health/heartbeat monitoring system.

Ported from OpenClaw's heartbeat scheduling patterns. Provides:
- Per-agent heartbeat scheduling with configurable intervals
- Active hours awareness (don't heartbeat during off-hours)
- Heartbeat prompt injection for agent polling
- Missed heartbeat detection and alerting
- Wake handlers for event-driven heartbeats

Per OPERATING_RULES.md RULE 5: No missing health checks — every component exposes status.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from openhands.core.logger import openhands_logger as logger

# Heartbeat configuration
DEFAULT_HEARTBEAT_INTERVAL_S = 60.0
MAX_MISSED_HEARTBEATS = 3
MIN_HEARTBEAT_INTERVAL_S = 5.0
MAX_HEARTBEAT_INTERVAL_S = 3600.0


class HeartbeatState(Enum):
    """State of a heartbeat monitor."""

    ACTIVE = 'active'
    PAUSED = 'paused'
    MISSED = 'missed'
    DEAD = 'dead'
    STOPPED = 'stopped'


class HealthStatus(Enum):
    """Overall health status."""

    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


@dataclass
class HeartbeatConfig:
    """Configuration for a heartbeat monitor."""

    agent_id: str
    interval_s: float = DEFAULT_HEARTBEAT_INTERVAL_S
    max_missed: int = MAX_MISSED_HEARTBEATS
    active_hours_start: int | None = None  # UTC hour (0-23), None = always active
    active_hours_end: int | None = None  # UTC hour (0-23), None = always active
    inject_prompt: bool = True  # Whether to inject heartbeat into agent prompt
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.interval_s = max(
            MIN_HEARTBEAT_INTERVAL_S,
            min(MAX_HEARTBEAT_INTERVAL_S, self.interval_s),
        )


@dataclass
class HeartbeatEntry:
    """Tracking entry for a single agent's heartbeat."""

    config: HeartbeatConfig
    state: HeartbeatState = HeartbeatState.ACTIVE
    last_beat_at: float = 0.0
    missed_count: int = 0
    total_beats: int = 0
    total_missed: int = 0
    created_at: float = 0.0
    _task: asyncio.Task[None] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def seconds_since_last_beat(self) -> float:
        """Seconds since the last heartbeat."""
        if self.last_beat_at == 0.0:
            return time.time() - self.created_at
        return time.time() - self.last_beat_at

    @property
    def is_in_active_hours(self) -> bool:
        """Check if current time is within active hours."""
        if (
            self.config.active_hours_start is None
            or self.config.active_hours_end is None
        ):
            return True

        import datetime
        current_hour = datetime.datetime.now(datetime.timezone.utc).hour
        start = self.config.active_hours_start
        end = self.config.active_hours_end

        if start <= end:
            return start <= current_hour < end
        else:
            # Wraps around midnight
            return current_hour >= start or current_hour < end


@dataclass
class ComponentHealth:
    """Health status of a single component."""

    name: str
    status: HealthStatus
    message: str = ''
    last_check_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class HeartbeatMonitor:
    """Manages heartbeat scheduling and health monitoring for agents.

    Each agent can register a heartbeat that fires at a configurable interval.
    Missed heartbeats trigger warnings and eventually mark the agent as dead.
    """

    def __init__(self) -> None:
        self._entries: dict[str, HeartbeatEntry] = {}
        self._components: dict[str, ComponentHealth] = {}
        self._on_miss_handlers: list[Callable[[str, int], Awaitable[None]]] = []
        self._on_dead_handlers: list[Callable[[str], Awaitable[None]]] = []
        self._on_wake_handlers: list[Callable[[str, str], Awaitable[None]]] = []

    def register(self, config: HeartbeatConfig) -> HeartbeatEntry:
        """Register a new heartbeat monitor for an agent."""
        if config.agent_id in self._entries:
            logger.warning(
                f'Heartbeat already registered for {config.agent_id}, updating config'
            )
            entry = self._entries[config.agent_id]
            entry.config = config
            return entry

        entry = HeartbeatEntry(config=config)
        self._entries[config.agent_id] = entry
        logger.info(
            f'Registered heartbeat for {config.agent_id} '
            f'(interval={config.interval_s}s, max_missed={config.max_missed})'
        )
        return entry

    def unregister(self, agent_id: str) -> bool:
        """Remove heartbeat monitoring for an agent."""
        entry = self._entries.pop(agent_id, None)
        if entry is None:
            return False
        if entry._task is not None:
            entry._task.cancel()
        entry.state = HeartbeatState.STOPPED
        return True

    def beat(self, agent_id: str) -> bool:
        """Record a heartbeat from an agent.

        Returns True if the agent was being monitored.
        """
        entry = self._entries.get(agent_id)
        if entry is None:
            return False

        entry.last_beat_at = time.time()
        entry.total_beats += 1
        entry.missed_count = 0

        if entry.state in (HeartbeatState.MISSED, HeartbeatState.DEAD):
            logger.info(f'Agent {agent_id} recovered from {entry.state.value}')
            entry.state = HeartbeatState.ACTIVE

        return True

    async def check(self, agent_id: str) -> HeartbeatState:
        """Check heartbeat status for an agent and fire handlers if needed."""
        entry = self._entries.get(agent_id)
        if entry is None:
            return HeartbeatState.STOPPED

        if entry.state == HeartbeatState.STOPPED:
            return HeartbeatState.STOPPED

        if entry.state == HeartbeatState.PAUSED:
            return HeartbeatState.PAUSED

        # Skip check during inactive hours
        if not entry.is_in_active_hours:
            return entry.state

        elapsed = entry.seconds_since_last_beat
        if elapsed > entry.config.interval_s:
            # Compute missed count from elapsed time, not check cycles
            expected_missed = int(elapsed / entry.config.interval_s)
            if expected_missed > entry.missed_count:
                new_misses = expected_missed - entry.missed_count
                entry.total_missed += new_misses
                entry.missed_count = expected_missed

            if entry.missed_count >= entry.config.max_missed:
                if entry.state != HeartbeatState.DEAD:
                    entry.state = HeartbeatState.DEAD
                    logger.error(
                        f'Agent {agent_id} declared DEAD '
                        f'({entry.missed_count} missed heartbeats)'
                    )
                    for handler in self._on_dead_handlers:
                        try:
                            await handler(agent_id)
                        except Exception as e:
                            logger.error(f'Dead handler error for {agent_id}: {e}')
            else:
                entry.state = HeartbeatState.MISSED
                logger.warning(
                    f'Agent {agent_id} missed heartbeat '
                    f'({entry.missed_count}/{entry.config.max_missed})'
                )
                for handler in self._on_miss_handlers:
                    try:
                        await handler(agent_id, entry.missed_count)
                    except Exception as e:
                        logger.error(f'Miss handler error for {agent_id}: {e}')
        else:
            if entry.state != HeartbeatState.ACTIVE:
                entry.state = HeartbeatState.ACTIVE

        return entry.state

    async def check_all(self) -> dict[str, HeartbeatState]:
        """Check all registered heartbeats."""
        results: dict[str, HeartbeatState] = {}
        for agent_id in list(self._entries.keys()):
            results[agent_id] = await self.check(agent_id)
        return results

    async def start_monitor(self, check_interval_s: float = 10.0) -> asyncio.Task[None]:
        """Start periodic heartbeat monitoring."""

        async def _monitor() -> None:
            while True:
                try:
                    await asyncio.sleep(check_interval_s)
                    await self.check_all()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f'Heartbeat monitor error: {e}')

        task = asyncio.ensure_future(_monitor())
        return task

    def pause(self, agent_id: str) -> bool:
        """Pause heartbeat monitoring for an agent."""
        entry = self._entries.get(agent_id)
        if entry is None:
            return False
        entry.state = HeartbeatState.PAUSED
        return True

    def resume(self, agent_id: str) -> bool:
        """Resume heartbeat monitoring for an agent."""
        entry = self._entries.get(agent_id)
        if entry is None:
            return False
        entry.state = HeartbeatState.ACTIVE
        entry.missed_count = 0
        return True

    async def wake(self, agent_id: str, reason: str) -> bool:
        """Trigger an event-driven wake for an agent.

        Fires registered wake handlers.
        """
        entry = self._entries.get(agent_id)
        if entry is None:
            return False

        logger.info(f'Wake event for {agent_id}: {reason}')
        for handler in self._on_wake_handlers:
            try:
                await handler(agent_id, reason)
            except Exception as e:
                logger.error(f'Wake handler error for {agent_id}: {e}')

        return True

    def on_miss(self, handler: Callable[[str, int], Awaitable[None]]) -> None:
        """Register a handler for missed heartbeats."""
        self._on_miss_handlers.append(handler)

    def on_dead(self, handler: Callable[[str], Awaitable[None]]) -> None:
        """Register a handler for dead agents."""
        self._on_dead_handlers.append(handler)

    def on_wake(self, handler: Callable[[str, str], Awaitable[None]]) -> None:
        """Register a handler for wake events."""
        self._on_wake_handlers.append(handler)

    def get_prompt_injection(self, agent_id: str) -> str:
        """Get heartbeat prompt text for injection into agent prompt.

        Returns empty string if agent doesn't have prompt injection enabled.
        """
        entry = self._entries.get(agent_id)
        if entry is None or not entry.config.inject_prompt:
            return ''

        return (
            f'[Heartbeat: Report status every {entry.config.interval_s:.0f}s. '
            f'Missed: {entry.missed_count}/{entry.config.max_missed}]'
        )

    # Component health tracking

    def register_component(
        self,
        name: str,
        status: HealthStatus = HealthStatus.UNKNOWN,
    ) -> None:
        """Register a system component for health tracking."""
        self._components[name] = ComponentHealth(
            name=name,
            status=status,
            last_check_at=time.time(),
        )

    def update_component(
        self,
        name: str,
        status: HealthStatus,
        message: str = '',
    ) -> None:
        """Update a component's health status."""
        if name not in self._components:
            self.register_component(name, status)

        comp = self._components[name]
        comp.status = status
        comp.message = message
        comp.last_check_at = time.time()

    def get_overall_health(self) -> HealthStatus:
        """Get the overall system health based on all components."""
        if not self._components:
            return HealthStatus.UNKNOWN

        statuses = [c.status for c in self._components.values()]

        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN

    def stats(self) -> dict[str, Any]:
        """Get heartbeat and health statistics."""
        agent_stats: dict[str, dict[str, Any]] = {}
        for agent_id, entry in self._entries.items():
            agent_stats[agent_id] = {
                'state': entry.state.value,
                'missed_count': entry.missed_count,
                'total_beats': entry.total_beats,
                'total_missed': entry.total_missed,
                'seconds_since_last': round(entry.seconds_since_last_beat, 1),
                'interval_s': entry.config.interval_s,
            }

        component_stats: dict[str, dict[str, Any]] = {}
        for name, comp in self._components.items():
            component_stats[name] = {
                'status': comp.status.value,
                'message': comp.message,
                'last_check_at': comp.last_check_at,
            }

        return {
            'agents': agent_stats,
            'components': component_stats,
            'overall_health': self.get_overall_health().value,
        }
