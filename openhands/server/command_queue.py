"""Lane-based command queue — serialized execution with concurrency control.

Ported from OpenClaw's process/command-queue.ts. Provides:
- Named lanes (main, background, cron) with configurable concurrency
- Task generation tracking for safe restart
- Queue draining for graceful shutdown
- Queue depth monitoring

Per OPERATING_RULES.md RULE 5: No unbounded resources — every queue has max size.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

from openhands.core.logger import openhands_logger as logger

T = TypeVar('T')

# Queue limits
MAX_QUEUE_DEPTH = 1000
DEFAULT_WARN_AFTER_MS = 2000
DEFAULT_MAX_CONCURRENT = 1


class QueueState(Enum):
    """Overall queue system state."""

    RUNNING = 'running'
    DRAINING = 'draining'
    STOPPED = 'stopped'


@dataclass
class QueueEntry:
    """A single task in the queue."""

    task: Callable[[], Awaitable[Any]]
    future: asyncio.Future[Any]
    enqueued_at: float
    warn_after_ms: float = DEFAULT_WARN_AFTER_MS
    lane: str = 'main'
    task_id: int = 0


@dataclass
class LaneState:
    """State of a single queue lane."""

    lane: str
    queue: list[QueueEntry] = field(default_factory=list)
    active_count: int = 0
    max_concurrent: int = DEFAULT_MAX_CONCURRENT
    draining: bool = False
    generation: int = 0
    total_enqueued: int = 0
    total_completed: int = 0
    total_failed: int = 0


class GatewayDrainingError(Exception):
    """Raised when trying to enqueue during gateway drain."""
    pass


class QueueFullError(Exception):
    """Raised when a queue lane is full."""
    pass


class CommandQueue:
    """Lane-based command queue with concurrency control.

    Tasks are organized into named lanes. Each lane has its own queue
    and configurable concurrency limit. Tasks within a lane are
    executed in order, with at most N concurrent tasks per lane.
    """

    def __init__(self) -> None:
        self._lanes: dict[str, LaneState] = {}
        self._state = QueueState.RUNNING
        self._task_counter = 0
        self._lock = asyncio.Lock()

    def _get_lane(self, lane_name: str) -> LaneState:
        """Get or create a lane state."""
        normalized = lane_name.strip().lower() or 'main'
        if normalized not in self._lanes:
            self._lanes[normalized] = LaneState(lane=normalized)
        return self._lanes[normalized]

    async def enqueue(
        self,
        task: Callable[[], Awaitable[T]],
        lane: str = 'main',
        warn_after_ms: float = DEFAULT_WARN_AFTER_MS,
    ) -> T:
        """Enqueue a task for execution in the specified lane.

        Args:
            task: Async callable to execute
            lane: Lane name ('main', 'background', 'cron', etc.)
            warn_after_ms: Log warning if task waits longer than this

        Returns:
            Result of the task execution

        Raises:
            GatewayDrainingError: If the queue is draining
            QueueFullError: If the lane queue is at max depth
        """
        if self._state == QueueState.DRAINING:
            raise GatewayDrainingError('Queue is draining, not accepting new tasks')
        if self._state == QueueState.STOPPED:
            raise GatewayDrainingError('Queue is stopped')

        async with self._lock:
            lane_state = self._get_lane(lane)

            if len(lane_state.queue) >= MAX_QUEUE_DEPTH:
                raise QueueFullError(
                    f'Lane {lane} queue is full ({MAX_QUEUE_DEPTH} tasks)'
                )

            self._task_counter += 1
            loop = asyncio.get_event_loop()
            future: asyncio.Future[Any] = loop.create_future()

            entry = QueueEntry(
                task=task,
                future=future,
                enqueued_at=time.time() * 1000,
                warn_after_ms=warn_after_ms,
                lane=lane,
                task_id=self._task_counter,
            )

            lane_state.queue.append(entry)
            lane_state.total_enqueued += 1

        # Trigger drain outside the lock
        asyncio.ensure_future(self._drain_lane(lane))

        return await future

    async def _drain_lane(self, lane_name: str) -> None:
        """Process queued tasks in a lane up to its concurrency limit."""
        lane_state = self._get_lane(lane_name)

        while lane_state.queue and lane_state.active_count < lane_state.max_concurrent:
            entry = lane_state.queue.pop(0)
            lane_state.active_count += 1

            # Check for long wait warning
            wait_ms = time.time() * 1000 - entry.enqueued_at
            if wait_ms > entry.warn_after_ms:
                logger.warning(
                    f'Task {entry.task_id} in lane {lane_name} waited {wait_ms:.0f}ms '
                    f'(queued ahead: {len(lane_state.queue)})'
                )

            # Execute the task
            asyncio.ensure_future(self._execute_entry(entry, lane_state))

    async def _execute_entry(self, entry: QueueEntry, lane_state: LaneState) -> None:
        """Execute a single queue entry and handle completion."""
        try:
            result = await entry.task()
            if not entry.future.done():
                entry.future.set_result(result)
            lane_state.total_completed += 1
        except Exception as exc:
            if not entry.future.done():
                entry.future.set_exception(exc)
            lane_state.total_failed += 1
        finally:
            lane_state.active_count -= 1
            # Continue draining
            if lane_state.queue:
                asyncio.ensure_future(self._drain_lane(lane_state.lane))

    def set_lane_concurrency(self, lane: str, max_concurrent: int) -> None:
        """Set the maximum concurrency for a lane."""
        lane_state = self._get_lane(lane)
        lane_state.max_concurrent = max(1, max_concurrent)

    def get_queue_size(self, lane: str | None = None) -> int:
        """Get the number of queued (waiting) tasks.

        Args:
            lane: Specific lane to check, or None for total across all lanes
        """
        if lane is not None:
            lane_state = self._lanes.get(lane.strip().lower(), None)
            return len(lane_state.queue) if lane_state else 0

        return sum(len(ls.queue) for ls in self._lanes.values())

    def get_active_count(self, lane: str | None = None) -> int:
        """Get the number of currently executing tasks."""
        if lane is not None:
            lane_state = self._lanes.get(lane.strip().lower(), None)
            return lane_state.active_count if lane_state else 0

        return sum(ls.active_count for ls in self._lanes.values())

    async def drain(self, timeout_ms: int = 30000) -> bool:
        """Start draining — stop accepting new tasks and wait for completion.

        Args:
            timeout_ms: Maximum time to wait for drain in milliseconds

        Returns:
            True if all tasks completed, False if timeout expired
        """
        self._state = QueueState.DRAINING

        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            total_pending = self.get_queue_size() + self.get_active_count()
            if total_pending == 0:
                self._state = QueueState.STOPPED
                return True
            await asyncio.sleep(0.1)

        self._state = QueueState.STOPPED
        remaining = self.get_queue_size() + self.get_active_count()
        if remaining > 0:
            logger.warning(f'Queue drain timed out with {remaining} tasks remaining')
        return remaining == 0

    def stop(self) -> None:
        """Immediately stop the queue — cancel all pending tasks."""
        self._state = QueueState.STOPPED
        for lane_state in self._lanes.values():
            for entry in lane_state.queue:
                if not entry.future.done():
                    entry.future.cancel()
            lane_state.queue.clear()

    def stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        lane_stats = {}
        for name, lane_state in self._lanes.items():
            lane_stats[name] = {
                'queued': len(lane_state.queue),
                'active': lane_state.active_count,
                'max_concurrent': lane_state.max_concurrent,
                'total_enqueued': lane_state.total_enqueued,
                'total_completed': lane_state.total_completed,
                'total_failed': lane_state.total_failed,
                'generation': lane_state.generation,
            }

        return {
            'state': self._state.value,
            'total_queued': self.get_queue_size(),
            'total_active': self.get_active_count(),
            'lanes': lane_stats,
        }
