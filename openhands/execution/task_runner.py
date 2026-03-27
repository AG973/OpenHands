"""Task Runner — executes individual phases of the task lifecycle.

Each phase has a dedicated handler that receives the Task and its context,
performs the phase work, and returns a PhaseResult. Handlers can be
overridden by registering custom callables for any phase.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from openhands.core.logger import openhands_logger as logger
from openhands.execution.task_models import (
    ArtifactType,
    Task,
    TaskArtifact,
    TaskContext,
    TaskType,
)
from openhands.execution.task_state_machine import TaskPhase


@dataclass
class PhaseResult:
    """Result of executing a single phase."""

    phase: TaskPhase
    success: bool = True
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ''
    duration_s: float = 0.0
    artifacts: list[TaskArtifact] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'phase': self.phase.value,
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'duration_s': self.duration_s,
            'artifacts': [a.to_dict() for a in self.artifacts],
        }


class PhaseHandler(Protocol):
    """Protocol for phase handler callables."""

    def __call__(self, task: Task) -> PhaseResult: ...


class TaskRunner:
    """Executes individual phases of the task lifecycle.

    Maintains a registry of phase handlers. Each phase has a default
    implementation that can be overridden by registering a custom handler.

    Integration points:
        - set_context_builder(fn): Override CONTEXT_BUILD phase
        - set_repo_analyzer(fn): Override REPO_ANALYSIS phase
        - set_planner(fn): Override PLAN phase
        - set_executor(fn): Override EXECUTE phase
        - set_tester(fn): Override TEST phase
        - set_failure_analyzer(fn): Override FAILURE_ANALYSIS phase
        - set_fixer(fn): Override RETRY_OR_FIX phase
        - set_reviewer(fn): Override REVIEW phase
        - set_artifact_generator(fn): Override ARTIFACT_GENERATION phase
    """

    def __init__(self) -> None:
        self._handlers: dict[TaskPhase, Callable[[Task], PhaseResult]] = {
            TaskPhase.INTAKE: self._handle_intake,
            TaskPhase.CONTEXT_BUILD: self._handle_context_build,
            TaskPhase.REPO_ANALYSIS: self._handle_repo_analysis,
            TaskPhase.PLAN: self._handle_plan,
            TaskPhase.EXECUTE: self._handle_execute,
            TaskPhase.TEST: self._handle_test,
            TaskPhase.FAILURE_ANALYSIS: self._handle_failure_analysis,
            TaskPhase.RETRY_OR_FIX: self._handle_retry_or_fix,
            TaskPhase.REVIEW: self._handle_review,
            TaskPhase.ARTIFACT_GENERATION: self._handle_artifact_generation,
        }

        # External integration callables (set by EngineeringOS or caller)
        self._context_builder: Callable[[Task], dict[str, Any]] | None = None
        self._repo_analyzer: Callable[[Task], dict[str, Any]] | None = None
        self._planner: Callable[[Task], list[dict[str, Any]]] | None = None
        self._executor: Callable[[Task], dict[str, Any]] | None = None
        self._tester: Callable[[Task], dict[str, Any]] | None = None
        self._failure_analyzer: Callable[[Task], dict[str, Any]] | None = None
        self._fixer: Callable[[Task], dict[str, Any]] | None = None
        self._reviewer: Callable[[Task], dict[str, Any]] | None = None
        self._artifact_generator: Callable[[Task], list[TaskArtifact]] | None = None

    # ── Integration setters ──────────────────────────────────────────────

    def set_context_builder(
        self, fn: Callable[[Task], dict[str, Any]]
    ) -> None:
        self._context_builder = fn

    def set_repo_analyzer(
        self, fn: Callable[[Task], dict[str, Any]]
    ) -> None:
        self._repo_analyzer = fn

    def set_planner(
        self, fn: Callable[[Task], list[dict[str, Any]]]
    ) -> None:
        self._planner = fn

    def set_executor(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        self._executor = fn

    def set_tester(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        self._tester = fn

    def set_failure_analyzer(
        self, fn: Callable[[Task], dict[str, Any]]
    ) -> None:
        self._failure_analyzer = fn

    def set_fixer(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        self._fixer = fn

    def set_reviewer(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        self._reviewer = fn

    def set_artifact_generator(
        self, fn: Callable[[Task], list[TaskArtifact]]
    ) -> None:
        self._artifact_generator = fn

    # ── Core execution ───────────────────────────────────────────────────

    def run_phase(self, phase: TaskPhase, task: Task) -> PhaseResult:
        """Execute a single phase for the given task.

        Args:
            phase: The phase to execute
            task: The task being processed

        Returns:
            PhaseResult with success/failure and output data
        """
        handler = self._handlers.get(phase)
        if handler is None:
            return PhaseResult(
                phase=phase,
                success=False,
                error=f'No handler registered for phase {phase.value}',
            )

        start = time.time()
        try:
            result = handler(task)
            result.duration_s = time.time() - start
            logger.info(
                f'[TaskRunner] Phase {phase.value} completed: '
                f'success={result.success}, duration={result.duration_s:.2f}s'
            )
            return result
        except Exception as exc:
            duration = time.time() - start
            error_msg = f'{type(exc).__name__}: {exc}'
            logger.error(
                f'[TaskRunner] Phase {phase.value} failed: {error_msg}'
            )
            return PhaseResult(
                phase=phase,
                success=False,
                error=error_msg,
                duration_s=duration,
                artifacts=[
                    TaskArtifact(
                        artifact_type=ArtifactType.ERROR_REPORT,
                        name=f'{phase.value}_error',
                        content=traceback.format_exc(),
                    )
                ],
            )

    def register_handler(
        self, phase: TaskPhase, handler: Callable[[Task], PhaseResult]
    ) -> None:
        """Register a custom handler for a phase."""
        self._handlers[phase] = handler

    # ── Default phase handlers ───────────────────────────────────────────

    def _handle_intake(self, task: Task) -> PhaseResult:
        """INTAKE: Validate and classify the incoming task.

        - Ensures task has title and description
        - Auto-classifies task type if not set
        - Sets up initial context
        """
        errors: list[str] = []

        if not task.title and not task.description:
            errors.append('Task must have a title or description')

        if errors:
            return PhaseResult(
                phase=TaskPhase.INTAKE,
                success=False,
                error='; '.join(errors),
            )

        # Auto-classify task type from description keywords
        if task.task_type == TaskType.CUSTOM and task.description:
            desc_lower = task.description.lower()
            if any(w in desc_lower for w in ['fix', 'bug', 'error', 'crash']):
                task.task_type = TaskType.BUG_FIX
            elif any(w in desc_lower for w in ['add', 'feature', 'implement', 'create']):
                task.task_type = TaskType.FEATURE
            elif any(w in desc_lower for w in ['refactor', 'clean', 'reorganize']):
                task.task_type = TaskType.REFACTOR
            elif any(w in desc_lower for w in ['test', 'spec', 'coverage']):
                task.task_type = TaskType.TEST
            elif any(w in desc_lower for w in ['doc', 'readme', 'comment']):
                task.task_type = TaskType.DOCUMENTATION

        # Initialize context with task ID
        task.context.task_id = task.task_id

        logger.info(
            f'[TaskRunner] INTAKE: task={task.task_id}, '
            f'type={task.task_type.value}, priority={task.priority.value}'
        )

        return PhaseResult(
            phase=TaskPhase.INTAKE,
            success=True,
            output={
                'task_type': task.task_type.value,
                'priority': task.priority.value,
                'has_repo': bool(task.context.repo_path),
            },
        )

    def _handle_context_build(self, task: Task) -> PhaseResult:
        """CONTEXT_BUILD: Gather context from memory subsystems.

        If a context_builder integration is set, delegates to it.
        Otherwise, creates a minimal context from available task data.
        """
        if self._context_builder:
            try:
                context_data = self._context_builder(task)
                task.context.error_memory = context_data.get('error_memory', [])
                task.context.fix_memory = context_data.get('fix_memory', [])
                task.context.decision_memory = context_data.get('decision_memory', [])
                task.context.repo_memory = context_data.get('repo_memory', {})
                logger.info(
                    f'[TaskRunner] CONTEXT_BUILD: loaded '
                    f'{len(task.context.error_memory)} errors, '
                    f'{len(task.context.fix_memory)} fixes from memory'
                )
                return PhaseResult(
                    phase=TaskPhase.CONTEXT_BUILD,
                    success=True,
                    output=context_data,
                )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] CONTEXT_BUILD integration failed: {exc}, '
                    f'falling back to default'
                )

        # Default: minimal context from task data
        return PhaseResult(
            phase=TaskPhase.CONTEXT_BUILD,
            success=True,
            output={
                'source': 'default',
                'repo_path': task.context.repo_path,
                'repo_name': task.context.repo_name,
            },
        )

    def _handle_repo_analysis(self, task: Task) -> PhaseResult:
        """REPO_ANALYSIS: Analyze repository structure and dependencies.

        If a repo_analyzer integration is set, delegates to it.
        Otherwise, creates minimal repo context.
        """
        if self._repo_analyzer:
            try:
                repo_data = self._repo_analyzer(task)
                task.context.file_map = repo_data.get('file_map', {})
                task.context.dependency_graph = repo_data.get('dependency_graph', {})
                task.context.test_map = repo_data.get('test_map', {})
                task.context.api_map = repo_data.get('api_map', {})
                task.context.impact_files = repo_data.get('impact_files', [])
                task.context.service_boundaries = repo_data.get('service_boundaries', [])
                logger.info(
                    f'[TaskRunner] REPO_ANALYSIS: '
                    f'{len(task.context.file_map)} files, '
                    f'{len(task.context.dependency_graph)} deps, '
                    f'{len(task.context.test_map)} test mappings'
                )
                return PhaseResult(
                    phase=TaskPhase.REPO_ANALYSIS,
                    success=True,
                    output=repo_data,
                )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] REPO_ANALYSIS integration failed: {exc}, '
                    f'falling back to default'
                )

        # Default: no repo analysis (still succeeds — repo intel is optional)
        return PhaseResult(
            phase=TaskPhase.REPO_ANALYSIS,
            success=True,
            output={'source': 'default', 'repo_path': task.context.repo_path},
        )

    def _handle_plan(self, task: Task) -> PhaseResult:
        """PLAN: Create execution plan from task + context.

        If a planner integration is set, delegates to it.
        Otherwise, creates a single-step plan.
        """
        if self._planner:
            try:
                plan_steps = self._planner(task)
                task.context.plan_steps = plan_steps
                logger.info(
                    f'[TaskRunner] PLAN: generated {len(plan_steps)} steps'
                )
                return PhaseResult(
                    phase=TaskPhase.PLAN,
                    success=True,
                    output={'plan_steps': plan_steps},
                )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] PLAN integration failed: {exc}, '
                    f'falling back to default'
                )

        # Default: single-step plan
        default_plan = [
            {
                'step': 1,
                'action': 'execute',
                'description': task.description or task.title,
                'type': task.task_type.value,
            }
        ]
        task.context.plan_steps = default_plan
        return PhaseResult(
            phase=TaskPhase.PLAN,
            success=True,
            output={'plan_steps': default_plan, 'source': 'default'},
        )

    def _handle_execute(self, task: Task) -> PhaseResult:
        """EXECUTE: Run the actual implementation work.

        This is the core phase — an executor integration MUST be set
        for real work to happen. Without it, the phase succeeds as a
        no-op (useful for dry runs and testing).
        """
        if self._executor:
            try:
                exec_result = self._executor(task)
                logger.info(
                    f'[TaskRunner] EXECUTE: completed with '
                    f'{len(exec_result)} output keys'
                )
                return PhaseResult(
                    phase=TaskPhase.EXECUTE,
                    success=exec_result.get('success', True),
                    output=exec_result,
                    error=exec_result.get('error', ''),
                )
            except Exception as exc:
                return PhaseResult(
                    phase=TaskPhase.EXECUTE,
                    success=False,
                    error=f'Executor failed: {exc}',
                    artifacts=[
                        TaskArtifact(
                            artifact_type=ArtifactType.ERROR_REPORT,
                            name='execute_error',
                            content=traceback.format_exc(),
                        )
                    ],
                )

        # Default: no-op (dry run mode)
        logger.info('[TaskRunner] EXECUTE: no executor set, dry-run mode')
        return PhaseResult(
            phase=TaskPhase.EXECUTE,
            success=True,
            output={'mode': 'dry_run', 'executor': 'none'},
        )

    def _handle_test(self, task: Task) -> PhaseResult:
        """TEST: Run tests against changes.

        If a tester integration is set, delegates to it.
        If require_tests is False, skips testing.
        """
        if not task.require_tests:
            logger.info('[TaskRunner] TEST: skipped (require_tests=False)')
            return PhaseResult(
                phase=TaskPhase.TEST,
                success=True,
                output={'skipped': True, 'reason': 'require_tests=False'},
            )

        if self._tester:
            try:
                test_result = self._tester(task)
                success = test_result.get('success', True)
                logger.info(
                    f'[TaskRunner] TEST: '
                    f'passed={test_result.get("passed", 0)}, '
                    f'failed={test_result.get("failed", 0)}'
                )
                artifacts = []
                if 'output' in test_result:
                    artifacts.append(
                        TaskArtifact(
                            artifact_type=ArtifactType.TEST_RESULT,
                            name='test_output',
                            content=str(test_result['output'])[:5000],
                        )
                    )
                return PhaseResult(
                    phase=TaskPhase.TEST,
                    success=success,
                    output=test_result,
                    error=test_result.get('error', ''),
                    artifacts=artifacts,
                )
            except Exception as exc:
                return PhaseResult(
                    phase=TaskPhase.TEST,
                    success=False,
                    error=f'Tester failed: {exc}',
                )

        # Default: no tester set, pass
        logger.info('[TaskRunner] TEST: no tester set, skipping')
        return PhaseResult(
            phase=TaskPhase.TEST,
            success=True,
            output={'skipped': True, 'reason': 'no_tester_set'},
        )

    def _handle_failure_analysis(self, task: Task) -> PhaseResult:
        """FAILURE_ANALYSIS: Analyze why execution or tests failed.

        Classifies the error and determines retry strategy.
        """
        last_error = task.result.error

        if self._failure_analyzer:
            try:
                analysis = self._failure_analyzer(task)
                logger.info(
                    f'[TaskRunner] FAILURE_ANALYSIS: '
                    f'category={analysis.get("category", "unknown")}'
                )
                return PhaseResult(
                    phase=TaskPhase.FAILURE_ANALYSIS,
                    success=True,
                    output=analysis,
                )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] FAILURE_ANALYSIS integration failed: {exc}'
                )

        # Default: basic error classification
        category = 'unknown'
        if last_error:
            error_lower = last_error.lower()
            if 'syntax' in error_lower or 'parse' in error_lower:
                category = 'syntax_error'
            elif 'import' in error_lower or 'module' in error_lower:
                category = 'import_error'
            elif 'test' in error_lower or 'assert' in error_lower:
                category = 'test_failure'
            elif 'timeout' in error_lower:
                category = 'timeout'
            elif 'permission' in error_lower or 'auth' in error_lower:
                category = 'permission_error'
            else:
                category = 'runtime_error'

        task.result.error_category = category

        return PhaseResult(
            phase=TaskPhase.FAILURE_ANALYSIS,
            success=True,
            output={
                'category': category,
                'original_error': last_error[:500] if last_error else '',
                'retry_recommended': category in (
                    'timeout',
                    'runtime_error',
                    'test_failure',
                ),
            },
        )

    def _handle_retry_or_fix(self, task: Task) -> PhaseResult:
        """RETRY_OR_FIX: Apply fix strategy and prepare for retry.

        If a fixer integration is set, delegates to it.
        Otherwise, just signals readiness to retry.
        """
        if self._fixer:
            try:
                fix_result = self._fixer(task)
                logger.info(
                    f'[TaskRunner] RETRY_OR_FIX: '
                    f'strategy={fix_result.get("strategy", "unknown")}'
                )
                return PhaseResult(
                    phase=TaskPhase.RETRY_OR_FIX,
                    success=fix_result.get('success', True),
                    output=fix_result,
                )
            except Exception as exc:
                return PhaseResult(
                    phase=TaskPhase.RETRY_OR_FIX,
                    success=False,
                    error=f'Fixer failed: {exc}',
                )

        # Default: signal retry with no fix applied
        return PhaseResult(
            phase=TaskPhase.RETRY_OR_FIX,
            success=True,
            output={
                'strategy': 'retry_without_fix',
                'retry_count': task.result.retry_count,
            },
        )

    def _handle_review(self, task: Task) -> PhaseResult:
        """REVIEW: Review changes before finalizing.

        If a reviewer integration is set, delegates to it.
        Otherwise, auto-approves.
        """
        if not task.require_review:
            logger.info('[TaskRunner] REVIEW: skipped (require_review=False)')
            return PhaseResult(
                phase=TaskPhase.REVIEW,
                success=True,
                output={'skipped': True, 'reason': 'require_review=False'},
            )

        if self._reviewer:
            try:
                review_result = self._reviewer(task)
                approved = review_result.get('approved', True)
                logger.info(
                    f'[TaskRunner] REVIEW: approved={approved}'
                )
                return PhaseResult(
                    phase=TaskPhase.REVIEW,
                    success=approved,
                    output=review_result,
                    error=review_result.get('rejection_reason', ''),
                )
            except Exception as exc:
                logger.warning(f'[TaskRunner] REVIEW integration failed: {exc}')

        # Default: auto-approve
        logger.info('[TaskRunner] REVIEW: auto-approved (no reviewer set)')
        return PhaseResult(
            phase=TaskPhase.REVIEW,
            success=True,
            output={'approved': True, 'source': 'auto'},
        )

    def _handle_artifact_generation(self, task: Task) -> PhaseResult:
        """ARTIFACT_GENERATION: Package results for delivery.

        Generates execution trace artifact and delegates to artifact_generator
        if one is set.
        """
        artifacts: list[TaskArtifact] = []

        # Always generate execution trace
        trace_artifact = TaskArtifact(
            artifact_type=ArtifactType.EXECUTION_TRACE,
            name='execution_trace',
            content=str(task.result.phase_results),
        )
        artifacts.append(trace_artifact)

        if self._artifact_generator:
            try:
                generated = self._artifact_generator(task)
                artifacts.extend(generated)
                logger.info(
                    f'[TaskRunner] ARTIFACT_GENERATION: '
                    f'{len(generated)} artifacts generated'
                )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] ARTIFACT_GENERATION integration failed: {exc}'
                )
                artifacts.append(
                    TaskArtifact(
                        artifact_type=ArtifactType.ERROR_REPORT,
                        name='artifact_generation_error',
                        content=str(exc),
                    )
                )

        # Add all artifacts to task result
        for artifact in artifacts:
            task.result.add_artifact(artifact)

        return PhaseResult(
            phase=TaskPhase.ARTIFACT_GENERATION,
            success=True,
            output={'artifact_count': len(artifacts)},
            artifacts=artifacts,
        )
