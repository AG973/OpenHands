"""Task Queue — accepts, prioritizes, and dispatches tasks.

Provides the entry point for the SaaS platform. Tasks are submitted,
validated, prioritized, and dispatched to the execution engine.
Supports multiple projects, priority levels, and concurrency limits.

Patterns extracted from:
    - Celery: Task queue with priority and routing
    - GPT-Pilot: Project-scoped task management
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class QueuePriority(Enum):
    """Task priority levels."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class QueueStatus(Enum):
    """Status of a queued task."""

    PENDING = 'pending'
    DISPATCHED = 'dispatched'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    TIMEOUT = 'timeout'


@dataclass
class QueueEntry:
    """A task entry in the queue."""

    queue_id: str = field(default_factory=lambda: f'q-{uuid.uuid4().hex[:12]}')
    task_id: str = ''
    project_id: str = ''
    title: str = ''
    description: str = ''
    priority: QueuePriority = QueuePriority.NORMAL
    status: QueueStatus = QueueStatus.PENDING
    submitted_at: float = field(default_factory=time.time)
    dispatched_at: float = 0.0
    completed_at: float = 0.0
    timeout_s: float = 3600.0  # 1 hour default
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def wait_time_s(self) -> float:
        if self.dispatched_at:
            return self.dispatched_at - self.submitted_at
        return time.time() - self.submitted_at

    @property
    def execution_time_s(self) -> float:
        if not self.dispatched_at:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.dispatched_at

    def to_dict(self) -> dict[str, Any]:
        return {
            'queue_id': self.queue_id,
            'task_id': self.task_id,
            'project_id': self.project_id,
            'title': self.title,
            'priority': self.priority.value,
            'status': self.status.value,
            'wait_time_s': self.wait_time_s,
            'execution_time_s': self.execution_time_s,
        }


