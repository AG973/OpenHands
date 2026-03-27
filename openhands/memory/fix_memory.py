"""Fix Memory — stores successful fixes and repair strategies.

When an error is fixed, the fix pattern is stored here. When similar
errors occur in the future, fix memory is consulted FIRST to replay
known-good solutions.

Memory MUST change decisions — fix memory drives the retry strategy.

Patterns extracted from:
    - GPT-Pilot: Iterative fix-test cycles with memory
    - Cline: Task-level fix tracking
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class FixEntry:
    """A single fix record."""

    fix_id: str = ''
    error_type: str = ''
    error_pattern: str = ''  # Regex or substring pattern that triggers this fix
    fix_description: str = ''
    fix_steps: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    last_applied: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def fingerprint(self) -> str:
        raw = f'{self.error_type}:{self.error_pattern}:{self.fix_description[:50]}'
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            'fix_id': self.fix_id,
            'error_type': self.error_type,
            'fix_description': self.fix_description,
            'success_rate': self.success_rate,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
        }


class FixMemory:
    """Stores and retrieves fix strategies based on error patterns.

    Usage:
        mem = FixMemory()
        mem.record_fix(FixEntry(
            error_type='import_error',
            error_pattern='ModuleNotFoundError',
            fix_description='Install missing package',
            fix_steps=['pip install X'],
        ))
        fixes = mem.get_fixes_for('import_error', 'ModuleNotFoundError: No module named X')
        if fixes:
            # Apply the best fix
            best = fixes[0]
    """

    def __init__(self, max_entries: int = 500) -> None:
        self._entries: dict[str, FixEntry] = {}
        self._max_entries = max_entries
        self._by_error_type: dict[str, list[str]] = {}

    def record_fix(self, entry: FixEntry) -> str:
        """Record a fix in memory.

        Returns:
            The fix_id
        """
        fp = entry.fingerprint

        # Update existing or create new
        if fp in self._entries:
            existing = self._entries[fp]
            existing.success_count += entry.success_count
            existing.failure_count += entry.failure_count
            existing.last_applied = time.time()
            return existing.fix_id

        if len(self._entries) >= self._max_entries:
            self._evict_worst()

        entry.fix_id = fp
        self._entries[fp] = entry

        if entry.error_type not in self._by_error_type:
            self._by_error_type[entry.error_type] = []
        self._by_error_type[entry.error_type].append(fp)

        logger.info(
            f'[FixMemory] Recorded fix: {entry.fix_description[:50]} '
            f'for {entry.error_type}'
        )
        return fp

    def record_success(self, fix_id: str) -> None:
        """Record a successful application of a fix."""
        entry = self._entries.get(fix_id)
        if entry:
            entry.success_count += 1
            entry.last_applied = time.time()

    def record_failure(self, fix_id: str) -> None:
        """Record a failed application of a fix."""
        entry = self._entries.get(fix_id)
        if entry:
            entry.failure_count += 1
            entry.last_applied = time.time()

    def get_fixes_for(
        self,
        error_type: str,
        error_message: str = '',
        limit: int = 5,
    ) -> list[FixEntry]:
        """Get applicable fixes for an error, sorted by success rate.

        This is where MEMORY CHANGES DECISIONS — the ordering of fixes
        is driven by past success/failure rates.
        """
        candidates: list[FixEntry] = []

        # Search by error type
        if error_type in self._by_error_type:
            for fid in self._by_error_type[error_type]:
                entry = self._entries.get(fid)
                if entry:
                    candidates.append(entry)

        # Filter by error pattern match
        if error_message:
            msg_lower = error_message.lower()
            filtered: list[FixEntry] = []
            for entry in candidates:
                if entry.error_pattern and entry.error_pattern.lower() in msg_lower:
                    filtered.append(entry)
            # If pattern matching narrows results, use those; otherwise keep all
            if filtered:
                candidates = filtered

        # Score: success_rate * recency bonus
        def score(e: FixEntry) -> float:
            s = e.success_rate * 10
            age_hours = (time.time() - e.last_applied) / 3600 if e.last_applied else 1000
            s += max(0, 10 - age_hours) * 0.1  # Recent fixes get a small bonus
            return s

        candidates.sort(key=score, reverse=True)
        return candidates[:limit]

    def get_best_fix(
        self, error_type: str, error_message: str = ''
    ) -> FixEntry | None:
        """Get the single best fix for an error."""
        fixes = self.get_fixes_for(error_type, error_message, limit=1)
        return fixes[0] if fixes else None

    def get_all_fixes(self) -> list[FixEntry]:
        """Get all recorded fixes."""
        return list(self._entries.values())

    def stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        total = len(self._entries)
        high_success = sum(1 for e in self._entries.values() if e.success_rate > 0.7)
        return {
            'total_fixes': total,
            'high_success_fixes': high_success,
            'by_error_type': {
                t: len(ids) for t, ids in self._by_error_type.items()
            },
        }

    def _evict_worst(self) -> None:
        """Remove the fix with lowest success rate."""
        if not self._entries:
            return
        worst_id = min(
            self._entries,
            key=lambda k: self._entries[k].success_rate,
        )
        del self._entries[worst_id]
