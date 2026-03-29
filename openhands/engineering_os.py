"""Engineering OS — top-level entry point that wires the execution engine.

This is the single entry point for running tasks through the CODEIT OS.
It creates a TaskEngine, wires memory + policy + observability subsystems
to the TaskRunner, and exposes run_task() as the canonical execution path.

Wiring:
    - ErrorMemory  → TaskRunner (for failure analysis, planning avoidance)
    - FixMemory    → TaskRunner (for retry strategy selection)
    - DecisionMemory → TaskRunner (for approach selection in planning)
    - RetryPolicy  → TaskRunner (for retry/escalate decisions)
    - ToolSelector → TaskRunner (for per-step tool filtering)
    - ExecutionTrace → TaskRunner (for observability recording)
    - ArtifactBuilder → TaskRunner (for artifact persistence)

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

    Creates a TaskEngine and wires all memory, policy, and observability
    subsystems into the TaskRunner so every phase has full access to:
    - ErrorMemory: past errors and their resolutions
    - FixMemory: successful fix strategies
    - DecisionMemory: past decisions and outcomes
    - RetryPolicy: retry/escalate logic
    - ToolSelector: per-step tool filtering
    - ExecutionTrace: full execution recording
    - ArtifactBuilder: artifact persistence
    """

    def __init__(self) -> None:
        self._engine = TaskEngine()

        # ── Memory subsystems ─────────────────────────────────────────────
        self._error_memory = self._create_error_memory()
        self._fix_memory = self._create_fix_memory()
        self._decision_memory = self._create_decision_memory()

        # ── Policy subsystems ─────────────────────────────────────────────
        self._retry_policy = self._create_retry_policy()
        self._tool_selector = self._create_tool_selector()

        # ── Observability subsystems ──────────────────────────────────────
        self._execution_trace = self._create_execution_trace()
        self._artifact_builder = self._create_artifact_builder()

        # ── Wire everything into the TaskRunner ───────────────────────────
        self._wire_subsystems()

        # Register observability callbacks
        self._engine.on_phase_start(self._log_phase_start)
        self._engine.on_phase_end(self._log_phase_end)
        self._engine.on_task_complete(self._log_task_complete)

        logger.info(
            '[EngineeringOS] Initialized with TaskEngine + '
            'memory (error, fix, decision) + '
            'policy (retry, tool_selector) + '
            'observability (trace, artifact_builder)'
        )

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

    # ── Subsystem accessors ────────────────────────────────────────────

    @property
    def error_memory(self) -> Any:
        """Access the ErrorMemory subsystem."""
        return self._error_memory

    @property
    def fix_memory(self) -> Any:
        """Access the FixMemory subsystem."""
        return self._fix_memory

    @property
    def decision_memory(self) -> Any:
        """Access the DecisionMemory subsystem."""
        return self._decision_memory

    @property
    def retry_policy(self) -> Any:
        """Access the RetryPolicy subsystem."""
        return self._retry_policy

    @property
    def tool_selector(self) -> Any:
        """Access the ToolSelector subsystem."""
        return self._tool_selector

    @property
    def execution_trace(self) -> Any:
        """Access the ExecutionTrace subsystem."""
        return self._execution_trace

    @property
    def artifact_builder(self) -> Any:
        """Access the ArtifactBuilder subsystem."""
        return self._artifact_builder

    # ── Subsystem creation ────────────────────────────────────────────────

    @staticmethod
    def _create_error_memory() -> Any:
        """Create and return an ErrorMemory instance."""
        try:
            from openhands.memory.error_memory import ErrorMemory
            mem = ErrorMemory()
            logger.info('[EngineeringOS] ErrorMemory created')
            return mem
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ErrorMemory unavailable: {exc}')
            return None

    @staticmethod
    def _create_fix_memory() -> Any:
        """Create and return a FixMemory instance."""
        try:
            from openhands.memory.fix_memory import FixMemory
            mem = FixMemory()
            logger.info('[EngineeringOS] FixMemory created')
            return mem
        except Exception as exc:
            logger.warning(f'[EngineeringOS] FixMemory unavailable: {exc}')
            return None

    @staticmethod
    def _create_decision_memory() -> Any:
        """Create and return a DecisionMemory instance."""
        try:
            from openhands.memory.decision_memory import DecisionMemory
            mem = DecisionMemory()
            logger.info('[EngineeringOS] DecisionMemory created')
            return mem
        except Exception as exc:
            logger.warning(f'[EngineeringOS] DecisionMemory unavailable: {exc}')
            return None

    @staticmethod
    def _create_retry_policy() -> Any:
        """Create and return a RetryPolicy instance."""
        try:
            from openhands.policy.retry_policy import RetryPolicy
            policy = RetryPolicy()
            logger.info('[EngineeringOS] RetryPolicy created')
            return policy
        except Exception as exc:
            logger.warning(f'[EngineeringOS] RetryPolicy unavailable: {exc}')
            return None

    @staticmethod
    def _create_tool_selector() -> Any:
        """Create and return a ToolSelector instance."""
        try:
            from openhands.policy.tool_selector import ToolSelector
            selector = ToolSelector()
            logger.info('[EngineeringOS] ToolSelector created')
            return selector
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ToolSelector unavailable: {exc}')
            return None

    @staticmethod
    def _create_execution_trace() -> Any:
        """Create and return an ExecutionTrace instance."""
        try:
            from openhands.observability.execution_trace import ExecutionTrace
            trace = ExecutionTrace()
            logger.info('[EngineeringOS] ExecutionTrace created')
            return trace
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ExecutionTrace unavailable: {exc}')
            return None

    @staticmethod
    def _create_artifact_builder() -> Any:
        """Create and return an ArtifactBuilder instance."""
        try:
            from openhands.observability.artifact_builder import ArtifactBuilder
            builder = ArtifactBuilder()
            logger.info('[EngineeringOS] ArtifactBuilder created')
            return builder
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ArtifactBuilder unavailable: {exc}')
            return None

    def _wire_subsystems(self) -> None:
        """Wire all memory, policy, and observability subsystems into the TaskRunner.

        This is the key integration point — it connects every subsystem
        to the execution engine so all phases have access to memory,
        policy decisions, and observability recording.
        """
        runner = self._engine.runner

        # Wire memory subsystems
        if self._error_memory:
            runner.set_error_memory(self._error_memory)
        if self._fix_memory:
            runner.set_fix_memory(self._fix_memory)
        if self._decision_memory:
            runner.set_decision_memory(self._decision_memory)

        # Wire policy subsystems
        if self._retry_policy:
            runner.set_retry_policy(self._retry_policy)
        if self._tool_selector:
            runner.set_tool_selector(self._tool_selector)

        # Wire observability subsystems
        if self._execution_trace:
            runner.set_execution_trace(self._execution_trace)
        if self._artifact_builder:
            runner.set_artifact_builder(self._artifact_builder)

        wired_count = sum(1 for s in [
            self._error_memory, self._fix_memory, self._decision_memory,
            self._retry_policy, self._tool_selector,
            self._execution_trace, self._artifact_builder,
        ] if s is not None)

        logger.info(
            f'[EngineeringOS] Wired {wired_count}/7 subsystems into TaskRunner'
        )

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
