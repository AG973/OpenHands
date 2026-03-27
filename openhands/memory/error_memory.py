"""Error Memory — persistent storage and retrieval of past errors.

Stores error patterns with classification, context, and resolution status.
Used by the DebuggerAgent to find similar past failures and by the
execution engine to avoid repeating known-bad approaches.

Memory MUST change decisions — this is not passive storage.

Patterns extracted from:
    - GPT-Pilot: Error tracking across development cycles
    - OpenHands: StuckDetector repetition detection
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class ErrorEntry:
    """A single error record in memory."""

    error_id: str = ''
    error_type: str = ''  # import_error, syntax_error, type_error, etc.
    error_message: str = ''
    stack_trace: str = ''
    file_path: str = ''
    line_number: int = 0
    task_id: str = ''
    phase: str = ''
    timestamp: float = field(default_factory=time.time)
    resolution: str = ''  # 'fixed', 'workaround', 'unresolved'
    fix_applied: str = ''
    fix_successful: bool = False
    occurrence_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        """Unique fingerprint for deduplication."""
        raw = f'{self.error_type}:{self.error_message[:100]}:{self.file_path}'
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            'error_id': self.error_id,
            'error_type': self.error_type,
            'error_message': self.error_message[:200],
            'file_path': self.file_path,
            'resolution': self.resolution,
            'fix_applied': self.fix_applied,
            'fix_successful': self.fix_successful,
            'occurrence_count': self.occurrence_count,
        }


class ErrorMemory:
    """Persistent error memory that influences decision-making.

    Usage:
        mem = ErrorMemory()
        mem.record(ErrorEntry(error_type='import_error', error_message='...'))
        similar = mem.find_similar('import_error', 'ModuleNotFoundError')
        if similar:
            # Use past resolution to guide current fix
            past_fix = similar[0].fix_applied
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._entries: dict[str, ErrorEntry] = {}
        self._max_entries = max_entries
        self._by_type: dict[str, list[str]] = {}
        self._by_file: dict[str, list[str]] = {}

    def record(self, entry: ErrorEntry) -> str:
        """Record an error in memory.

        If a similar error already exists (same fingerprint), increment
        the occurrence count instead of creating a duplicate.

        Returns:
            The error_id of the recorded entry
        """
        fp = entry.fingerprint

        # Check for duplicate
        if fp in self._entries:
            existing = self._entries[fp]
            existing.occurrence_count += 1
            existing.timestamp = time.time()
            logger.info(
                f'[ErrorMemory] Duplicate error (count={existing.occurrence_count}): '
                f'{entry.error_type}'
            )
            return existing.error_id

        # Enforce max entries (evict oldest)
        if len(self._entries) >= self._max_entries:
            self._evict_oldest()

        entry.error_id = fp
        self._entries[fp] = entry

        # Index by type
        if entry.error_type not in self._by_type:
            self._by_type[entry.error_type] = []
        self._by_type[entry.error_type].append(fp)

        # Index by file
        if entry.file_path:
            if entry.file_path not in self._by_file:
                self._by_file[entry.file_path] = []
            self._by_file[entry.file_path].append(fp)

        logger.info(
            f'[ErrorMemory] Recorded: {entry.error_type} in {entry.file_path or "unknown"}'
        )
        return fp

    def find_similar(
        self,
        error_type: str = '',
        error_message: str = '',
        file_path: str = '',
        limit: int = 5,
    ) -> list[ErrorEntry]:
        """Find similar past errors.

        Searches by error type, message content, and file path.
        Returns entries sorted by relevance (occurrence count * recency).
        """
        candidates: list[ErrorEntry] = []

        # Search by type
        if error_type and error_type in self._by_type:
            for eid in self._by_type[error_type]:
                if eid in self._entries:
                    candidates.append(self._entries[eid])

        # Search by file
        if file_path and file_path in self._by_file:
            for eid in self._by_file[file_path]:
                if eid in self._entries and self._entries[eid] not in candidates:
                    candidates.append(self._entries[eid])

        # Search by message content
        if error_message:
            msg_lower = error_message.lower()
            for entry in self._entries.values():
                if (
                    msg_lower in entry.error_message.lower()
                    and entry not in candidates
                ):
                    candidates.append(entry)

        # Score and sort
        def score(e: ErrorEntry) -> float:
            s = e.occurrence_count * 0.5
            age_hours = (time.time() - e.timestamp) / 3600
            s += max(0, 10 - age_hours) * 0.3  # Recency bonus
            if e.fix_successful:
                s += 2.0  # Prefer entries with known fixes
            return s

        candidates.sort(key=score, reverse=True)
        return candidates[:limit]

    def get_resolved_errors(self) -> list[ErrorEntry]:
        """Get all errors that have been successfully resolved."""
        return [
            e for e in self._entries.values()
            if e.resolution == 'fixed' and e.fix_successful
        ]

    def get_recurring_errors(self, min_count: int = 3) -> list[ErrorEntry]:
        """Get errors that keep recurring (potential systemic issues)."""
        return [
            e for e in self._entries.values()
            if e.occurrence_count >= min_count
        ]

    def mark_resolved(
        self, error_id: str, fix_applied: str, successful: bool = True
    ) -> bool:
        """Mark an error as resolved with the fix that was applied."""
        entry = self._entries.get(error_id)
        if entry is None:
            return False

        entry.resolution = 'fixed' if successful else 'workaround'
        entry.fix_applied = fix_applied
        entry.fix_successful = successful
        return True

    def should_avoid_approach(self, error_type: str, approach: str) -> bool:
        """Check if a specific approach has failed before for this error type.

        This is where MEMORY CHANGES DECISIONS — if we've seen this error
        type before and a specific approach failed, we avoid it.
        """
        if error_type not in self._by_type:
            return False

        for eid in self._by_type[error_type]:
            entry = self._entries.get(eid)
            if (
                entry
                and entry.fix_applied == approach
                and not entry.fix_successful
            ):
                logger.info(
                    f'[ErrorMemory] Avoiding approach "{approach}" — '
                    f'failed for {error_type} before (count={entry.occurrence_count})'
                )
                return True

        return False

    @property
    def total_errors(self) -> int:
        return len(self._entries)

    @property
    def total_resolved(self) -> int:
        return sum(1 for e in self._entries.values() if e.fix_successful)

    def stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            'total_errors': self.total_errors,
            'total_resolved': self.total_resolved,
            'error_types': {
                t: len(ids) for t, ids in self._by_type.items()
            },
            'top_recurring': [
                {'type': e.error_type, 'count': e.occurrence_count}
                for e in sorted(
                    self._entries.values(),
                    key=lambda x: x.occurrence_count,
                    reverse=True,
                )[:5]
            ],
        }

    def _evict_oldest(self) -> None:
        """Remove the oldest entry to make room."""
        if not self._entries:
            return
        oldest_id = min(self._entries, key=lambda k: self._entries[k].timestamp)
        del self._entries[oldest_id]
