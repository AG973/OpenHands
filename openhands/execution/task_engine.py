"""Task Engine — the central orchestrator of the execution pipeline.

This is the CORE of the engineering operating system. It:
1. Accepts tasks from any source (user, issue, automated)
2. Drives tasks through the state machine phases
3. Coordinates with repo intelligence, memory, workflow, and agent roles
4. Produces artifacts and execution traces
5. Manages retries, failures, and escalation

The TaskEngine replaces the reactive AgentController loop with a
deterministic, phase-driven execution pipeline.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from openhands.core.logger import openhands_logger as logger
from openhands.execution.task_models import (
    Task,
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


# Engine limits
MAX_CONCURRENT_TASKS = 10
MAX_TASK_DURATION_S = 3600  # 1 hour
MAX_PHASE_DURATION_S = 300  # 5 minutes per phase


class TaskEngine:
    """Central orchestrator for the execution pipeline.

    Usage:
        engine = TaskEngine()

        # Submit a task
        task = engine.submit(
            title="Fix login bug",
            description="Users can't login with email containing +",
            task_type=TaskType.BUG_FIX,
            repo_path="/workspace/myapp",
        )

        # Run the task through all phases
        result = engine.run(task.task_id)

        # Check result
        print(result.success, result.artifacts)
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._state_machines: dict[str, TaskStateMachine] = {}
        self._runner = TaskRunner()

        # Event hooks for external integration
        self._on_task_created: list[Callable[[Task], None]] = []
        self._on_task_completed: list[Callable[[Task], None]] = []
        self._on_phase_change: list[Callable[[str, TaskPhase, TaskPhase], None]] = []

        # Phase-specific integrations (set by external modules)
        self._context_builder: Callable[[Task], TaskContext] | None = None
        self._repo_analyzer: Callable[[Task, TaskContext], None] | None = None
        self._planner: Callable[[Task, TaskContext], list[dict[str, Any]]] | None = None
        self._executor: Callable[[Task, TaskContext], PhaseResult] | None = None
        self._tester: Callable[[Task, TaskContext], PhaseResult] | None = None
        self._reviewer: Callable[[Task, TaskContext], PhaseResult] | None = None

        logger.info('TaskEngine initialized')

    # ── Task Submission ─────────────────────────────────────────────────

    def submit(
        self,
        title: str = '',
        description: str = '',
        task_type: TaskType = TaskType.CUSTOM,
        priority: TaskPriority = TaskPriority.NORMAL,
        repo_path: str = '',
        source: str = 'user',
        max_retries: int = 3,
        require_tests: bool = True,
        require_review: bool = True,
        auto_pr: bool = True,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        parent_task_id: str = '',
    ) -> Task:
        """Submit a new task to the execution engine.

        Args:
            title: Short task title
            description: Full task description
            task_type: Classification of the task
            priority: Task priority
            repo_path: Path to the repository
            source: Where the task came from
            max_retries: Max retry attempts
            require_tests: Whether to run tests
            require_review: Whether to require review
            auto_pr: Whether to auto-generate PR
            tags: Optional tags
            metadata: Optional metadata
            parent_task_id: If this is a subtask

        Returns:
            The created Task object
        """
        if len(self._tasks) >= MAX_CONCURRENT_TASKS:
            raise RuntimeError(
                f'TaskEngine: max concurrent tasks ({MAX_CONCURRENT_TASKS}) reached'
            )

        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            source=source,
            max_retries=max_retries,
            require_tests=require_tests,
            require_review=require_review,
            auto_pr=auto_pr,
            tags=tags or [],
            metadata=metadata or {},
            parent_task_id=parent_task_id,
        )
        task.context.repo_path = repo_path

        # Initialize state machine
        sm = TaskStateMachine(task.task_id)
        sm.set_max_retries(max_retries)

        self._tasks[task.task_id] = task
        self._state_machines[task.task_id] = sm

        # Link parent-child
        if parent_task_id and parent_task_id in self._tasks:
            self._tasks[parent_task_id].child_task_ids.append(task.task_id)

        logger.info(
            f'[TaskEngine] Task submitted: {task.task_id} '
            f'({task.task_type.value}/{task.priority.value})'
        )

        # Notify hooks
        for hook in self._on_task_created:
            try:
                hook(task)
            except Exception as e:
                logger.warning(f'Task created hook error: {e}')

        return task

    # ── Task Execution ──────────────────────────────────────────────────

    def run(self, task_id: str) -> TaskResult:
        """Run a task through all phases of the execution pipeline.

        This is the main entry point. It drives the task through:
        INTAKE -> CONTEXT_BUILD -> REPO_ANALYSIS -> PLAN -> EXECUTE ->
        TEST -> (FAILURE_ANALYSIS -> RETRY_OR_FIX ->)* REVIEW ->
        ARTIFACT_GENERATION -> COMPLETE

        Args:
            task_id: ID of the task to run

        Returns:
            TaskResult with success/failure and artifacts
        """
        task = self._get_task(task_id)
        sm = self._get_sm(task_id)

        task.started_at = time.time()
        logger.info(f'[TaskEngine] Starting task {task_id}: {task.title}')

        try:
            self._run_pipeline(task, sm)
        except Exception as e:
            logger.error(f'[TaskEngine] Task {task_id} pipeline error: {e}')
            task.result.success = False
            task.result.error = f'{type(e).__name__}: {str(e)}'
            if not sm.is_terminal:
                try:
                    sm.transition_to(TaskPhase.FAILED, success=False, error=str(e))
                except TransitionError:
                    pass

        task.completed_at = time.time()
        task.result.duration_s = task.duration_s

        # Notify completion hooks
        for hook in self._on_task_completed:
            try:
                hook(task)
            except Exception as e:
                logger.warning(f'Task completed hook error: {e}')

        logger.info(
            f'[TaskEngine] Task {task_id} finished: '
            f'success={task.result.success}, '
            f'duration={task.duration_s:.2f}s, '
            f'retries={task.result.retry_count}, '
            f'artifacts={len(task.result.artifacts)}'
        )

        return task.result

    def _run_pipeline(self, task: Task, sm: TaskStateMachine) -> None:
        """Drive the task through the phase pipeline.

        The pipeline follows the state machine transitions. Each phase
        is executed by the TaskRunner, and the result determines the
        next phase.
        """
        # Phase sequence for the happy path
        happy_path = [
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

        while not sm.is_terminal and phase_idx < len(happy_path):
            current_phase = sm.current_phase
            target_phase = happy_path[phase_idx]

            # If we're already past this phase (e.g., after retry loop), advance
            if current_phase == target_phase:
                # Execute the current phase
                result = self._execute_phase(task, sm, current_phase)

                if not result.success:
                    # Phase failed — route to failure handling
                    self._handle_phase_failure(task, sm, current_phase, result)
                    if sm.is_terminal:
                        break
                    # After retry, we might be back at EXECUTE — find where we are
                    phase_idx = self._find_phase_index(
                        happy_path, sm.current_phase
                    )
                    continue

                # Phase succeeded — advance to next
                if phase_idx + 1 < len(happy_path):
                    next_phase = happy_path[phase_idx + 1]
                    try:
                        old_phase = sm.current_phase
                        sm.transition_to(next_phase, success=True)
                        self._notify_phase_change(task.task_id, old_phase, next_phase)
                    except TransitionError as e:
                        logger.error(f'Transition error: {e}')
                        break

                phase_idx += 1
            else:
                # We're at a different phase than expected — find it
                phase_idx = self._find_phase_index(happy_path, current_phase)
                if phase_idx < 0:
                    # Current phase not in happy path — we're in failure/retry
                    break

        # Mark final state
        if sm.current_phase == TaskPhase.COMPLETE:
            task.result.success = True
            task.result.message = 'Task completed successfully'
        elif not sm.is_terminal:
            # Shouldn't happen, but safety net
            try:
                sm.transition_to(TaskPhase.COMPLETE, success=True)
                task.result.success = True
            except TransitionError:
                task.result.success = False

    def _execute_phase(
        self, task: Task, sm: TaskStateMachine, phase: TaskPhase
    ) -> PhaseResult:
        """Execute a single phase with timeout protection."""
        start = time.time()

        # Wire in external integrations before running
        self._wire_integrations(task, phase)

        result = self._runner.run_phase(phase, task)

        duration = time.time() - start
        if duration > MAX_PHASE_DURATION_S:
            logger.warning(
                f'Phase {phase.value} exceeded time limit: {duration:.2f}s '
                f'(limit: {MAX_PHASE_DURATION_S}s)'
            )

        return result

    def _handle_phase_failure(
        self,
        task: Task,
        sm: TaskStateMachine,
        failed_phase: TaskPhase,
        result: PhaseResult,
    ) -> None:
        """Handle a phase failure — route to failure analysis and retry."""
        logger.warning(
            f'[TaskEngine] Phase {failed_phase.value} failed for task '
            f'{task.task_id}: {result.error}'
        )

        task.result.error = result.error

        # Can we go to failure analysis?
        if failed_phase in (TaskPhase.EXECUTE, TaskPhase.TEST):
            try:
                sm.transition_to(
                    TaskPhase.FAILURE_ANALYSIS,
                    success=False,
                    error=result.error,
                )
                self._notify_phase_change(
                    task.task_id, failed_phase, TaskPhase.FAILURE_ANALYSIS
                )

                # Run failure analysis
                fa_result = self._runner.run_phase(TaskPhase.FAILURE_ANALYSIS, task)

                if sm.can_retry():
                    sm.transition_to(TaskPhase.RETRY_OR_FIX, success=True)
                    self._notify_phase_change(
                        task.task_id,
                        TaskPhase.FAILURE_ANALYSIS,
                        TaskPhase.RETRY_OR_FIX,
                    )

                    # Run retry/fix
                    fix_result = self._runner.run_phase(TaskPhase.RETRY_OR_FIX, task)

                    # Route back to EXECUTE
                    target = (
                        fix_result.next_phase_hint
                        if fix_result.next_phase_hint
                        else TaskPhase.EXECUTE
                    )
                    sm.transition_to(target, success=True)
                    self._notify_phase_change(
                        task.task_id, TaskPhase.RETRY_OR_FIX, target
                    )
                else:
                    # Max retries exceeded
                    sm.transition_to(
                        TaskPhase.FAILED,
                        success=False,
                        error=f'Max retries ({sm.retry_count}) exceeded',
                    )
                    task.result.error_category = 'max_retries_exceeded'
            except TransitionError as e:
                logger.error(f'Failure handling transition error: {e}')
                try:
                    sm.transition_to(
                        TaskPhase.FAILED, success=False, error=str(e)
                    )
                except TransitionError:
                    pass
        else:
            # Non-retryable phase failure
            try:
                sm.transition_to(
                    TaskPhase.FAILED, success=False, error=result.error
                )
            except TransitionError:
                pass

    def _wire_integrations(self, task: Task, phase: TaskPhase) -> None:
        """Wire external integrations into the runner for a specific phase.

        This connects the execution engine to repo intelligence, memory,
        workflow engine, and agent roles.
        """
        if phase == TaskPhase.CONTEXT_BUILD and self._context_builder:
            self._runner.register_handler(
                TaskPhase.CONTEXT_BUILD,
                lambda t, ctx: self._run_context_builder(t),
            )
        if phase == TaskPhase.REPO_ANALYSIS and self._repo_analyzer:
            self._runner.register_handler(
                TaskPhase.REPO_ANALYSIS,
                lambda t, ctx: self._run_repo_analyzer(t, ctx),
            )
        if phase == TaskPhase.EXECUTE and self._executor:
            self._runner.register_handler(
                TaskPhase.EXECUTE,
                lambda t, ctx: self._executor(t, ctx),
            )
        if phase == TaskPhase.TEST and self._tester:
            self._runner.register_handler(
                TaskPhase.TEST,
                lambda t, ctx: self._tester(t, ctx),
            )
        if phase == TaskPhase.REVIEW and self._reviewer:
            self._runner.register_handler(
                TaskPhase.REVIEW,
                lambda t, ctx: self._reviewer(t, ctx),
            )

    def _run_context_builder(self, task: Task) -> PhaseResult:
        """Run the external context builder."""
        try:
            context = self._context_builder(task)  # type: ignore[misc]
            task.context = context
            return PhaseResult(success=True)
        except Exception as e:
            return PhaseResult(success=False, error=str(e))

    def _run_repo_analyzer(
        self, task: Task, context: TaskContext
    ) -> PhaseResult:
        """Run the external repo analyzer."""
        try:
            self._repo_analyzer(task, context)  # type: ignore[misc]
            return PhaseResult(
                success=True,
                metadata={
                    'file_count': len(context.file_map),
                    'dependency_count': len(context.dependency_graph),
                },
            )
        except Exception as e:
            return PhaseResult(success=False, error=str(e))

    # ── Integration Setters ─────────────────────────────────────────────

    def set_context_builder(
        self, builder: Callable[[Task], TaskContext]
    ) -> None:
        """Set the context builder integration."""
        self._context_builder = builder

    def set_repo_analyzer(
        self, analyzer: Callable[[Task, TaskContext], None]
    ) -> None:
        """Set the repo intelligence integration."""
        self._repo_analyzer = analyzer

    def set_planner(
        self, planner: Callable[[Task, TaskContext], list[dict[str, Any]]]
    ) -> None:
        """Set the planning integration."""
        self._planner = planner

    def set_executor(
        self, executor: Callable[[Task, TaskContext], PhaseResult]
    ) -> None:
        """Set the execution integration (coder agent role)."""
        self._executor = executor

    def set_tester(
        self, tester: Callable[[Task, TaskContext], PhaseResult]
    ) -> None:
        """Set the testing integration (tester agent role)."""
        self._tester = tester

    def set_reviewer(
        self, reviewer: Callable[[Task, TaskContext], PhaseResult]
    ) -> None:
        """Set the review integration (reviewer agent role)."""
        self._reviewer = reviewer

    # ── Event Hooks ─────────────────────────────────────────────────────

    def on_task_created(self, hook: Callable[[Task], None]) -> None:
        self._on_task_created.append(hook)

    def on_task_completed(self, hook: Callable[[Task], None]) -> None:
        self._on_task_completed.append(hook)

    def on_phase_change(
        self, hook: Callable[[str, TaskPhase, TaskPhase], None]
    ) -> None:
        self._on_phase_change.append(hook)

    # ── Query Methods ───────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def get_state_machine(self, task_id: str) -> TaskStateMachine | None:
        return self._state_machines.get(task_id)

    def list_tasks(
        self, status: str | None = None
    ) -> list[dict[str, Any]]:
        """List all tasks, optionally filtered by status."""
        result = []
        for task_id, task in self._tasks.items():
            sm = self._state_machines.get(task_id)
            if status and sm and sm.current_phase.value != status:
                continue
            result.append({
                'task_id': task_id,
                'title': task.title,
                'phase': sm.current_phase.value if sm else 'unknown',
                'is_terminal': sm.is_terminal if sm else False,
                'success': task.result.success,
                'duration_s': task.duration_s,
            })
        return result

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        sm = self._state_machines.get(task_id)
        if sm is None or sm.is_terminal:
            return False
        try:
            sm.transition_to(TaskPhase.CANCELLED, success=False, error='Cancelled by user')
            return True
        except TransitionError:
            return False

    def cleanup_task(self, task_id: str) -> bool:
        """Remove a completed task from memory."""
        if task_id in self._tasks:
            sm = self._state_machines.get(task_id)
            if sm and not sm.is_terminal:
                return False
            del self._tasks[task_id]
            self._state_machines.pop(task_id, None)
            return True
        return False

    # ── Internal Helpers ────────────────────────────────────────────────

    def _get_task(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f'Task {task_id} not found')
        return task

    def _get_sm(self, task_id: str) -> TaskStateMachine:
        sm = self._state_machines.get(task_id)
        if sm is None:
            raise ValueError(f'State machine for task {task_id} not found')
        return sm

    def _find_phase_index(
        self, phases: list[TaskPhase], target: TaskPhase
    ) -> int:
        """Find the index of a phase in the sequence."""
        for i, phase in enumerate(phases):
            if phase == target:
                return i
        return -1

    def _notify_phase_change(
        self, task_id: str, old_phase: TaskPhase, new_phase: TaskPhase
    ) -> None:
        """Notify phase change hooks."""
        for hook in self._on_phase_change:
            try:
                hook(task_id, old_phase, new_phase)
            except Exception as e:
                logger.warning(f'Phase change hook error: {e}')

    def stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        total = len(self._tasks)
        completed = sum(
            1
            for sm in self._state_machines.values()
            if sm.current_phase == TaskPhase.COMPLETE
        )
        failed = sum(
            1
            for sm in self._state_machines.values()
            if sm.current_phase == TaskPhase.FAILED
        )
        running = total - completed - failed

        return {
            'total_tasks': total,
            'completed': completed,
            'failed': failed,
            'running': running,
            'max_concurrent': MAX_CONCURRENT_TASKS,
        }
