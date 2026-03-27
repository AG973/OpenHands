"""Engineering OS — top-level entry point that wires the execution engine.

This is the single entry point for running tasks through the CODEIT OS.
It creates a TaskEngine, wires integration setters to subsystems,
and exposes run_task() as the canonical execution path.

Usage:
    eos = EngineeringOS()
    result = eos.run_task(title="Fix login bug", description="...")
"""

from __future__ import annotations

from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.execution.task_engine import TaskEngine
from openhands.execution.task_models import (
    TaskPriority,
    TaskResult,
    TaskType,
)
from openhands.execution.task_runner import PhaseResult
from openhands.execution.task_state_machine import TaskPhase


class EngineeringOS:
    """Top-level orchestrator wiring the execution engine to subsystems.

    Creates a TaskEngine and exposes run_task() as the canonical way
    to execute tasks. Integration setters allow subsystems (repo_intel,
    memory, workflow, agents, policy, observability, platform) to be
    wired in after construction.
    """

    def __init__(self) -> None:
        self._engine = TaskEngine()

        # Register observability callbacks
        self._engine.on_phase_start(self._log_phase_start)
        self._engine.on_phase_end(self._log_phase_end)
        self._engine.on_task_complete(self._log_task_complete)

        logger.info('[EngineeringOS] Initialized with TaskEngine')

    @property
    def engine(self) -> TaskEngine:
        """Access the underlying TaskEngine."""
        return self._engine

    def run_task(
        self,
        title: str = '',
        description: str = '',
        task_type: TaskType = TaskType.CUSTOM,
        priority: TaskPriority = TaskPriority.NORMAL,
        repo_path: str = '',
        repo_name: str = '',
        branch_name: str = '',
        base_branch: str = 'main',
        max_retries: int = 3,
        timeout_s: float = 600.0,
        require_tests: bool = True,
        require_review: bool = True,
        auto_pr: bool = True,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        model_name: str = '',
        provider: str = '',
    ) -> TaskResult:
        """Submit and run a task through the execution engine.

        This is the canonical entry point for all task execution.
        It submits the task to the engine and runs it through all phases.

        Returns:
            TaskResult with success/failure and all artifacts
        """
        task_id = self._engine.submit(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            repo_path=repo_path,
            repo_name=repo_name,
            branch_name=branch_name,
            base_branch=base_branch,
            max_retries=max_retries,
            timeout_s=timeout_s,
            require_tests=require_tests,
            require_review=require_review,
            auto_pr=auto_pr,
            tags=tags,
            metadata=metadata,
            model_name=model_name,
            provider=provider,
        )

        return self._engine.run(task_id)

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get current status of a running or completed task."""
        return self._engine.get_task_status(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all tasks with their current status."""
        return self._engine.list_tasks()

    # ── Observability callbacks ──────────────────────────────────────────

    @staticmethod
    def _log_phase_start(task_id: str, phase: TaskPhase) -> None:
        logger.info(f'[EngineeringOS] Phase START: {phase.value} (task={task_id})')

    @staticmethod
    def _log_phase_end(
        task_id: str, phase: TaskPhase, result: PhaseResult
    ) -> None:
        status = 'OK' if result.success else 'FAIL'
        logger.info(
            f'[EngineeringOS] Phase END: {phase.value} [{status}] '
            f'duration={result.duration_s:.2f}s (task={task_id})'
        )

    @staticmethod
    def _log_task_complete(task_id: str, result: TaskResult) -> None:
        status = 'SUCCESS' if result.success else 'FAILED'
        logger.info(
            f'[EngineeringOS] Task COMPLETE: {task_id} [{status}] '
            f'duration={result.duration_s:.2f}s, '
            f'retries={result.retry_count}, '
            f'artifacts={len(result.artifacts)}'
        )
