"""Tool loop detection — detect when an agent is stuck repeating the same actions.

Ported from OpenClaw's tool-loop detection using Jaccard similarity on
recent tool calls. When the agent keeps calling the same tools with similar
arguments, it's likely stuck in a loop and needs intervention.

Per OPERATING_RULES.md RULE 5: No unbounded resources — every loop has max iterations.
"""

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger

# Detection configuration
DEFAULT_WINDOW_SIZE = 10  # Number of recent calls to consider
DEFAULT_SIMILARITY_THRESHOLD = 0.8  # Jaccard similarity threshold
DEFAULT_MIN_CALLS_FOR_DETECTION = 4  # Minimum calls before detection kicks in
MAX_HISTORY_SIZE = 100  # Maximum tool call history to keep


@dataclass
class ToolCall:
    """Record of a single tool invocation."""

    tool_name: str
    arguments_hash: str
    timestamp: float = 0.0
    call_id: str = ''

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class LoopDetectionResult:
    """Result of loop detection analysis."""

    is_loop: bool = False
    similarity_score: float = 0.0
    repeated_tools: list[str] = field(default_factory=list)
    window_size: int = 0
    suggestion: str = ''


@dataclass
class ToolLoopConfig:
    """Configuration for tool loop detection."""

    window_size: int = DEFAULT_WINDOW_SIZE
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    min_calls: int = DEFAULT_MIN_CALLS_FOR_DETECTION
    enabled: bool = True


class ToolLoopDetector:
    """Detects when an agent is stuck in a tool call loop.

    Uses Jaccard similarity on sliding windows of recent tool calls.
    If the first half and second half of the window have high similarity,
    the agent is likely repeating itself.
    """

    def __init__(self, config: ToolLoopConfig | None = None):
        self._config = config or ToolLoopConfig()
        self._history: deque[ToolCall] = deque(maxlen=MAX_HISTORY_SIZE)
        self._loop_count = 0
        self._total_checks = 0

    def record(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> LoopDetectionResult:
        """Record a tool call and check for loops.

        Args:
            tool_name: Name of the tool being called
            arguments: Tool call arguments (hashed for comparison)

        Returns:
            LoopDetectionResult with analysis
        """
        # Hash the arguments for comparison
        args_hash = _hash_arguments(arguments) if arguments else ''

        call = ToolCall(
            tool_name=tool_name,
            arguments_hash=args_hash,
        )
        self._history.append(call)

        if not self._config.enabled:
            return LoopDetectionResult()

        return self.check()

    def check(self) -> LoopDetectionResult:
        """Check the current history for loops."""
        self._total_checks += 1

        if len(self._history) < self._config.min_calls:
            return LoopDetectionResult(window_size=len(self._history))

        window_size = min(self._config.window_size, len(self._history))
        recent = list(self._history)[-window_size:]

        # Split window into two halves
        mid = window_size // 2
        first_half = recent[:mid]
        second_half = recent[mid:]

        # Compute Jaccard similarity
        similarity = _jaccard_similarity(first_half, second_half)

        # Find repeated tools
        first_tools = {c.tool_name for c in first_half}
        second_tools = {c.tool_name for c in second_half}
        repeated = sorted(first_tools & second_tools)

        is_loop = similarity >= self._config.similarity_threshold
        if is_loop:
            self._loop_count += 1

        suggestion = ''
        if is_loop:
            suggestion = (
                f'Agent appears stuck in a loop (similarity={similarity:.2f}). '
                f'Repeated tools: {", ".join(repeated)}. '
                'Consider: changing approach, asking for help, or trying a different tool.'
            )
            logger.warning(
                f'Tool loop detected: similarity={similarity:.2f}, '
                f'repeated={repeated}, window={window_size}'
            )

        return LoopDetectionResult(
            is_loop=is_loop,
            similarity_score=similarity,
            repeated_tools=repeated,
            window_size=window_size,
            suggestion=suggestion,
        )

    def reset(self) -> None:
        """Clear the tool call history."""
        self._history.clear()

    @property
    def call_count(self) -> int:
        return len(self._history)

    @property
    def loop_count(self) -> int:
        return self._loop_count

    def stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        # Count tool frequencies
        tool_freq: dict[str, int] = {}
        for call in self._history:
            tool_freq[call.tool_name] = tool_freq.get(call.tool_name, 0) + 1

        return {
            'total_calls': len(self._history),
            'total_checks': self._total_checks,
            'loop_detections': self._loop_count,
            'window_size': self._config.window_size,
            'threshold': self._config.similarity_threshold,
            'tool_frequencies': tool_freq,
        }


def _hash_arguments(arguments: dict[str, Any]) -> str:
    """Create a deterministic hash of tool arguments."""
    # Sort keys for deterministic ordering
    parts: list[str] = []
    for key in sorted(arguments.keys()):
        value = arguments[key]
        parts.append(f'{key}={value!r}')
    combined = '|'.join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _jaccard_similarity(
    set_a: list[ToolCall],
    set_b: list[ToolCall],
) -> float:
    """Compute Jaccard similarity between two sets of tool calls.

    Uses (tool_name, arguments_hash) as the comparison key.
    """
    keys_a = {(c.tool_name, c.arguments_hash) for c in set_a}
    keys_b = {(c.tool_name, c.arguments_hash) for c in set_b}

    if not keys_a and not keys_b:
        return 0.0

    intersection = keys_a & keys_b
    union = keys_a | keys_b

    if not union:
        return 0.0

    return len(intersection) / len(union)
