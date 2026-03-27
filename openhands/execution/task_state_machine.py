"""Task State Machine — deterministic phase transitions for task execution.

Defines the ONLY execution path a task can follow:
INTAKE -> CONTEXT_BUILD -> REPO_ANALYSIS -> PLAN -> EXECUTE -> TEST ->
(FAILURE_ANALYSIS -> RETRY_OR_FIX -> back to EXECUTE)* ->
REVIEW -> ARTIFACT_GENERATION -> COMPLETE

No shortcuts. No skipping phases. Every transition is logged and validated.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class TaskPhase(Enum):
    """Ordered phases of task execution."""

    INTAKE = 'intake'
    CONTEXT_BUILD = 'context_build'
    REPO_ANALYSIS = 'repo_analysis'
    PLAN = 'plan'
    EXECUTE = 'execute'
    TEST = 'test'
    FAILURE_ANALYSIS = 'failure_analysis'
    RETRY_OR_FIX = 'retry_or_fix'
    REVIEW = 'review'
    ARTIFACT_GENERATION = 'artifact_generation'
    COMPLETE = 'complete'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


# Valid phase transitions — enforced strictly
_VALID_TRANSITIONS: dict[TaskPhase, list[TaskPhase]] = {
    TaskPhase.INTAKE: [TaskPhase.CONTEXT_BUILD, TaskPhase.FAILED, TaskPhase.CANCELLED],
    TaskPhase.CONTEXT_BUILD: [TaskPhase.REPO_ANALYSIS, TaskPhase.FAILED],
    TaskPhase.REPO_ANALYSIS: [TaskPhase.PLAN, TaskPhase.FAILED],
    TaskPhase.PLAN: [TaskPhase.EXECUTE, TaskPhase.FAILED],
    TaskPhase.EXECUTE: [
        TaskPhase.TEST,
        TaskPhase.FAILURE_ANALYSIS,
        TaskPhase.FAILED,
    ],
    TaskPhase.TEST: [
        TaskPhase.REVIEW,
        TaskPhase.FAILURE_ANALYSIS,
        TaskPhase.FAILED,
    ],
    TaskPhase.FAILURE_ANALYSIS: [TaskPhase.RETRY_OR_FIX, TaskPhase.FAILED],
    TaskPhase.RETRY_OR_FIX: [
        TaskPhase.EXECUTE,
        TaskPhase.PLAN,
        TaskPhase.FAILED,
    ],
    TaskPhase.REVIEW: [
        TaskPhase.ARTIFACT_GENERATION,
        TaskPhase.EXECUTE,  # review can send back to execution
        TaskPhase.FAILED,
    ],
    TaskPhase.ARTIFACT_GENERATION: [TaskPhase.COMPLETE, TaskPhase.FAILED],
    TaskPhase.COMPLETE: [],  # terminal
    TaskPhase.FAILED: [],  # terminal
    TaskPhase.CANCELLED: [],  # terminal
}


class TransitionError(Exception):
    """Raised when an invalid phase transition is attempted."""

    pass


class PhaseRecord:
    """Record of a single phase execution."""

    __slots__ = (
        'phase',
        'entered_at',
        'exited_at',
        'duration_s',
        'success',
        'error',
        'metadata',
    )

    def __init__(self, phase: TaskPhase) -> None:
        self.phase = phase
        self.entered_at: float = time.time()
        self.exited_at: float = 0.0
        self.duration_s: float = 0.0
        self.success: bool = False
        self.error: str = ''
        self.metadata: dict[str, Any] = {}

    def close(self, success: bool, error: str = '') -> None:
        self.exited_at = time.time()
        self.duration_s = self.exited_at - self.entered_at
        self.success = success
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            'phase': self.phase.value,
            'entered_at': self.entered_at,
            'exited_at': self.exited_at,
            'duration_s': self.duration_s,
            'success': self.success,
            'error': self.error,
            'metadata': self.metadata,
        }


class TaskStateMachine:
    """Deterministic state machine for task execution phases.

    Enforces valid transitions, tracks phase history, and provides
    observability into task lifecycle.
    """

    def __init__(self, task_id: str) -> None:
        self._task_id = task_id
        self._current_phase = TaskPhase.INTAKE
        self._history: list[PhaseRecord] = []
        self._current_record = PhaseRecord(TaskPhase.INTAKE)
        self._retry_count = 0
        self._max_retries = 3
        self._created_at = time.time()

        logger.info(
            f'[TaskSM {task_id}] Initialized at phase {self._current_phase.value}'
        )

    @property
    def current_phase(self) -> TaskPhase:
        return self._current_phase

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def is_terminal(self) -> bool:
        return self._current_phase in (
            TaskPhase.COMPLETE,
            TaskPhase.FAILED,
            TaskPhase.CANCELLED,
        )

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @property
    def history(self) -> list[PhaseRecord]:
        return list(self._history)

    @property
    def duration_s(self) -> float:
        return time.time() - self._created_at

    def transition_to(
        self,
        target: TaskPhase,
        success: bool = True,
        error: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Transition to a new phase. Validates the transition is allowed.

        Raises:
            TransitionError: If the transition is not valid
        """
        if self.is_terminal:
            raise TransitionError(
                f'[TaskSM {self._task_id}] Cannot transition from terminal '
                f'phase {self._current_phase.value}'
            )

        valid_targets = _VALID_TRANSITIONS.get(self._current_phase, [])
        if target not in valid_targets:
            raise TransitionError(
                f'[TaskSM {self._task_id}] Invalid transition: '
                f'{self._current_phase.value} -> {target.value}. '
                f'Valid targets: {[t.value for t in valid_targets]}'
            )

        # Close current phase record
        self._current_record.close(success=success, error=error)
        if metadata:
            self._current_record.metadata.update(metadata)
        self._history.append(self._current_record)

        # Track retries
        if target == TaskPhase.RETRY_OR_FIX:
            self._retry_count += 1

        old_phase = self._current_phase
        self._current_phase = target
        self._current_record = PhaseRecord(target)

        logger.info(
            f'[TaskSM {self._task_id}] {old_phase.value} -> {target.value} '
            f'(success={success}, retries={self._retry_count})'
        )

    def can_retry(self) -> bool:
        """Check if the task can retry (under max retries)."""
        return self._retry_count < self._max_retries

    def set_max_retries(self, max_retries: int) -> None:
        self._max_retries = max_retries

    def get_phase_durations(self) -> dict[str, float]:
        """Get duration of each phase that has been executed."""
        durations: dict[str, float] = {}
        for record in self._history:
            phase_key = record.phase.value
            if phase_key in durations:
                durations[phase_key] += record.duration_s
            else:
                durations[phase_key] = record.duration_s
        return durations

    def get_failed_phases(self) -> list[PhaseRecord]:
        """Get all phases that failed."""
        return [r for r in self._history if not r.success]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the state machine for persistence/observability."""
        return {
            'task_id': self._task_id,
            'current_phase': self._current_phase.value,
            'is_terminal': self.is_terminal,
            'retry_count': self._retry_count,
            'max_retries': self._max_retries,
            'duration_s': self.duration_s,
            'history': [r.to_dict() for r in self._history],
            'phase_durations': self.get_phase_durations(),
        }
