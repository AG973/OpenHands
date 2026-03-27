"""Retry Policy — governs retry behavior for failed operations.

Defines when, how many times, and with what strategy to retry
failed operations. Integrates with error memory and fix memory
to make informed retry decisions.

Patterns extracted from:
    - GPT-Pilot: Iterative fix-test-retry cycles
    - OpenHands: StuckDetector retry limits
    - Cline: Task-level retry with different approaches
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class RetryStrategy(Enum):
    """Strategy for retrying a failed operation."""

    SAME_APPROACH = 'same_approach'  # Retry with the same approach
    DIFFERENT_APPROACH = 'different_approach'  # Try a different approach
    SIMPLIFIED = 'simplified'  # Simplify the task and retry
    ESCALATE = 'escalate'  # Give up and escalate
    BACKOFF = 'backoff'  # Wait and retry


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    max_total_retries: int = 5
    backoff_base_s: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff_s: float = 60.0
    same_approach_limit: int = 1  # Max times to retry same approach
    allow_simplified: bool = True
    allow_escalation: bool = True


@dataclass
class RetryRecord:
    """Record of a retry attempt."""

    attempt: int
    strategy: RetryStrategy
    error: str
    timestamp: float = field(default_factory=time.time)
    duration_s: float = 0.0
    success: bool = False


@dataclass
class RetryDecision:
    """Decision from the retry policy."""

    should_retry: bool = False
    strategy: RetryStrategy = RetryStrategy.SAME_APPROACH
    wait_seconds: float = 0.0
    reason: str = ''
    attempt_number: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'should_retry': self.should_retry,
            'strategy': self.strategy.value,
            'wait_seconds': self.wait_seconds,
            'reason': self.reason,
            'attempt_number': self.attempt_number,
        }


class RetryPolicy:
    """Governs retry behavior for failed operations.

    Usage:
        policy = RetryPolicy()
        decision = policy.should_retry(
            error='ImportError: No module named X',
            attempt=1,
            error_type='import_error',
        )
        if decision.should_retry:
            time.sleep(decision.wait_seconds)
            # Retry with decision.strategy
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        self._config = config or RetryConfig()
        self._retry_history: dict[str, list[RetryRecord]] = {}
        self._approach_attempts: dict[str, dict[str, int]] = {}

    def should_retry(
        self,
        task_id: str = '',
        error: str = '',
        error_type: str = '',
        attempt: int = 0,
        current_approach: str = '',
    ) -> RetryDecision:
        """Determine whether and how to retry a failed operation.

        Args:
            task_id: Task identifier for tracking
            error: Error message
            error_type: Classified error type
            attempt: Current attempt number
            current_approach: The approach that just failed

        Returns:
            RetryDecision with strategy and wait time
        """
        # Check absolute limits
        if attempt >= self._config.max_total_retries:
            return RetryDecision(
                should_retry=False,
                strategy=RetryStrategy.ESCALATE,
                reason=f'Max total retries ({self._config.max_total_retries}) exceeded',
                attempt_number=attempt,
            )

        if attempt >= self._config.max_retries:
            # Past normal retry limit but under total — try different approach
            if self._config.allow_simplified:
                return RetryDecision(
                    should_retry=True,
                    strategy=RetryStrategy.SIMPLIFIED,
                    wait_seconds=self._calculate_backoff(attempt),
                    reason='Normal retries exhausted — trying simplified approach',
                    attempt_number=attempt + 1,
                )
            return RetryDecision(
                should_retry=False,
                strategy=RetryStrategy.ESCALATE,
                reason=f'Max retries ({self._config.max_retries}) exceeded',
                attempt_number=attempt,
            )

        # Check if same approach has been tried too many times
        approach_count = self._get_approach_count(task_id, current_approach)
        if approach_count >= self._config.same_approach_limit:
            # Switch to different approach
            return RetryDecision(
                should_retry=True,
                strategy=RetryStrategy.DIFFERENT_APPROACH,
                wait_seconds=self._calculate_backoff(attempt),
                reason=f'Approach "{current_approach}" tried {approach_count} times — switching',
                attempt_number=attempt + 1,
            )

        # Determine strategy based on error type
        strategy = self._select_strategy(error_type, attempt)
        wait = self._calculate_backoff(attempt)

        # Record attempt
        self._record_attempt(task_id, current_approach, error)

        return RetryDecision(
            should_retry=True,
            strategy=strategy,
            wait_seconds=wait,
            reason=f'Retry {attempt + 1}/{self._config.max_retries}: {error_type or "unknown"}',
            attempt_number=attempt + 1,
        )

    def _select_strategy(self, error_type: str, attempt: int) -> RetryStrategy:
        """Select retry strategy based on error type and attempt number."""
        # First attempt: try same approach (might be transient)
        if attempt == 0:
            return RetryStrategy.SAME_APPROACH

        # Known transient errors: retry with backoff
        transient_types = {'connection_error', 'timeout', 'rate_limit'}
        if error_type in transient_types:
            return RetryStrategy.BACKOFF

        # Second+ attempt: try different approach
        if attempt >= 1:
            return RetryStrategy.DIFFERENT_APPROACH

        return RetryStrategy.SAME_APPROACH

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff wait time."""
        wait = self._config.backoff_base_s * (self._config.backoff_multiplier ** attempt)
        return min(wait, self._config.max_backoff_s)

    def _get_approach_count(self, task_id: str, approach: str) -> int:
        """Get how many times an approach has been tried for a task."""
        if not approach or task_id not in self._approach_attempts:
            return 0
        return self._approach_attempts.get(task_id, {}).get(approach, 0)

    def _record_attempt(self, task_id: str, approach: str, error: str) -> None:
        """Record a retry attempt."""
        if task_id:
            if task_id not in self._approach_attempts:
                self._approach_attempts[task_id] = {}
            if approach:
                self._approach_attempts[task_id][approach] = (
                    self._approach_attempts[task_id].get(approach, 0) + 1
                )

            if task_id not in self._retry_history:
                self._retry_history[task_id] = []
            self._retry_history[task_id].append(
                RetryRecord(
                    attempt=len(self._retry_history[task_id]) + 1,
                    strategy=RetryStrategy.SAME_APPROACH,
                    error=error[:200],
                )
            )

    def get_history(self, task_id: str) -> list[RetryRecord]:
        """Get retry history for a task."""
        return self._retry_history.get(task_id, [])

    def reset(self, task_id: str) -> None:
        """Reset retry state for a task."""
        self._retry_history.pop(task_id, None)
        self._approach_attempts.pop(task_id, None)

    def stats(self) -> dict[str, Any]:
        """Get policy statistics."""
        total_retries = sum(len(h) for h in self._retry_history.values())
        return {
            'tasks_tracked': len(self._retry_history),
            'total_retries': total_retries,
            'config': {
                'max_retries': self._config.max_retries,
                'max_total_retries': self._config.max_total_retries,
            },
        }
