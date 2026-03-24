"""Sub-agent spawning and lifecycle management.

Ported from OpenClaw's sub-agent orchestration patterns. Provides:
- Sub-agent registry with lifecycle tracking
- Parallel spawning with depth limits
- Announce/completion queue for inter-agent messaging
- Orphan recovery for crashed sub-agents
- TTL-based timeout enforcement

Per OPERATING_RULES.md RULE 5: No unbounded resources — depth limits, TTL, max agents.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from openhands.core.logger import openhands_logger as logger

# Sub-agent limits
MAX_SUBAGENT_DEPTH = 5  # Maximum nesting depth
MAX_CONCURRENT_SUBAGENTS = 10  # Maximum concurrent sub-agents per parent
DEFAULT_TTL_MS = 300000  # 5 minutes default TTL
ORPHAN_CHECK_INTERVAL_S = 30.0  # Check for orphans every 30s


class SubagentState(Enum):
    """Lifecycle state of a sub-agent."""

    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    TIMEOUT = 'timeout'
    CANCELLED = 'cancelled'
    ORPHANED = 'orphaned'


@dataclass
class SubagentResult:
    """Result from a completed sub-agent."""

    subagent_id: str
    state: SubagentState
    output: str = ''
    error: str = ''
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubagentEntry:
    """Registry entry for a sub-agent."""

    subagent_id: str
    parent_id: str
    task: str
    state: SubagentState = SubagentState.PENDING
    depth: int = 0
    ttl_ms: float = DEFAULT_TTL_MS
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    result: SubagentResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _future: asyncio.Future[SubagentResult] | None = field(
        default=None, repr=False
    )

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time() * 1000

    @property
    def is_terminal(self) -> bool:
        """Whether the sub-agent is in a terminal state."""
        return self.state in (
            SubagentState.COMPLETED,
            SubagentState.FAILED,
            SubagentState.TIMEOUT,
            SubagentState.CANCELLED,
            SubagentState.ORPHANED,
        )

    @property
    def elapsed_ms(self) -> float:
        """Time since creation in milliseconds."""
        return time.time() * 1000 - self.created_at

    @property
    def is_expired(self) -> bool:
        """Whether the sub-agent has exceeded its TTL."""
        return self.ttl_ms > 0 and self.elapsed_ms > self.ttl_ms


@dataclass
class SpawnRequest:
    """Request to spawn a sub-agent."""

    parent_id: str
    task: str
    ttl_ms: float = DEFAULT_TTL_MS
    metadata: dict[str, Any] = field(default_factory=dict)


class SubagentRegistry:
    """Central registry for managing sub-agent lifecycle.

    Tracks all sub-agents, enforces depth/concurrency limits,
    handles timeouts, and provides orphan recovery.
    """

    def __init__(
        self,
        max_depth: int = MAX_SUBAGENT_DEPTH,
        max_concurrent: int = MAX_CONCURRENT_SUBAGENTS,
    ):
        self._entries: dict[str, SubagentEntry] = {}
        self._children: dict[str, list[str]] = {}  # parent_id → [child_ids]
        self._max_depth = max_depth
        self._max_concurrent = max_concurrent
        self._lock = asyncio.Lock()
        self._orphan_task: asyncio.Task[None] | None = None

    async def spawn(
        self,
        request: SpawnRequest,
        executor: Callable[[SubagentEntry], Awaitable[SubagentResult]],
    ) -> SubagentEntry:
        """Spawn a new sub-agent.

        Args:
            request: Spawn configuration
            executor: Async function that runs the sub-agent

        Returns:
            SubagentEntry for the new sub-agent

        Raises:
            SubagentDepthError: If max depth exceeded
            SubagentLimitError: If max concurrent agents exceeded
        """
        async with self._lock:
            # Check depth
            depth = self._get_depth(request.parent_id)
            if depth >= self._max_depth:
                raise SubagentDepthError(
                    f'Maximum sub-agent depth ({self._max_depth}) exceeded'
                )

            # Check concurrency
            active = self._count_active(request.parent_id)
            if active >= self._max_concurrent:
                raise SubagentLimitError(
                    f'Maximum concurrent sub-agents ({self._max_concurrent}) '
                    f'for parent {request.parent_id} exceeded'
                )

            # Create entry
            subagent_id = f'subagent-{uuid.uuid4().hex[:12]}'
            loop = asyncio.get_event_loop()
            future: asyncio.Future[SubagentResult] = loop.create_future()

            entry = SubagentEntry(
                subagent_id=subagent_id,
                parent_id=request.parent_id,
                task=request.task,
                depth=depth + 1,
                ttl_ms=request.ttl_ms,
                metadata=request.metadata,
                _future=future,
            )

            self._entries[subagent_id] = entry

            if request.parent_id not in self._children:
                self._children[request.parent_id] = []
            self._children[request.parent_id].append(subagent_id)

        # Execute outside the lock
        asyncio.ensure_future(self._run_subagent(entry, executor))

        logger.info(
            f'Spawned sub-agent {subagent_id} (parent={request.parent_id}, '
            f'depth={entry.depth}, ttl={request.ttl_ms}ms)'
        )

        return entry

    async def _run_subagent(
        self,
        entry: SubagentEntry,
        executor: Callable[[SubagentEntry], Awaitable[SubagentResult]],
    ) -> None:
        """Execute a sub-agent with TTL enforcement."""
        entry.state = SubagentState.RUNNING
        entry.started_at = time.time() * 1000

        try:
            if entry.ttl_ms > 0:
                result = await asyncio.wait_for(
                    executor(entry),
                    timeout=entry.ttl_ms / 1000,
                )
            else:
                result = await executor(entry)

            entry.state = SubagentState.COMPLETED
            entry.result = result

        except asyncio.TimeoutError:
            entry.state = SubagentState.TIMEOUT
            entry.result = SubagentResult(
                subagent_id=entry.subagent_id,
                state=SubagentState.TIMEOUT,
                error=f'Sub-agent exceeded TTL of {entry.ttl_ms}ms',
            )
            logger.warning(f'Sub-agent {entry.subagent_id} timed out')

        except asyncio.CancelledError:
            entry.state = SubagentState.CANCELLED
            entry.result = SubagentResult(
                subagent_id=entry.subagent_id,
                state=SubagentState.CANCELLED,
                error='Sub-agent was cancelled',
            )

        except Exception as e:
            entry.state = SubagentState.FAILED
            entry.result = SubagentResult(
                subagent_id=entry.subagent_id,
                state=SubagentState.FAILED,
                error=str(e),
            )
            logger.error(f'Sub-agent {entry.subagent_id} failed: {e}')

        finally:
            entry.completed_at = time.time() * 1000
            if entry.result is not None:
                entry.result.duration_ms = entry.completed_at - entry.started_at

            # Resolve the future
            if entry._future is not None and not entry._future.done():
                if entry.result is not None:
                    entry._future.set_result(entry.result)
                else:
                    entry._future.set_result(
                        SubagentResult(
                            subagent_id=entry.subagent_id,
                            state=entry.state,
                        )
                    )

    async def wait_for(self, subagent_id: str) -> SubagentResult:
        """Wait for a sub-agent to complete.

        Args:
            subagent_id: ID of the sub-agent to wait for

        Returns:
            SubagentResult with the outcome
        """
        entry = self._entries.get(subagent_id)
        if entry is None:
            raise SubagentNotFoundError(f'Sub-agent {subagent_id} not found')

        if entry.is_terminal and entry.result is not None:
            return entry.result

        if entry._future is not None:
            return await entry._future

        raise SubagentNotFoundError(
            f'Sub-agent {subagent_id} has no future to wait on'
        )

    async def wait_all(self, parent_id: str) -> list[SubagentResult]:
        """Wait for all sub-agents of a parent to complete."""
        child_ids = self._children.get(parent_id, [])
        results: list[SubagentResult] = []
        for child_id in child_ids:
            result = await self.wait_for(child_id)
            results.append(result)
        return results

    def cancel(self, subagent_id: str) -> bool:
        """Cancel a running sub-agent."""
        entry = self._entries.get(subagent_id)
        if entry is None or entry.is_terminal:
            return False

        entry.state = SubagentState.CANCELLED
        if entry._future is not None and not entry._future.done():
            entry._future.cancel()
        return True

    def cancel_children(self, parent_id: str) -> int:
        """Cancel all sub-agents of a parent."""
        child_ids = self._children.get(parent_id, [])
        cancelled = 0
        for child_id in child_ids:
            if self.cancel(child_id):
                cancelled += 1
        return cancelled

    def get(self, subagent_id: str) -> SubagentEntry | None:
        """Get a sub-agent entry by ID."""
        return self._entries.get(subagent_id)

    def get_children(self, parent_id: str) -> list[SubagentEntry]:
        """Get all sub-agents for a parent."""
        child_ids = self._children.get(parent_id, [])
        return [
            self._entries[cid]
            for cid in child_ids
            if cid in self._entries
        ]

    def get_active(self) -> list[SubagentEntry]:
        """Get all non-terminal sub-agents."""
        return [
            entry
            for entry in self._entries.values()
            if not entry.is_terminal
        ]

    def _get_depth(self, agent_id: str) -> int:
        """Get the depth of an agent in the hierarchy."""
        entry = self._entries.get(agent_id)
        if entry is None:
            return 0
        return entry.depth

    def _count_active(self, parent_id: str) -> int:
        """Count active (non-terminal) sub-agents for a parent."""
        child_ids = self._children.get(parent_id, [])
        return sum(
            1
            for cid in child_ids
            if cid in self._entries and not self._entries[cid].is_terminal
        )

    async def check_orphans(self) -> list[str]:
        """Check for and recover orphaned sub-agents.

        An orphan is a running sub-agent whose parent is terminal or missing.
        """
        orphaned: list[str] = []
        for entry in self._entries.values():
            if entry.is_terminal:
                continue

            parent = self._entries.get(entry.parent_id)
            # Parent is either unknown (root) or terminal — check if this is a real orphan
            if parent is not None and parent.is_terminal:
                entry.state = SubagentState.ORPHANED
                entry.result = SubagentResult(
                    subagent_id=entry.subagent_id,
                    state=SubagentState.ORPHANED,
                    error='Parent agent terminated',
                )
                if entry._future is not None and not entry._future.done():
                    entry._future.set_result(entry.result)
                orphaned.append(entry.subagent_id)
                logger.warning(
                    f'Recovered orphaned sub-agent {entry.subagent_id} '
                    f'(parent {entry.parent_id} is terminal)'
                )

        return orphaned

    async def start_orphan_monitor(self) -> None:
        """Start periodic orphan checking."""
        if self._orphan_task is not None:
            return

        async def _monitor() -> None:
            while True:
                try:
                    await asyncio.sleep(ORPHAN_CHECK_INTERVAL_S)
                    await self.check_orphans()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f'Orphan monitor error: {e}')

        self._orphan_task = asyncio.ensure_future(_monitor())

    async def stop_orphan_monitor(self) -> None:
        """Stop the orphan monitor."""
        if self._orphan_task is not None:
            self._orphan_task.cancel()
            try:
                await self._orphan_task
            except asyncio.CancelledError:
                pass
            self._orphan_task = None

    def stats(self) -> dict[str, Any]:
        """Get sub-agent registry statistics."""
        by_state: dict[str, int] = {}
        for entry in self._entries.values():
            state_name = entry.state.value
            by_state[state_name] = by_state.get(state_name, 0) + 1

        return {
            'total': len(self._entries),
            'active': len(self.get_active()),
            'by_state': by_state,
            'max_depth': self._max_depth,
            'max_concurrent': self._max_concurrent,
        }


class SubagentDepthError(Exception):
    """Raised when maximum sub-agent nesting depth is exceeded."""
    pass


class SubagentLimitError(Exception):
    """Raised when maximum concurrent sub-agent limit is exceeded."""
    pass


class SubagentNotFoundError(Exception):
    """Raised when a sub-agent ID is not found."""
    pass
