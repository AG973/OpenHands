"""Task Runner — executes individual phases of the task lifecycle.

Each phase has a dedicated handler method. The runner is called by the
TaskEngine for each phase transition. Phase handlers receive the full
TaskContext and return success/failure with artifacts.

This is where the actual work happens — LLM calls, tool execution,
test running, PR generation, etc.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Protocol

from openhands.core.logger import openhands_logger as logger
from openhands.execution.task_models import (
    ArtifactType,
    Task,
    TaskArtifact,
    TaskContext,
    TaskResult,
)
from openhands.execution.task_state_machine import TaskPhase


class PhaseHandler(Protocol):
    """Protocol for phase handler callables."""

    def __call__(
        self, task: Task, context: TaskContext
    ) -> PhaseResult: ...


class PhaseResult:
    """Result of executing a single phase."""

    __slots__ = ('success', 'error', 'artifacts', 'metadata', 'next_phase_hint')

    def __init__(
        self,
        success: bool = True,
        error: str = '',
        artifacts: list[TaskArtifact] | None = None,
        metadata: dict[str, Any] | None = None,
        next_phase_hint: TaskPhase | None = None,
    ) -> None:
        self.success = success
        self.error = error
        self.artifacts = artifacts or []
        self.metadata = metadata or {}
        self.next_phase_hint = next_phase_hint


class TaskRunner:
    """Executes individual phases of the task lifecycle.

    The runner maintains a registry of phase handlers. Each handler
    receives the task and its context, and returns a PhaseResult.

    Custom handlers can be registered to override default behavior,
    enabling extensibility without modifying core code.
    """

    def __init__(self) -> None:
        self._phase_handlers: dict[TaskPhase, Callable[..., PhaseResult]] = {}
        self._pre_phase_hooks: list[Callable[[TaskPhase, Task], None]] = []
        self._post_phase_hooks: list[Callable[[TaskPhase, Task, PhaseResult], None]] = []

        # Register default handlers
        self._register_defaults()

    def register_handler(
        self, phase: TaskPhase, handler: Callable[..., PhaseResult]
    ) -> None:
        """Register a custom handler for a phase.

        Args:
            phase: The phase this handler processes
            handler: Callable that takes (task, context) and returns PhaseResult
        """
        self._phase_handlers[phase] = handler
        logger.info(f'Registered custom handler for phase {phase.value}')

    def add_pre_phase_hook(
        self, hook: Callable[[TaskPhase, Task], None]
    ) -> None:
        """Add a hook that runs before each phase execution."""
        self._pre_phase_hooks.append(hook)

    def add_post_phase_hook(
        self, hook: Callable[[TaskPhase, Task, PhaseResult], None]
    ) -> None:
        """Add a hook that runs after each phase execution."""
        self._post_phase_hooks.append(hook)

    def run_phase(self, phase: TaskPhase, task: Task) -> PhaseResult:
        """Execute a phase for the given task.

        Args:
            phase: The phase to execute
            task: The task being processed

        Returns:
            PhaseResult with success/failure and any artifacts
        """
        handler = self._phase_handlers.get(phase)
        if handler is None:
            logger.warning(f'No handler registered for phase {phase.value}')
            return PhaseResult(
                success=True,
                metadata={'note': f'No handler for {phase.value}, passing through'},
            )

        # Run pre-phase hooks
        for hook in self._pre_phase_hooks:
            try:
                hook(phase, task)
            except Exception as e:
                logger.warning(f'Pre-phase hook error for {phase.value}: {e}')

        # Execute the phase handler
        start_time = time.time()
        try:
            result = handler(task, task.context)
            duration = time.time() - start_time

            logger.info(
                f'[TaskRunner] Phase {phase.value} completed in {duration:.2f}s '
                f'(success={result.success})'
            )

            # Add execution trace artifact
            result.artifacts.append(
                TaskArtifact(
                    artifact_type=ArtifactType.EXECUTION_TRACE,
                    name=f'phase_{phase.value}_trace',
                    content=f'Phase {phase.value}: success={result.success}, '
                    f'duration={duration:.2f}s, error={result.error or "none"}',
                    metadata={
                        'phase': phase.value,
                        'duration_s': duration,
                        'success': result.success,
                    },
                )
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f'[TaskRunner] Phase {phase.value} crashed after {duration:.2f}s: {e}'
            )
            result = PhaseResult(
                success=False,
                error=f'{type(e).__name__}: {str(e)}',
                artifacts=[
                    TaskArtifact(
                        artifact_type=ArtifactType.ERROR_REPORT,
                        name=f'phase_{phase.value}_crash',
                        content=f'Phase {phase.value} crashed: {e}',
                        metadata={'exception_type': type(e).__name__},
                    )
                ],
            )

        # Run post-phase hooks
        for hook in self._post_phase_hooks:
            try:
                hook(phase, task, result)
            except Exception as e:
                logger.warning(f'Post-phase hook error for {phase.value}: {e}')

        # Collect artifacts into task result
        for artifact in result.artifacts:
            task.result.add_artifact(artifact)

        # Record phase result
        task.result.set_phase_result(
            phase.value, result.success, result.error or result.metadata.get('note', '')
        )

        return result

    def _register_defaults(self) -> None:
        """Register default phase handlers."""
        self._phase_handlers[TaskPhase.INTAKE] = self._handle_intake
        self._phase_handlers[TaskPhase.CONTEXT_BUILD] = self._handle_context_build
        self._phase_handlers[TaskPhase.REPO_ANALYSIS] = self._handle_repo_analysis
        self._phase_handlers[TaskPhase.PLAN] = self._handle_plan
        self._phase_handlers[TaskPhase.EXECUTE] = self._handle_execute
        self._phase_handlers[TaskPhase.TEST] = self._handle_test
        self._phase_handlers[TaskPhase.FAILURE_ANALYSIS] = self._handle_failure_analysis
        self._phase_handlers[TaskPhase.RETRY_OR_FIX] = self._handle_retry_or_fix
        self._phase_handlers[TaskPhase.REVIEW] = self._handle_review
        self._phase_handlers[TaskPhase.ARTIFACT_GENERATION] = (
            self._handle_artifact_generation
        )

    # ── Default Phase Handlers ──────────────────────────────────────────

    def _handle_intake(self, task: Task, context: TaskContext) -> PhaseResult:
        """INTAKE: Validate and classify the incoming task.

        - Validate task has required fields
        - Classify task type if not set
        - Set defaults for configuration
        """
        if not task.title and not task.description:
            return PhaseResult(
                success=False,
                error='Task must have a title or description',
            )

        # Set task context reference
        context.task_id = task.task_id

        logger.info(
            f'[Intake] Task {task.task_id}: {task.title or task.description[:50]}'
        )
        return PhaseResult(
            success=True,
            metadata={
                'task_type': task.task_type.value,
                'priority': task.priority.value,
            },
        )

    def _handle_context_build(
        self, task: Task, context: TaskContext
    ) -> PhaseResult:
        """CONTEXT_BUILD: Gather context from memory, config, and environment.

        - Load error memory for similar past failures
        - Load fix memory for known solutions
        - Load decision memory for past choices
        - Gather available tools
        """
        logger.info(f'[ContextBuild] Building context for task {task.task_id}')

        # Context is populated by external integrations (memory system, etc.)
        # The default handler validates that minimum context exists
        return PhaseResult(
            success=True,
            metadata={
                'error_memory_count': len(context.error_memory),
                'fix_memory_count': len(context.fix_memory),
                'tools_available': len(context.available_tools),
            },
        )

    def _handle_repo_analysis(
        self, task: Task, context: TaskContext
    ) -> PhaseResult:
        """REPO_ANALYSIS: Analyze the repository structure.

        - Build file map
        - Extract dependency graph
        - Map tests to source files
        - Identify impact radius
        """
        logger.info(
            f'[RepoAnalysis] Analyzing repo for task {task.task_id}: '
            f'{context.repo_path or "no repo"}'
        )

        if not context.repo_path:
            return PhaseResult(
                success=True,
                metadata={'note': 'No repo path — skipping repo analysis'},
            )

        # Repo analysis is performed by the RepoIntelligence module
        # Results are stored in context.file_map, context.dependency_graph, etc.
        return PhaseResult(
            success=True,
            metadata={
                'file_count': len(context.file_map),
                'dependency_count': len(context.dependency_graph),
                'test_count': len(context.test_map),
            },
        )

    def _handle_plan(self, task: Task, context: TaskContext) -> PhaseResult:
        """PLAN: Create an execution plan for the task.

        Uses the LangGraphPlanner to decompose the task into steps.
        The plan is stored in the task metadata for execution.
        """
        logger.info(f'[Plan] Creating execution plan for task {task.task_id}')

        # Planning is performed by the planner agent role
        # The default handler creates a single-step plan
        return PhaseResult(
            success=True,
            metadata={'plan_steps': 1, 'plan_type': 'default_single_step'},
        )

    def _handle_execute(self, task: Task, context: TaskContext) -> PhaseResult:
        """EXECUTE: Run the actual implementation work.

        This is where the coder agent role does the work:
        - Generate code changes
        - Apply patches
        - Run commands
        - Create files
        """
        logger.info(f'[Execute] Executing task {task.task_id}')

        # Execution is performed by the coder agent role
        # The default handler is a pass-through for external wiring
        return PhaseResult(
            success=True,
            metadata={'note': 'Execution delegated to agent role system'},
        )

    def _handle_test(self, task: Task, context: TaskContext) -> PhaseResult:
        """TEST: Run tests against the changes.

        - Run test suite
        - Capture test output
        - Determine pass/fail
        """
        logger.info(f'[Test] Running tests for task {task.task_id}')

        if not task.require_tests:
            return PhaseResult(
                success=True,
                metadata={'note': 'Tests not required for this task'},
            )

        # Testing is performed by the tester agent role
        return PhaseResult(
            success=True,
            metadata={'note': 'Testing delegated to agent role system'},
        )

    def _handle_failure_analysis(
        self, task: Task, context: TaskContext
    ) -> PhaseResult:
        """FAILURE_ANALYSIS: Analyze why execution or tests failed.

        - Classify the error
        - Search error memory for similar past failures
        - Determine if retry is possible
        - Suggest fix strategy
        """
        logger.info(f'[FailureAnalysis] Analyzing failure for task {task.task_id}')

        last_error = task.result.error
        can_retry = task.result.can_retry

        return PhaseResult(
            success=True,
            metadata={
                'last_error': last_error,
                'can_retry': can_retry,
                'retry_count': task.result.retry_count,
            },
            next_phase_hint=(
                TaskPhase.RETRY_OR_FIX if can_retry else TaskPhase.FAILED
            ),
        )

    def _handle_retry_or_fix(
        self, task: Task, context: TaskContext
    ) -> PhaseResult:
        """RETRY_OR_FIX: Apply fix and retry execution.

        - Apply suggested fix from failure analysis
        - Increment retry counter
        - Loop back to EXECUTE phase
        """
        task.result.retry_count += 1
        logger.info(
            f'[RetryOrFix] Retry #{task.result.retry_count} for task {task.task_id}'
        )

        return PhaseResult(
            success=True,
            metadata={'retry_number': task.result.retry_count},
            next_phase_hint=TaskPhase.EXECUTE,
        )

    def _handle_review(self, task: Task, context: TaskContext) -> PhaseResult:
        """REVIEW: Review the changes before finalizing.

        - Code quality check
        - Security scan
        - Style consistency
        """
        logger.info(f'[Review] Reviewing changes for task {task.task_id}')

        if not task.require_review:
            return PhaseResult(
                success=True,
                metadata={'note': 'Review not required for this task'},
            )

        # Review is performed by the reviewer agent role
        return PhaseResult(
            success=True,
            metadata={'note': 'Review delegated to agent role system'},
        )

    def _handle_artifact_generation(
        self, task: Task, context: TaskContext
    ) -> PhaseResult:
        """ARTIFACT_GENERATION: Package results for delivery.

        - Generate PR if configured
        - Package diffs
        - Generate execution report
        - Bundle all artifacts
        """
        logger.info(f'[ArtifactGen] Generating artifacts for task {task.task_id}')

        # Generate summary artifact
        summary = TaskArtifact(
            artifact_type=ArtifactType.EXECUTION_TRACE,
            name='task_summary',
            content=(
                f'Task: {task.title}\n'
                f'Type: {task.task_type.value}\n'
                f'Duration: {task.duration_s:.2f}s\n'
                f'Retries: {task.result.retry_count}\n'
                f'Artifacts: {len(task.result.artifacts)}\n'
            ),
            metadata={
                'task_id': task.task_id,
                'duration_s': task.duration_s,
            },
        )

        return PhaseResult(
            success=True,
            artifacts=[summary],
            metadata={'artifact_count': len(task.result.artifacts) + 1},
        )