class TaskQueue:
    """Priority task queue for the SaaS platform.

    Usage:
        queue = TaskQueue(max_concurrent=5)

        # Submit a task
        entry = queue.submit(
            title='Fix login bug',
            project_id='proj-1',
            priority=QueuePriority.HIGH,
        )

        # Dispatch next task
        next_task = queue.dispatch()
        if next_task:
            # Execute the task
            pass

        # Mark complete
        queue.complete(next_task.queue_id)
    """

    def __init__(self, max_concurrent: int = 10) -> None:
        self._entries: dict[str, QueueEntry] = {}
        self._pending: dict[int, deque[str]] = {
            p.value: deque() for p in QueuePriority
        }
        self._running: set[str] = set()
        self._max_concurrent = max_concurrent

    def submit(
        self,
        title: str,
        project_id: str = '',
        description: str = '',
        priority: QueuePriority = QueuePriority.NORMAL,
        task_id: str = '',
        timeout_s: float = 3600.0,
        metadata: dict[str, Any] | None = None,
    ) -> QueueEntry:
        """Submit a task to the queue.

        Returns:
            QueueEntry with the assigned queue_id
        """
        entry = QueueEntry(
            task_id=task_id or f'task-{uuid.uuid4().hex[:8]}',
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
            timeout_s=timeout_s,
            metadata=metadata or {},
        )

        self._entries[entry.queue_id] = entry
        self._pending[priority.value].append(entry.queue_id)

        logger.info(
            f'[TaskQueue] Submitted: {entry.queue_id} — "{title}" '
            f'(priority={priority.name})'
        )
        return entry

    def dispatch(self) -> QueueEntry | None:
        """Dispatch the next highest-priority pending task.

        Returns:
            QueueEntry if a task is available, None if queue is empty
            or max concurrent tasks reached.
        """
        if len(self._running) >= self._max_concurrent:
            logger.info('[TaskQueue] Max concurrent tasks reached')
            return None

        # Find next task by priority
        for priority_val in sorted(self._pending.keys()):
            queue = self._pending[priority_val]
            while queue:
                queue_id = queue.popleft()
                entry = self._entries.get(queue_id)
                if entry and entry.status == QueueStatus.PENDING:
                    entry.status = QueueStatus.DISPATCHED
                    entry.dispatched_at = time.time()
                    self._running.add(queue_id)
                    logger.info(
                        f'[TaskQueue] Dispatched: {queue_id} — "{entry.title}"'
                    )
                    return entry

        return None

    def mark_running(self, queue_id: str) -> bool:
        """Mark a task as running."""
        entry = self._entries.get(queue_id)
        if entry and entry.status == QueueStatus.DISPATCHED:
            entry.status = QueueStatus.RUNNING
            return True
        return False

    def complete(self, queue_id: str, success: bool = True) -> bool:
        """Mark a task as completed or failed."""
        entry = self._entries.get(queue_id)
        if entry is None:
            return False

        entry.status = QueueStatus.COMPLETED if success else QueueStatus.FAILED
        entry.completed_at = time.time()
        self._running.discard(queue_id)

        logger.info(
            f'[TaskQueue] {"Completed" if success else "Failed"}: {queue_id} '
            f'(execution={entry.execution_time_s:.2f}s)'
        )
        return True

    def cancel(self, queue_id: str) -> bool:
        """Cancel a pending or running task."""
        entry = self._entries.get(queue_id)
        if entry is None:
            return False

        entry.status = QueueStatus.CANCELLED
        entry.completed_at = time.time()
        self._running.discard(queue_id)

        # Remove from pending queues
        for queue in self._pending.values():
            try:
                queue.remove(queue_id)
            except ValueError:
                pass

        return True

    def requeue(self, queue_id: str) -> bool:
        """Requeue a failed task for retry."""
        entry = self._entries.get(queue_id)
        if entry is None or entry.retry_count >= entry.max_retries:
            return False

        entry.status = QueueStatus.PENDING
        entry.retry_count += 1
        entry.dispatched_at = 0.0
        entry.completed_at = 0.0
        self._running.discard(queue_id)
        self._pending[entry.priority.value].append(queue_id)

        logger.info(
            f'[TaskQueue] Requeued: {queue_id} (retry {entry.retry_count}/{entry.max_retries})'
        )
        return True

    def get_entry(self, queue_id: str) -> QueueEntry | None:
        """Get a queue entry by ID."""
        return self._entries.get(queue_id)

    def get_pending(self) -> list[QueueEntry]:
        """Get all pending tasks sorted by priority."""
        pending: list[QueueEntry] = []
        for priority_val in sorted(self._pending.keys()):
            for qid in self._pending[priority_val]:
                entry = self._entries.get(qid)
                if entry and entry.status == QueueStatus.PENDING:
                    pending.append(entry)
        return pending

    def get_running(self) -> list[QueueEntry]:
        """Get all currently running tasks."""
        return [
            self._entries[qid]
            for qid in self._running
            if qid in self._entries
        ]

    def get_by_project(self, project_id: str) -> list[QueueEntry]:
        """Get all tasks for a project."""
        return [
            e for e in self._entries.values()
            if e.project_id == project_id
        ]

    def check_timeouts(self) -> list[str]:
        """Check for timed-out tasks and mark them."""
        timed_out: list[str] = []
        now = time.time()

        for qid in list(self._running):
            entry = self._entries.get(qid)
            if entry and entry.dispatched_at:
                elapsed = now - entry.dispatched_at
                if elapsed > entry.timeout_s:
                    entry.status = QueueStatus.TIMEOUT
                    entry.completed_at = now
                    self._running.discard(qid)
                    timed_out.append(qid)

        if timed_out:
            logger.warning(f'[TaskQueue] {len(timed_out)} tasks timed out')

        return timed_out

    @property
    def pending_count(self) -> int:
        return sum(len(q) for q in self._pending.values())

    @property
    def running_count(self) -> int:
        return len(self._running)

    def stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        status_counts: dict[str, int] = {}
        for entry in self._entries.values():
            sv = entry.status.value
            status_counts[sv] = status_counts.get(sv, 0) + 1

        return {
            'total_tasks': len(self._entries),
            'pending': self.pending_count,
            'running': self.running_count,
            'max_concurrent': self._max_concurrent,
            'by_status': status_counts,
        }
