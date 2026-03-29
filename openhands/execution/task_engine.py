"""Task Engine — the central orchestrator of the execution pipeline.

This is the canonical execution entrypoint that replaces AgentController's
_step() loop. Every task flows through TaskEngine.run() which drives it
through the deterministic state machine phases.

Usage:
    engine = TaskEngine()
    task_id = engine.submit(title="Fix login bug", description="...")
    result = engine.run(task_id)
"""

from __future__ import annotations

import time
from typing import Any, Callable

from openhands.core.logger import openhands_logger as logger
from openhands.execution.task_models import (
    Task,
    TaskArtifact,
    TaskContext,
    TaskPriority,
    TaskResult,
    TaskType,
)
from openhands.execution.task_runner import PhaseResult, TaskRunner
from openhands.execution.task_state_machine import (
    TaskPhase,
    TaskStateMachine,
    TransitionError,
)


class TaskEngine:
    """Central orchestrator of the execution pipeline.

    Accepts tasks, drives them through the state machine, coordinates
    with the TaskRunner for phase execution, and handles failure/retry.

    Attributes:
        _tasks: Registry of all submitted tasks
        _state_machines: State machine per task
        _runner: The TaskRunner that executes individual phases
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._state_machines: dict[str, TaskStateMachine] = {}
        self._runner = TaskRunner()

        # Callbacks for observability
        self._on_phase_start: Callable[[str, TaskPhase], None] | None = None
        self._on_phase_end: Callable[[str, TaskPhase, PhaseResult], None] | None = None
        self._on_task_complete: Callable[[str, TaskResult], None] | None = None

        logger.info('[TaskEngine] Initialized')

    # ── Task submission ──────────────────────────────────────────────────

    def submit(
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
    ) -> str:
        """Submit a new task for execution.

        Returns:
            task_id: The unique ID of the submitted task
        """
        context = TaskContext(
            repo_path=repo_path,
            repo_name=repo_name,
            branch_name=branch_name,
            base_branch=base_branch,
            model_name=model_name,
            provider=provider,
        )

        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            context=context,
            max_retries=max_retries,
            timeout_s=timeout_s,
            require_tests=require_tests,
            require_review=require_review,
            auto_pr=auto_pr,
            tags=tags or [],
            metadata=metadata or {},
        )

        task.result.max_retries = max_retries
        self._tasks[task.task_id] = task
        sm = TaskStateMachine(task.task_id)
        sm.set_max_retries(max_retries)
        self._state_machines[task.task_id] = sm

        logger.info(
            f'[TaskEngine] Task submitted: {task.task_id} — "{title}"'
        )
        return task.task_id

    # ── Task execution ───────────────────────────────────────────────────

    def run(self, task_id: str) -> TaskResult:
        """Run a submitted task through the full execution pipeline.

        This is the main entry point. It drives the task through all phases
        of the state machine until it reaches a terminal state.

        Args:
            task_id: The ID of the task to run

        Returns:
            TaskResult with success/failure and all artifacts
        """
        task = self._tasks.get(task_id)
        if task is None:
            return TaskResult(
                success=False,
                error=f'Task {task_id} not found',
            )

        sm = self._state_machines.get(task_id)
        if sm is None:
            return TaskResult(
                success=False,
                error=f'State machine for {task_id} not found',
            )

        task.started_at = time.time()
        logger.info(f'[TaskEngine] Starting task: {task_id}')

        try:
            self._run_pipeline(task, sm)
        except Exception as exc:
            logger.error(f'[TaskEngine] Pipeline error for {task_id}: {exc}')
            task.result.success = False
            task.result.error = f'Pipeline error: {exc}'
            if not sm.is_terminal:
                try:
                    sm.transition_to(TaskPhase.FAILED, success=False, error=str(exc))
                except TransitionError:
                    pass

        task.completed_at = time.time()
        task.result.duration_s = task.duration_s

        logger.info(
            f'[TaskEngine] Task {task_id} finished: '
            f'success={task.result.success}, '
            f'phase={sm.current_phase.value}, '
            f'duration={task.result.duration_s:.2f}s, '
            f'retries={sm.retry_count}'
        )

        if self._on_task_complete:
            try:
                self._on_task_complete(task_id, task.result)
            except Exception as exc:
                logger.warning(f'[TaskEngine] on_task_complete callback failed: {exc}')

        return task.result

    def _run_pipeline(self, task: Task, sm: TaskStateMachine) -> None:
        """Drive the task through the execution pipeline.

        The pipeline follows the deterministic phase sequence:
        INTAKE -> CONTEXT_BUILD -> REPO_ANALYSIS -> PLAN -> EXECUTE -> TEST ->
        REVIEW -> ARTIFACT_GENERATION -> COMPLETE

        With failure handling:
        (any phase fails) -> FAILURE_ANALYSIS -> RETRY_OR_FIX -> back to EXECUTE

        Fix #7: REPO_ANALYSIS is a MANDATORY gate before PLAN.
        If REPO_ANALYSIS fails, the pipeline does NOT proceed to PLAN.
        This ensures that the planner always has repo intelligence context.

        The pipeline exits when the state machine reaches a terminal state.
        """
        # Phase sequence for the happy path
        happy_path: list[TaskPhase] = [
            TaskPhase.INTAKE,
            TaskPhase.CONTEXT_BUILD,
            TaskPhase.REPO_ANALYSIS,
            TaskPhase.PLAN,
            TaskPhase.EXECUTE,
            TaskPhase.TEST,
            TaskPhase.REVIEW,
            TaskPhase.ARTIFACT_GENERATION,
            TaskPhase.COMPLETE,
        ]

        phase_idx = 0
        repo_analysis_passed = False  # Fix #7: track REPO_ANALYSIS gate

        while not sm.is_terminal and phase_idx < len(happy_path):
            current_target = happy_path[phase_idx]

            # Fix #7: REPO_ANALYSIS is a mandatory gate before PLAN.
            # If we're about to enter PLAN but REPO_ANALYSIS didn't pass,
            # block the pipeline — the planner MUST have repo context.
            if (
                current_target == TaskPhase.PLAN
                and not repo_analysis_passed
                and task.context.repo_path  # Only enforce if there's a repo
            ):
                logger.error(
                    f'[TaskEngine] PLAN blocked: REPO_ANALYSIS gate not passed '
                    f'for task {task.task_id}'
                )
                task.result.success = False
                task.result.error = (
                    'PLAN phase blocked: REPO_ANALYSIS must complete successfully '
                    'before planning can begin (Fix #7: mandatory gate)'
                )
                sm.transition_to(
                    TaskPhase.FAILED,
                    success=False,
                    error=task.result.error,
                )
                break

            # Skip if we're already past this phase (e.g. after retry)
            if sm.current_phase == current_target:
                # We're at this phase — execute it
                result = self._execute_phase(task, sm, current_target)

                # Fix #7: Track REPO_ANALYSIS gate status
                if current_target == TaskPhase.REPO_ANALYSIS and result.success:
                    repo_analysis_passed = True

                if result.success:
                    # Move to next phase
                    phase_idx += 1
                    if phase_idx < len(happy_path):
                        next_phase = happy_path[phase_idx]
                        if next_phase == TaskPhase.COMPLETE:
                            # COMPLETE is terminal — transition directly
                            task.result.success = True
                            task.result.message = 'Task completed successfully'
                            sm.transition_to(TaskPhase.COMPLETE, success=True)
                        else:
                            sm.transition_to(next_phase, success=True)
                    else:
                        # All phases done
                        task.result.success = True
                        task.result.message = 'Task completed successfully'
                        if not sm.is_terminal:
                            sm.transition_to(TaskPhase.COMPLETE, success=True)
                else:
                    # Phase failed — enter failure handling
                    self._handle_phase_failure(task, sm, current_target, result)
                    if sm.is_terminal:
                        break
                    # After retry, we loop back to EXECUTE
                    if sm.current_phase == TaskPhase.EXECUTE:
                        phase_idx = happy_path.index(TaskPhase.EXECUTE)
                    elif sm.current_phase == TaskPhase.PLAN:
                        phase_idx = happy_path.index(TaskPhase.PLAN)
            elif current_target == TaskPhase.INTAKE:
                # First phase — just transition won't work since we start AT intake
                result = self._execute_phase(task, sm, TaskPhase.INTAKE)
                if result.success:
                    phase_idx += 1
                    sm.transition_to(happy_path[phase_idx], success=True)
                else:
                    task.result.success = False
                    task.result.error = f'INTAKE failed: {result.error}'
                    sm.transition_to(TaskPhase.CANCELLED, success=False, error=result.error)
            else:
                # We need to transition to this phase first
                # This shouldn't happen in normal flow but handles edge cases
                try:
                    sm.transition_to(current_target, success=True)
                except TransitionError as exc:
                    logger.error(
                        f'[TaskEngine] Cannot transition to {current_target.value}: {exc}'
                    )
                    break

    def _execute_phase(
        self, task: Task, sm: TaskStateMachine, phase: TaskPhase
    ) -> PhaseResult:
        """Execute a single phase and record the result."""
        logger.info(
            f'[TaskEngine] Executing phase: {phase.value} for task {task.task_id}'
        )

        if self._on_phase_start:
            try:
                self._on_phase_start(task.task_id, phase)
            except Exception:
                pass

        result = self._runner.run_phase(phase, task)

        # Record phase result on the task
        task.result.set_phase_result(
            phase.value, result.success, result.error or str(result.output)[:500]
        )

        # Collect artifacts
        for artifact in result.artifacts:
            task.result.add_artifact(artifact)

        if self._on_phase_end:
            try:
                self._on_phase_end(task.task_id, phase, result)
            except Exception:
                pass

        return result

    def _handle_phase_failure(
        self,
        task: Task,
        sm: TaskStateMachine,
        failed_phase: TaskPhase,
        result: PhaseResult,
    ) -> None:
        """Handle a phase failure — analyze, decide retry or fail.

        Flow: failed_phase -> FAILURE_ANALYSIS -> RETRY_OR_FIX -> EXECUTE/PLAN
        Or:   failed_phase -> FAILED (if retries exhausted)
        """
        task.result.error = result.error
        logger.warning(
            f'[TaskEngine] Phase {failed_phase.value} failed: {result.error}'
        )

        # Check if we can retry
        if not sm.can_retry():
            logger.error(
                f'[TaskEngine] Max retries ({sm.retry_count}) exhausted for {task.task_id}'
            )
            task.result.success = False
            task.result.message = f'Failed after {sm.retry_count} retries'
            sm.transition_to(
                TaskPhase.FAILED,
                success=False,
                error=f'Max retries exhausted: {result.error}',
            )
            return

        # Only EXECUTE and TEST failures can be retried
        if failed_phase not in (TaskPhase.EXECUTE, TaskPhase.TEST):
            logger.error(
                f'[TaskEngine] Phase {failed_phase.value} is not retryable'
            )
            task.result.success = False
            task.result.message = f'{failed_phase.value} failed (not retryable)'
            sm.transition_to(
                TaskPhase.FAILED,
                success=False,
                error=result.error,
            )
            return

        # Transition to FAILURE_ANALYSIS
        sm.transition_to(
            TaskPhase.FAILURE_ANALYSIS,
            success=False,
            error=result.error,
        )
        analysis_result = self._execute_phase(task, sm, TaskPhase.FAILURE_ANALYSIS)

        # Transition to RETRY_OR_FIX
        sm.transition_to(
            TaskPhase.RETRY_OR_FIX,
            success=analysis_result.success,
        )
        fix_result = self._execute_phase(task, sm, TaskPhase.RETRY_OR_FIX)

        # Increment retry count
        task.result.retry_count += 1

        if fix_result.success:
            # Go back to EXECUTE
            sm.transition_to(TaskPhase.EXECUTE, success=True)
            logger.info(
                f'[TaskEngine] Retrying EXECUTE (attempt {task.result.retry_count})'
            )
        else:
            # Fix failed — try going back to PLAN for re-planning
            try:
                sm.transition_to(TaskPhase.PLAN, success=False, error='Fix failed')
                logger.info('[TaskEngine] Re-planning after fix failure')
            except TransitionError:
                sm.transition_to(
                    TaskPhase.FAILED,
                    success=False,
                    error=f'Fix failed and cannot re-plan: {fix_result.error}',
                )

    # ── Integration setters (delegated to TaskRunner) ────────────────────

    def set_context_builder(
        self, fn: Callable[[Task], dict[str, Any]]
    ) -> None:
        """Set the CONTEXT_BUILD phase integration."""
        self._runner.set_context_builder(fn)

    def set_repo_analyzer(
        self, fn: Callable[[Task], dict[str, Any]]
    ) -> None:
        """Set the REPO_ANALYSIS phase integration."""
        self._runner.set_repo_analyzer(fn)

    def set_planner(
        self, fn: Callable[[Task], list[dict[str, Any]]]
    ) -> None:
        """Set the PLAN phase integration."""
        self._runner.set_planner(fn)

    def set_executor(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        """Set the EXECUTE phase integration."""
        self._runner.set_executor(fn)

    def set_tester(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        """Set the TEST phase integration."""
        self._runner.set_tester(fn)

    def set_failure_analyzer(
        self, fn: Callable[[Task], dict[str, Any]]
    ) -> None:
        """Set the FAILURE_ANALYSIS phase integration."""
        self._runner.set_failure_analyzer(fn)

    def set_fixer(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        """Set the RETRY_OR_FIX phase integration."""
        self._runner.set_fixer(fn)

    def set_reviewer(self, fn: Callable[[Task], dict[str, Any]]) -> None:
        """Set the REVIEW phase integration."""
        self._runner.set_reviewer(fn)

    def set_artifact_generator(
        self, fn: Callable[[Task], list[TaskArtifact]]
    ) -> None:
        """Set the ARTIFACT_GENERATION phase integration."""
        self._runner.set_artifact_generator(fn)

    # ── Observability callbacks ──────────────────────────────────────────

    def on_phase_start(
        self, callback: Callable[[str, TaskPhase], None]
    ) -> None:
        """Register a callback for when a phase starts."""
        self._on_phase_start = callback

    def on_phase_end(
        self, callback: Callable[[str, TaskPhase, PhaseResult], None]
    ) -> None:
        """Register a callback for when a phase ends."""
        self._on_phase_end = callback

    def on_task_complete(
        self, callback: Callable[[str, TaskResult], None]
    ) -> None:
        """Register a callback for when a task completes."""
        self._on_task_complete = callback

    # ── Query methods ────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_state_machine(self, task_id: str) -> TaskStateMachine | None:
        """Get a task's state machine."""
        return self._state_machines.get(task_id)

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get current status of a task."""
        task = self._tasks.get(task_id)
        sm = self._state_machines.get(task_id)
        if task is None or sm is None:
            return {'error': f'Task {task_id} not found'}

        return {
            'task_id': task_id,
            'title': task.title,
            'current_phase': sm.current_phase.value,
            'is_terminal': sm.is_terminal,
            'retry_count': sm.retry_count,
            'duration_s': task.duration_s,
            'success': task.result.success,
            'error': task.result.error,
            'phase_results': task.result.phase_results,
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all submitted tasks with their current status."""
        return [self.get_task_status(tid) for tid in self._tasks]

    @property
    def runner(self) -> TaskRunner:
        """Access the underlying TaskRunner."""
        return self._runner
