"""Decision Memory — records and retrieves past decisions and their outcomes.

Every significant decision made during task execution is recorded here:
which approach was chosen, why, and whether it succeeded. Future tasks
consult decision memory to avoid repeating failed approaches and to
prefer strategies that worked before.

Memory MUST change decisions — decision memory is the primary driver
of approach selection in the planning and retry phases.

Patterns extracted from:
    - LangGraph: Checkpoint-based state persistence
    - GPT-Pilot: Decision tracking across development cycles
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class DecisionType(Enum):
    """Types of decisions tracked."""

    APPROACH = 'approach'  # Which approach to take for a task
    TOOL_CHOICE = 'tool_choice'  # Which tool to use
    FILE_SELECTION = 'file_selection'  # Which files to modify
    FIX_STRATEGY = 'fix_strategy'  # How to fix an error
    ARCHITECTURE = 'architecture'  # Architectural decisions
    SKIP = 'skip'  # Decision to skip something
    ESCALATE = 'escalate'  # Decision to escalate


class DecisionOutcome(Enum):
    """Outcome of a decision."""

    SUCCESS = 'success'
    FAILURE = 'failure'
    PARTIAL = 'partial'
    UNKNOWN = 'unknown'


@dataclass
class DecisionEntry:
    """A single decision record."""

    decision_id: str = ''
    decision_type: DecisionType = DecisionType.APPROACH
    description: str = ''
    alternatives_considered: list[str] = field(default_factory=list)
    chosen_alternative: str = ''
    reasoning: str = ''
    outcome: DecisionOutcome = DecisionOutcome.UNKNOWN
    outcome_details: str = ''
    task_id: str = ''
    task_type: str = ''
    context_hash: str = ''  # Hash of the context when decision was made
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        raw = f'{self.decision_type.value}:{self.description[:50]}:{self.chosen_alternative}'
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            'decision_id': self.decision_id,
            'type': self.decision_type.value,
            'description': self.description[:100],
            'chosen': self.chosen_alternative,
            'outcome': self.outcome.value,
        }


class DecisionMemory:
    """Records and retrieves past decisions to influence future choices.

    Usage:
        mem = DecisionMemory()

        # Record a decision
        did = mem.record(DecisionEntry(
            decision_type=DecisionType.APPROACH,
            description='How to fix import error',
            alternatives_considered=['install package', 'fix import path', 'add __init__.py'],
            chosen_alternative='install package',
            reasoning='Package not in requirements.txt',
        ))

        # Record outcome
        mem.record_outcome(did, DecisionOutcome.SUCCESS, 'Package installed, tests pass')

        # Later, when making a similar decision:
        past = mem.get_similar_decisions(DecisionType.APPROACH, 'import error fix')
        if past:
            # Prefer approaches that worked before
            best = mem.get_best_approach(DecisionType.APPROACH, 'import error')
    """

    def __init__(self, max_entries: int = 2000) -> None:
        self._entries: dict[str, DecisionEntry] = {}
        self._max_entries = max_entries
        self._by_type: dict[DecisionType, list[str]] = {}
        self._by_task: dict[str, list[str]] = {}

    def record(self, entry: DecisionEntry) -> str:
        """Record a decision."""
        if len(self._entries) >= self._max_entries:
            self._evict_oldest()

        fp = entry.fingerprint
        entry.decision_id = fp
        self._entries[fp] = entry

        # Index by type
        if entry.decision_type not in self._by_type:
            self._by_type[entry.decision_type] = []
        self._by_type[entry.decision_type].append(fp)

        # Index by task
        if entry.task_id:
            if entry.task_id not in self._by_task:
                self._by_task[entry.task_id] = []
            self._by_task[entry.task_id].append(fp)

        logger.info(
            f'[DecisionMemory] Recorded: {entry.decision_type.value} — '
            f'{entry.description[:50]}'
        )
        return fp

    def record_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        details: str = '',
    ) -> bool:
        """Record the outcome of a decision."""
        entry = self._entries.get(decision_id)
        if entry is None:
            return False

        entry.outcome = outcome
        entry.outcome_details = details
        logger.info(
            f'[DecisionMemory] Outcome: {decision_id} = {outcome.value}'
        )
        return True

    def get_similar_decisions(
        self,
        decision_type: DecisionType,
        description: str = '',
        limit: int = 10,
    ) -> list[DecisionEntry]:
        """Find similar past decisions.

        Used to learn from past experience when making new decisions.
        """
        candidates: list[DecisionEntry] = []

        # Filter by type
        if decision_type in self._by_type:
            for did in self._by_type[decision_type]:
                entry = self._entries.get(did)
                if entry:
                    candidates.append(entry)

        # Filter by description similarity (simple keyword match)
        if description:
            keywords = set(description.lower().split())
            scored: list[tuple[float, DecisionEntry]] = []
            for entry in candidates:
                entry_words = set(entry.description.lower().split())
                overlap = len(keywords & entry_words)
                if overlap > 0:
                    scored.append((overlap, entry))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [e for _, e in scored]

        return candidates[:limit]

    def get_best_approach(
        self,
        decision_type: DecisionType,
        context_description: str = '',
    ) -> str | None:
        """Get the best approach based on past decision outcomes.

        This is where MEMORY CHANGES DECISIONS — the system prefers
        approaches that succeeded before and avoids those that failed.
        """
        similar = self.get_similar_decisions(decision_type, context_description)

        # Score alternatives by success rate
        approach_scores: dict[str, dict[str, int]] = {}
        for entry in similar:
            alt = entry.chosen_alternative
            if alt not in approach_scores:
                approach_scores[alt] = {'success': 0, 'failure': 0, 'total': 0}

            approach_scores[alt]['total'] += 1
            if entry.outcome == DecisionOutcome.SUCCESS:
                approach_scores[alt]['success'] += 1
            elif entry.outcome == DecisionOutcome.FAILURE:
                approach_scores[alt]['failure'] += 1

        if not approach_scores:
            return None

        # Pick approach with highest success rate (min 1 success)
        best_approach = None
        best_score = -1.0

        for approach, counts in approach_scores.items():
            if counts['total'] == 0:
                continue
            score = counts['success'] / counts['total']
            if score > best_score and counts['success'] > 0:
                best_score = score
                best_approach = approach

        if best_approach:
            logger.info(
                f'[DecisionMemory] Best approach: "{best_approach}" '
                f'(score={best_score:.2f})'
            )

        return best_approach

    def should_avoid_alternative(
        self,
        decision_type: DecisionType,
        alternative: str,
        threshold: float = 0.3,
    ) -> bool:
        """Check if an alternative should be avoided based on past failures.

        Returns True if the alternative has a failure rate above threshold.
        """
        if decision_type not in self._by_type:
            return False

        success = 0
        failure = 0

        for did in self._by_type[decision_type]:
            entry = self._entries.get(did)
            if entry and entry.chosen_alternative == alternative:
                if entry.outcome == DecisionOutcome.SUCCESS:
                    success += 1
                elif entry.outcome == DecisionOutcome.FAILURE:
                    failure += 1

        total = success + failure
        if total < 2:
            return False  # Not enough data

        failure_rate = failure / total
        if failure_rate > threshold:
            logger.info(
                f'[DecisionMemory] Avoiding "{alternative}" — '
                f'failure rate {failure_rate:.0%} > {threshold:.0%}'
            )
            return True

        return False

    def get_task_decisions(self, task_id: str) -> list[DecisionEntry]:
        """Get all decisions made for a specific task."""
        if task_id not in self._by_task:
            return []
        return [
            self._entries[did]
            for did in self._by_task[task_id]
            if did in self._entries
        ]

    def stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        outcomes: dict[str, int] = {}
        for entry in self._entries.values():
            ov = entry.outcome.value
            outcomes[ov] = outcomes.get(ov, 0) + 1

        return {
            'total_decisions': len(self._entries),
            'by_type': {
                t.value: len(ids) for t, ids in self._by_type.items()
            },
            'outcomes': outcomes,
            'tasks_tracked': len(self._by_task),
        }

    def _evict_oldest(self) -> None:
        """Remove the oldest entry."""
        if not self._entries:
            return
        oldest_id = min(self._entries, key=lambda k: self._entries[k].timestamp)
        del self._entries[oldest_id]
