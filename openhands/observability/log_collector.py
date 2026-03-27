"""Log Collector — aggregates logs from all subsystems.

Collects structured logs from execution engine, agents, memory,
policy, and workflow subsystems into a unified log stream.
Supports filtering, searching, and export.

Patterns extracted from:
    - OpenHands: EventStream logging
    - LangGraph: State transition logging
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class LogLevel(Enum):
    """Log severity levels."""

    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class LogSource(Enum):
    """Source subsystems for logs."""

    EXECUTION = 'execution'
    AGENT = 'agent'
    MEMORY = 'memory'
    POLICY = 'policy'
    WORKFLOW = 'workflow'
    REPO_INTEL = 'repo_intel'
    OBSERVABILITY = 'observability'
    PLATFORM = 'platform'
    SYSTEM = 'system'


@dataclass
class LogEntry:
    """A single log entry."""

    level: LogLevel
    source: LogSource
    message: str
    timestamp: float = field(default_factory=time.time)
    task_id: str = ''
    phase: str = ''
    role: str = ''
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'level': self.level.value,
            'source': self.source.value,
            'message': self.message,
            'timestamp': self.timestamp,
            'task_id': self.task_id,
            'phase': self.phase,
            'role': self.role,
        }

    def to_text(self) -> str:
        parts = [
            f'[{self.level.value.upper():8s}]',
            f'[{self.source.value:12s}]',
        ]
        if self.task_id:
            parts.append(f'[{self.task_id}]')
        if self.phase:
            parts.append(f'[{self.phase}]')
        if self.role:
            parts.append(f'[{self.role}]')
        parts.append(self.message)
        return ' '.join(parts)


class LogCollector:
    """Aggregates logs from all subsystems.

    Usage:
        collector = LogCollector()
        collector.info(LogSource.EXECUTION, 'Task started', task_id='t-1')
        collector.error(LogSource.AGENT, 'Role failed', task_id='t-1', role='coder')

        # Query logs
        errors = collector.get_errors()
        task_logs = collector.get_by_task('t-1')

        # Export
        text = collector.export_text()
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: list[LogEntry] = []
        self._max_entries = max_entries
        self._by_task: dict[str, list[LogEntry]] = {}
        self._error_count = 0

    def log(
        self,
        level: LogLevel,
        source: LogSource,
        message: str,
        task_id: str = '',
        phase: str = '',
        role: str = '',
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add a log entry."""
        if len(self._entries) >= self._max_entries:
            self._entries = self._entries[self._max_entries // 2:]

        entry = LogEntry(
            level=level,
            source=source,
            message=message,
            task_id=task_id,
            phase=phase,
            role=role,
            data=data or {},
        )

        self._entries.append(entry)

        if task_id:
            if task_id not in self._by_task:
                self._by_task[task_id] = []
            self._by_task[task_id].append(entry)

        if level in (LogLevel.ERROR, LogLevel.CRITICAL):
            self._error_count += 1

    def debug(self, source: LogSource, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.DEBUG, source, message, **kwargs)

    def info(self, source: LogSource, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.INFO, source, message, **kwargs)

    def warning(self, source: LogSource, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.WARNING, source, message, **kwargs)

    def error(self, source: LogSource, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.ERROR, source, message, **kwargs)

    def critical(self, source: LogSource, message: str, **kwargs: Any) -> None:
        self.log(LogLevel.CRITICAL, source, message, **kwargs)

    def get_errors(self, limit: int = 50) -> list[LogEntry]:
        """Get recent error and critical logs."""
        return [
            e for e in self._entries
            if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)
        ][-limit:]

    def get_by_task(self, task_id: str) -> list[LogEntry]:
        """Get all logs for a specific task."""
        return list(self._by_task.get(task_id, []))

    def get_by_source(self, source: LogSource, limit: int = 100) -> list[LogEntry]:
        """Get logs from a specific source."""
        return [
            e for e in self._entries
            if e.source == source
        ][-limit:]

    def get_by_phase(self, phase: str, task_id: str = '') -> list[LogEntry]:
        """Get logs for a specific phase."""
        return [
            e for e in self._entries
            if e.phase == phase and (not task_id or e.task_id == task_id)
        ]

    def get_recent(self, limit: int = 100) -> list[LogEntry]:
        """Get the most recent log entries."""
        return self._entries[-limit:]

    def search(self, query: str, limit: int = 50) -> list[LogEntry]:
        """Search logs by message content."""
        query_lower = query.lower()
        return [
            e for e in self._entries
            if query_lower in e.message.lower()
        ][-limit:]

    def export_text(self, task_id: str = '') -> str:
        """Export logs as plain text."""
        entries = self.get_by_task(task_id) if task_id else self._entries
        return '\n'.join(e.to_text() for e in entries)

    def export_json(self, task_id: str = '') -> list[dict[str, Any]]:
        """Export logs as JSON-serializable dicts."""
        entries = self.get_by_task(task_id) if task_id else self._entries
        return [e.to_dict() for e in entries]

    @property
    def total_entries(self) -> int:
        return len(self._entries)

    @property
    def error_count(self) -> int:
        return self._error_count

    def stats(self) -> dict[str, Any]:
        """Get collector statistics."""
        by_level: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for e in self._entries:
            by_level[e.level.value] = by_level.get(e.level.value, 0) + 1
            by_source[e.source.value] = by_source.get(e.source.value, 0) + 1

        return {
            'total_entries': self.total_entries,
            'error_count': self._error_count,
            'tasks_tracked': len(self._by_task),
            'by_level': by_level,
            'by_source': by_source,
        }
