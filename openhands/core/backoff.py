"""Backoff policy engine — configurable exponential backoff with jitter.

Ported from OpenClaw's infra/backoff.ts. Provides a shared backoff policy
used across all retry points (LLM calls, HTTP requests, sub-agent spawning, etc.).

Per OPERATING_RULES.md RULE 5: No missing error handling — classify transient vs permanent errors.
"""

import asyncio
import math
import random
import time
from dataclasses import dataclass


@dataclass
class BackoffPolicy:
    """Configuration for exponential backoff behavior.

    Attributes:
        initial_ms: Base delay for the first retry attempt
        max_ms: Maximum delay cap
        factor: Exponential growth factor (delay = initial * factor^(attempt-1))
        jitter: Random jitter factor (0.0 = no jitter, 1.0 = up to 100% extra)
    """

    initial_ms: float = 1000.0
    max_ms: float = 60000.0
    factor: float = 2.0
    jitter: float = 0.25


# Pre-configured policies for common use cases
LLM_RETRY_POLICY = BackoffPolicy(
    initial_ms=2000.0,
    max_ms=60000.0,
    factor=2.0,
    jitter=0.3,
)

OLLAMA_RETRY_POLICY = BackoffPolicy(
    initial_ms=1000.0,
    max_ms=30000.0,
    factor=2.0,
    jitter=0.2,
)

NETWORK_RETRY_POLICY = BackoffPolicy(
    initial_ms=500.0,
    max_ms=30000.0,
    factor=2.0,
    jitter=0.5,
)

HEARTBEAT_RETRY_POLICY = BackoffPolicy(
    initial_ms=5000.0,
    max_ms=120000.0,
    factor=1.5,
    jitter=0.2,
)

SUBAGENT_RETRY_POLICY = BackoffPolicy(
    initial_ms=3000.0,
    max_ms=60000.0,
    factor=2.0,
    jitter=0.3,
)


def compute_backoff(policy: BackoffPolicy, attempt: int) -> float:
    """Compute the backoff delay for a given attempt number.

    Args:
        policy: Backoff configuration
        attempt: Attempt number (1-based, first retry is attempt 1)

    Returns:
        Delay in milliseconds, capped at policy.max_ms
    """
    base = policy.initial_ms * (policy.factor ** max(attempt - 1, 0))
    jitter_amount = base * policy.jitter * random.random()
    return min(policy.max_ms, round(base + jitter_amount))


def compute_backoff_seconds(policy: BackoffPolicy, attempt: int) -> float:
    """Compute backoff delay in seconds (convenience wrapper)."""
    return compute_backoff(policy, attempt) / 1000.0


def sleep_with_backoff(policy: BackoffPolicy, attempt: int) -> None:
    """Synchronous sleep with computed backoff delay."""
    delay_s = compute_backoff_seconds(policy, attempt)
    time.sleep(delay_s)


async def async_sleep_with_backoff(
    policy: BackoffPolicy,
    attempt: int,
    abort_event: asyncio.Event | None = None,
) -> bool:
    """Async sleep with computed backoff delay.

    Args:
        policy: Backoff configuration
        attempt: Attempt number (1-based)
        abort_event: Optional event that, when set, cancels the sleep early

    Returns:
        True if sleep completed normally, False if aborted
    """
    delay_s = compute_backoff_seconds(policy, attempt)
    if delay_s <= 0:
        return True

    if abort_event is not None:
        try:
            await asyncio.wait_for(abort_event.wait(), timeout=delay_s)
            # Event was set — we were aborted
            return False
        except asyncio.TimeoutError:
            # Timeout expired normally — sleep completed
            return True
    else:
        await asyncio.sleep(delay_s)
        return True


class ConsecutiveErrorTracker:
    """Track consecutive errors and determine when to abort.

    Used to detect persistent failures and escalate rather than
    retrying indefinitely. Ported from OpenClaw's error tracking pattern.
    """

    def __init__(self, max_consecutive: int = 5, window_ms: int = 300000):
        """Initialize the consecutive error tracker.

        Args:
            max_consecutive: Max consecutive errors before abort recommendation
            window_ms: Time window for tracking (default: 5 minutes)
        """
        self._max_consecutive = max_consecutive
        self._window_ms = window_ms
        self._errors: list[float] = []  # timestamps in ms
        self._consecutive_count = 0

    def record_error(self) -> None:
        """Record an error occurrence."""
        now = time.time() * 1000
        self._errors.append(now)
        self._consecutive_count += 1
        # Prune old errors outside window
        cutoff = now - self._window_ms
        self._errors = [t for t in self._errors if t > cutoff]

    def record_success(self) -> None:
        """Record a success — resets consecutive counter."""
        self._consecutive_count = 0

    @property
    def consecutive_count(self) -> int:
        return self._consecutive_count

    @property
    def errors_in_window(self) -> int:
        now = time.time() * 1000
        cutoff = now - self._window_ms
        return sum(1 for t in self._errors if t > cutoff)

    @property
    def should_abort(self) -> bool:
        """Returns True if we've exceeded the max consecutive error threshold."""
        return self._consecutive_count >= self._max_consecutive

    def reset(self) -> None:
        """Reset all counters."""
        self._errors.clear()
        self._consecutive_count = 0
