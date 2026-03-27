"""Execution Trace — records the full execution path of a task.

Every phase transition, decision, tool call, and outcome is recorded
in the execution trace. This provides:
- Full audit trail of what happened
- Performance data for optimization
- Debugging information for failures
- Input for the artifact builder

Patterns extracted from:
    - LangGraph: State checkpoint persistence
    - OpenHands: EventStream event recording
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class TraceEventType(Enum):
    """Types of events in the execution trace."""

    PHASE_START = 'phase_start'
    PHASE_END = 'phase_end'
    ROLE_START = 'role_start'
    ROLE_END = 'role_end'
    TOOL_CALL = 'tool_call'
    TOOL_RESULT = 'tool_result'
    DECISION = 'decision'
    ERROR = 'error'
    RETRY = 'retry'
    MEMORY_ACCESS = 'memory_access'
    RISK_ASSESSMENT = 'risk_assessment'
    ESCALATION = 'escalation'
    ARTIFACT_CREATED = 'artifact_created'
    CUSTOM = 'custom'


@dataclass
class TraceEvent:
    """A single event in the execution trace."""

    event_type: TraceEventType
    name: str = ''
    timestamp: float = field(default_factory=time.time)
    duration_s: float = 0.0
    success: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ''
    parent_event_id: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'type': self.event_type.value,
            'name': self.name,
            'timestamp': self.timestamp,
            'duration_s': self.duration_s,
            'success': self.success,
            'error': self.error,
        }


class ExecutionTrace:
    """Records the full execution path of a task.

    Usage:
        trace = ExecutionTrace(task_id='task-123')

        # Record phase start
        trace.record_phase_start('execute')

        # Record tool call
        trace.record_tool_call('file_write', {'path': 'src/main.py'})

        # Record phase end
        trace.record_phase_end('execute', success=True)

        # Get full trace
        timeline = trace.get_timeline()
        summary = trace.get_summary()
    """

    def __init__(self, task_id: str = '') -> None:
        self._task_id = task_id
        self._events: list[TraceEvent] = []
        self._phase_starts: dict[str, float] = {}
        self._role_starts: dict[str, float] = {}
        self._start_time = time.time()

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def event_count(self) -> int:
        return len(self._events)

    @property
    def duration_s(self) -> float:
        return time.time() - self._start_time

    def record_phase_start(self, phase: str) -> None:
        """Record the start of a phase."""
        self._phase_starts[phase] = time.time()
        self._events.append(TraceEvent(
            event_type=TraceEventType.PHASE_START,
            name=phase,
        ))

    def record_phase_end(
        self, phase: str, success: bool = True, error: str = ''
    ) -> None:
        """Record the end of a phase."""
        start = self._phase_starts.pop(phase, time.time())
        duration = time.time() - start
        self._events.append(TraceEvent(
            event_type=TraceEventType.PHASE_END,
            name=phase,
            duration_s=duration,
            success=success,
            error=error,
        ))

    def record_role_start(self, role: str) -> None:
        """Record the start of a role execution."""
        self._role_starts[role] = time.time()
        self._events.append(TraceEvent(
            event_type=TraceEventType.ROLE_START,
            name=role,
        ))

    def record_role_end(
        self, role: str, success: bool = True, error: str = ''
    ) -> None:
        """Record the end of a role execution."""
        start = self._role_starts.pop(role, time.time())
        duration = time.time() - start
        self._events.append(TraceEvent(
            event_type=TraceEventType.ROLE_END,
            name=role,
            duration_s=duration,
            success=success,
            error=error,
        ))

    def record_tool_call(
        self, tool_name: str, params: dict[str, Any] | None = None
    ) -> None:
        """Record a tool invocation."""
        self._events.append(TraceEvent(
            event_type=TraceEventType.TOOL_CALL,
            name=tool_name,
            data=params or {},
        ))

    def record_tool_result(
        self, tool_name: str, success: bool = True, error: str = ''
    ) -> None:
        """Record a tool result."""
        self._events.append(TraceEvent(
            event_type=TraceEventType.TOOL_RESULT,
            name=tool_name,
            success=success,
            error=error,
        ))

    def record_decision(
        self, description: str, chosen: str, alternatives: list[str] | None = None
    ) -> None:
        """Record a decision point."""
        self._events.append(TraceEvent(
            event_type=TraceEventType.DECISION,
            name=description,
            data={
                'chosen': chosen,
                'alternatives': alternatives or [],
            },
        ))

    def record_error(self, error: str, phase: str = '', recoverable: bool = True) -> None:
        """Record an error."""
        self._events.append(TraceEvent(
            event_type=TraceEventType.ERROR,
            name=phase or 'unknown',
            error=error,
            data={'recoverable': recoverable},
        ))

    def record_retry(self, attempt: int, strategy: str = '', reason: str = '') -> None:
        """Record a retry attempt."""
        self._events.append(TraceEvent(
            event_type=TraceEventType.RETRY,
            name=f'retry_{attempt}',
            data={'attempt': attempt, 'strategy': strategy, 'reason': reason},
        ))

    def record_custom(self, name: str, data: dict[str, Any] | None = None) -> None:
        """Record a custom event."""
        self._events.append(TraceEvent(
            event_type=TraceEventType.CUSTOM,
            name=name,
            data=data or {},
        ))

    def get_timeline(self) -> list[dict[str, Any]]:
        """Get the full timeline of events."""
        return [e.to_dict() for e in self._events]

    def get_phase_durations(self) -> dict[str, float]:
        """Get duration of each completed phase."""
        durations: dict[str, float] = {}
        for event in self._events:
            if event.event_type == TraceEventType.PHASE_END:
                durations[event.name] = event.duration_s
        return durations

    def get_errors(self) -> list[dict[str, Any]]:
        """Get all recorded errors."""
        return [
            e.to_dict() for e in self._events
            if e.event_type == TraceEventType.ERROR
        ]

    def get_decisions(self) -> list[dict[str, Any]]:
        """Get all recorded decisions."""
        return [
            {'name': e.name, **e.data}
            for e in self._events
            if e.event_type == TraceEventType.DECISION
        ]

    def get_retry_count(self) -> int:
        """Get total number of retries."""
        return sum(
            1 for e in self._events
            if e.event_type == TraceEventType.RETRY
        )

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the execution trace."""
        phases_completed = sum(
            1 for e in self._events
            if e.event_type == TraceEventType.PHASE_END and e.success
        )
        phases_failed = sum(
            1 for e in self._events
            if e.event_type == TraceEventType.PHASE_END and not e.success
        )
        tool_calls = sum(
            1 for e in self._events
            if e.event_type == TraceEventType.TOOL_CALL
        )

        return {
            'task_id': self._task_id,
            'total_events': len(self._events),
            'duration_s': self.duration_s,
            'phases_completed': phases_completed,
            'phases_failed': phases_failed,
            'tool_calls': tool_calls,
            'errors': len(self.get_errors()),
            'retries': self.get_retry_count(),
            'decisions': len(self.get_decisions()),
            'phase_durations': self.get_phase_durations(),
        }

    def to_text(self) -> str:
        """Generate a human-readable text representation of the trace."""
        lines: list[str] = []
        lines.append(f'# Execution Trace: {self._task_id}')
        lines.append(f'Duration: {self.duration_s:.2f}s')
        lines.append(f'Events: {len(self._events)}')
        lines.append('')

        for event in self._events:
            ts = event.timestamp - self._start_time
            status = 'OK' if event.success else 'FAIL'
            line = f'[{ts:8.2f}s] {event.event_type.value:20s} {event.name}'
            if event.duration_s > 0:
                line += f' ({event.duration_s:.2f}s)'
            if not event.success:
                line += f' [{status}]'
            if event.error:
                line += f' — {event.error[:80]}'
            lines.append(line)

        return '\n'.join(lines)
