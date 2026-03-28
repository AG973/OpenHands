"""Task Runner — executes individual phases of the task lifecycle.

Each phase has a dedicated handler that receives the Task and its context,
performs the phase work, and returns a PhaseResult. Handlers can be
overridden by registering custom callables for any phase.

Strengthened implementation:
- PLAN: generates real multi-step plans with file changes, commands, dependencies
- EXECUTE: runs plan steps individually with per-step tracking and tool control
- TEST: parses test results, classifies failures, extracts error types
- FAILURE_ANALYSIS: classifies errors (syntax/runtime/import/dep/test), searches
  memory for past fixes, selects retry strategy with confidence scoring
- ARTIFACT_GENERATION: produces code diffs, execution logs, test results, and
  structured summary bundles
- Memory integration: ErrorMemory, FixMemory, DecisionMemory injected into
  planning, failure analysis, and retry decisions
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from openhands.core.logger import openhands_logger as logger
from openhands.execution.task_models import (
    ArtifactType,
    ErrorCategory,
    FailureAnalysisResult,
    PlanStep,
    StepStatus,
    Task,
    TaskArtifact,
    TaskContext,
    TaskType,
    TestResult,
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

        # Memory subsystems (injected by EngineeringOS)
        self._error_memory: Any = None
        self._fix_memory: Any = None
        self._decision_memory: Any = None

        # Policy subsystems (injected by EngineeringOS)
        self._retry_policy: Any = None
        self._tool_selector: Any = None

        # Observability subsystems (injected by EngineeringOS)
        self._execution_trace: Any = None
        self._artifact_builder: Any = None

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

    # ── Memory / Policy / Observability setters ───────────────────────────

    def set_error_memory(self, mem: Any) -> None:
        """Inject ErrorMemory for failure analysis and planning."""
        self._error_memory = mem

    def set_fix_memory(self, mem: Any) -> None:
        """Inject FixMemory for retry strategy selection."""
        self._fix_memory = mem

    def set_decision_memory(self, mem: Any) -> None:
        """Inject DecisionMemory for approach selection."""
        self._decision_memory = mem

    def set_retry_policy(self, policy: Any) -> None:
        """Inject RetryPolicy for retry decisions."""
        self._retry_policy = policy

    def set_tool_selector(self, selector: Any) -> None:
        """Inject ToolSelector for per-step tool control."""
        self._tool_selector = selector

    def set_execution_trace(self, trace: Any) -> None:
        """Inject ExecutionTrace for observability."""
        self._execution_trace = trace

    def set_artifact_builder(self, builder: Any) -> None:
        """Inject ArtifactBuilder for artifact generation."""
        self._artifact_builder = builder

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
        """PLAN: Create multi-step execution plan from task + context.

        Generates a structured plan based on:
        1. Task type and description analysis
        2. Repo structure (file_map, dependency_graph) from context
        3. Past decision memory (what approaches worked/failed before)
        4. Available tools filtered by phase applicability

        Each step has: action, target_files, commands, dependencies,
        tools_allowed, and decision_reasoning.
        """
        if self._planner:
            try:
                plan_steps = self._planner(task)
                task.context.plan_steps = plan_steps
                # Convert raw dicts to PlanStep objects
                task.context.structured_plan = [
                    self._dict_to_plan_step(i, s) for i, s in enumerate(plan_steps)
                ]
                logger.info(
                    f'[TaskRunner] PLAN: generated {len(plan_steps)} steps (external planner)'
                )
                return PhaseResult(
                    phase=TaskPhase.PLAN,
                    success=True,
                    output={'plan_steps': plan_steps, 'source': 'external'},
                )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] PLAN integration failed: {exc}, '
                    f'falling back to intelligent default planner'
                )

        # ── Intelligent multi-step plan generation ────────────────────────
        steps: list[PlanStep] = []
        step_id = 0
        desc = task.description or task.title
        desc_lower = desc.lower()
        task_type = task.task_type

        # Step 1: Consult decision memory for best approach
        preferred_approach = ''
        if self._decision_memory:
            try:
                preferred_approach = self._decision_memory.get_best_approach(
                    decision_type=_import_decision_type('APPROACH'),
                    context_description=desc,
                ) or ''
            except Exception:
                pass

        # Step 2: Consult error memory to avoid known-bad approaches
        avoid_approaches: list[str] = []
        if self._error_memory:
            try:
                recurring = self._error_memory.get_recurring_errors(min_count=2)
                for err in recurring:
                    if err.fix_applied and not err.fix_successful:
                        avoid_approaches.append(err.fix_applied)
            except Exception:
                pass

        # Step 3: Select available tools for execute phase
        available_tools: list[str] = []
        if self._tool_selector:
            try:
                tool_specs = self._tool_selector.select_tools(phase='execute')
                available_tools = [t.name for t in tool_specs]
            except Exception:
                pass
        if not available_tools:
            available_tools = ['file_read', 'file_write', 'file_edit', 'shell_exec', 'search_code']

        # Step 4: Generate plan based on task type and context
        if task_type == TaskType.BUG_FIX:
            steps = self._generate_bug_fix_plan(
                task, step_id, desc, available_tools, preferred_approach, avoid_approaches
            )
        elif task_type == TaskType.FEATURE:
            steps = self._generate_feature_plan(
                task, step_id, desc, available_tools, preferred_approach, avoid_approaches
            )
        elif task_type == TaskType.REFACTOR:
            steps = self._generate_refactor_plan(
                task, step_id, desc, available_tools, preferred_approach, avoid_approaches
            )
        elif task_type == TaskType.TEST:
            steps = self._generate_test_plan(
                task, step_id, desc, available_tools, preferred_approach, avoid_approaches
            )
        else:
            steps = self._generate_generic_plan(
                task, step_id, desc, available_tools, preferred_approach, avoid_approaches
            )

        # Step 5: Record planning decision in decision memory
        if self._decision_memory:
            try:
                from openhands.memory.decision_memory import DecisionEntry, DecisionType
                self._decision_memory.record(DecisionEntry(
                    decision_type=DecisionType.APPROACH,
                    description=f'Plan for {task_type.value}: {desc[:100]}',
                    alternatives_considered=[task_type.value, 'generic'],
                    chosen_alternative=task_type.value,
                    reasoning=f'Task classified as {task_type.value}, '
                              f'generated {len(steps)} steps, '
                              f'preferred_approach={preferred_approach or "none"}',
                    task_id=task.task_id,
                    task_type=task_type.value,
                ))
            except Exception:
                pass

        # Store plan in context
        task.context.structured_plan = steps
        task.context.plan_steps = [s.to_dict() for s in steps]

        logger.info(
            f'[TaskRunner] PLAN: generated {len(steps)} steps for '
            f'{task_type.value} task (preferred_approach={preferred_approach or "none"}, '
            f'avoiding={len(avoid_approaches)} approaches)'
        )

        return PhaseResult(
            phase=TaskPhase.PLAN,
            success=True,
            output={
                'plan_steps': [s.to_dict() for s in steps],
                'step_count': len(steps),
                'task_type': task_type.value,
                'preferred_approach': preferred_approach,
                'avoid_approaches': avoid_approaches,
                'source': 'intelligent_default',
            },
        )

    def _handle_execute(self, task: Task) -> PhaseResult:
        """EXECUTE: Run plan steps individually with per-step tracking.

        Executes each PlanStep from the structured plan one by one:
        1. Validates step dependencies are met
        2. Selects tools allowed for this step via ToolSelector
        3. Runs the step (via executor integration or built-in handler)
        4. Records per-step result, timing, tools used
        5. Records decision in DecisionMemory
        6. On step failure: records error in ErrorMemory, stops execution

        If an executor integration is set, it receives the full task
        with the current step index for fine-grained control.
        """
        plan = task.context.structured_plan
        if not plan:
            # No structured plan — fall back to single-step execution
            if self._executor:
                try:
                    exec_result = self._executor(task)
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
                    )
            logger.info('[TaskRunner] EXECUTE: no plan and no executor, dry-run mode')
            return PhaseResult(
                phase=TaskPhase.EXECUTE,
                success=True,
                output={'mode': 'dry_run'},
            )

        # ── Step-by-step execution ────────────────────────────────────────
        step_results: list[dict[str, Any]] = []
        all_success = True
        failed_step: PlanStep | None = None

        for idx, step in enumerate(plan):
            task.context.current_step_index = idx
            step.status = StepStatus.RUNNING
            step.started_at = time.time()

            logger.info(
                f'[TaskRunner] EXECUTE step {step.step_id}/{len(plan)}: '
                f'{step.action} — {step.description[:80]}'
            )

            # Record in execution trace
            if self._execution_trace:
                try:
                    self._execution_trace.record_tool_call(
                        f'step_{step.step_id}_{step.action}',
                        {'description': step.description, 'files': step.target_files},
                    )
                except Exception:
                    pass

            # Validate dependencies
            dep_ok = self._check_step_dependencies(step, plan)
            if not dep_ok:
                step.status = StepStatus.SKIPPED
                step.error = 'Dependency step not completed'
                step.completed_at = time.time()
                step_results.append(step.to_dict())
                logger.warning(
                    f'[TaskRunner] EXECUTE step {step.step_id} skipped: deps not met'
                )
                continue

            # Select tools for this step
            if self._tool_selector and not step.tools_allowed:
                try:
                    tool_specs = self._tool_selector.select_tools(phase='execute')
                    step.tools_allowed = [t.name for t in tool_specs]
                except Exception:
                    pass

            # Execute the step
            try:
                step_output = self._execute_single_step(task, step)
                step.output = step_output
                step_success = step_output.get('success', True)

                if step_success:
                    step.status = StepStatus.COMPLETED
                    step.tools_used = step_output.get('tools_used', [])
                else:
                    step.status = StepStatus.FAILED
                    step.error = step_output.get('error', 'Step failed')
                    all_success = False
                    failed_step = step

            except Exception as exc:
                step.status = StepStatus.FAILED
                step.error = f'{type(exc).__name__}: {exc}'
                all_success = False
                failed_step = step

            step.completed_at = time.time()
            step_results.append(step.to_dict())

            # Record step result in execution trace
            if self._execution_trace:
                try:
                    self._execution_trace.record_tool_result(
                        f'step_{step.step_id}_{step.action}',
                        success=step.status == StepStatus.COMPLETED,
                        error=step.error,
                    )
                except Exception:
                    pass

            # Record in decision memory
            if self._decision_memory:
                try:
                    from openhands.memory.decision_memory import (
                        DecisionEntry,
                        DecisionOutcome,
                        DecisionType,
                    )
                    outcome = (
                        DecisionOutcome.SUCCESS
                        if step.status == StepStatus.COMPLETED
                        else DecisionOutcome.FAILURE
                    )
                    self._decision_memory.record(DecisionEntry(
                        decision_type=DecisionType.TOOL_CHOICE,
                        description=f'Execute step: {step.description[:80]}',
                        chosen_alternative=step.action,
                        outcome=outcome,
                        outcome_details=step.error or 'success',
                        task_id=task.task_id,
                    ))
                except Exception:
                    pass

            # On failure: record in error memory and stop
            if failed_step:
                if self._error_memory:
                    try:
                        from openhands.memory.error_memory import ErrorEntry
                        self._error_memory.record(ErrorEntry(
                            error_type=self._classify_error_string(step.error),
                            error_message=step.error[:500],
                            file_path=step.target_files[0] if step.target_files else '',
                            task_id=task.task_id,
                            phase='execute',
                        ))
                    except Exception:
                        pass

                logger.warning(
                    f'[TaskRunner] EXECUTE stopped at step {step.step_id}: {step.error[:200]}'
                )
                break

        # Store results in context
        task.context.step_results = step_results

        completed = sum(1 for s in plan if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in plan if s.status == StepStatus.FAILED)
        skipped = sum(1 for s in plan if s.status == StepStatus.SKIPPED)

        logger.info(
            f'[TaskRunner] EXECUTE: {completed} completed, {failed} failed, '
            f'{skipped} skipped out of {len(plan)} steps'
        )

        return PhaseResult(
            phase=TaskPhase.EXECUTE,
            success=all_success,
            output={
                'total_steps': len(plan),
                'completed': completed,
                'failed': failed,
                'skipped': skipped,
                'step_results': step_results,
                'failed_step': failed_step.to_dict() if failed_step else None,
            },
            error=failed_step.error if failed_step else '',
        )

    def _handle_test(self, task: Task) -> PhaseResult:
        """TEST: Run tests, parse results, classify failures, extract error types.

        Strengthened implementation:
        1. If tester integration set: delegates then parses output
        2. If no tester: attempts to discover and run tests from repo context
        3. Parses test output to extract: pass/fail counts, failure details,
           error type classification, affected files
        4. Stores structured TestResult in task.context.test_result
        5. Records failures in ErrorMemory for future reference
        """
        if not task.require_tests:
            logger.info('[TaskRunner] TEST: skipped (require_tests=False)')
            return PhaseResult(
                phase=TaskPhase.TEST,
                success=True,
                output={'skipped': True, 'reason': 'require_tests=False'},
            )

        raw_output = ''
        test_data: dict[str, Any] = {}

        if self._tester:
            try:
                test_data = self._tester(task)
                raw_output = str(test_data.get('output', ''))
            except Exception as exc:
                raw_output = str(exc)
                test_data = {'success': False, 'error': str(exc)}
        else:
            # Attempt to discover and run tests from repo context
            raw_output, test_data = self._discover_and_run_tests(task)

        # Parse test output into structured TestResult
        test_result = self._parse_test_output(raw_output, test_data)
        task.context.test_result = test_result

        # Record failures in error memory
        if not test_result.success and self._error_memory:
            for failure in test_result.failures:
                try:
                    from openhands.memory.error_memory import ErrorEntry
                    self._error_memory.record(ErrorEntry(
                        error_type='test_failure',
                        error_message=failure.get('error', '')[:500],
                        file_path=failure.get('file', ''),
                        line_number=failure.get('line', 0),
                        task_id=task.task_id,
                        phase='test',
                    ))
                except Exception:
                    pass

        # Build test artifact
        artifacts = []
        if raw_output:
            artifacts.append(TaskArtifact(
                artifact_type=ArtifactType.TEST_RESULT,
                name='test_output',
                content=raw_output[:10000],
            ))

        logger.info(
            f'[TaskRunner] TEST: total={test_result.total}, '
            f'passed={test_result.passed}, failed={test_result.failed}, '
            f'errors={test_result.errors}, '
            f'error_types={test_result.error_types}'
        )

        error_msg = ''
        if not test_result.success:
            error_msg = (
                f'{test_result.failed} test(s) failed, '
                f'{test_result.errors} error(s). '
                f'Types: {test_result.error_types}'
            )

        return PhaseResult(
            phase=TaskPhase.TEST,
            success=test_result.success,
            output=test_result.to_dict(),
            error=error_msg,
            artifacts=artifacts,
        )

    def _handle_failure_analysis(self, task: Task) -> PhaseResult:
        """FAILURE_ANALYSIS: Classify errors, search memory, select retry strategy.

        Strengthened implementation:
        1. Classify error into structured category (syntax, runtime, import,
           dependency, test_failure, type_error, permission, timeout, config, network)
        2. Extract stack trace, affected files, line numbers from error text
        3. Search ErrorMemory for similar past errors and their resolutions
        4. Search FixMemory for applicable fix strategies
        5. Consult RetryPolicy for retry decision
        6. Produce FailureAnalysisResult with confidence score
        7. Record analysis decision in DecisionMemory
        """
        last_error = task.result.error or ''

        if self._failure_analyzer:
            try:
                analysis = self._failure_analyzer(task)
                logger.info(
                    f'[TaskRunner] FAILURE_ANALYSIS: '
                    f'category={analysis.get("category", "unknown")} (external)'
                )
                return PhaseResult(
                    phase=TaskPhase.FAILURE_ANALYSIS,
                    success=True,
                    output=analysis,
                )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] FAILURE_ANALYSIS integration failed: {exc}, '
                    f'using intelligent default analyzer'
                )

        # ── Step 1: Classify error category ───────────────────────────────
        category = self._classify_error_to_category(last_error)
        confidence = self._compute_classification_confidence(last_error, category)

        # ── Step 2: Extract structured info from error ────────────────────
        stack_trace = self._extract_stack_trace(last_error)
        affected_files = self._extract_affected_files(last_error)

        # ── Step 3: Search ErrorMemory for similar past errors ────────────
        similar_errors: list[dict[str, Any]] = []
        if self._error_memory:
            try:
                similar = self._error_memory.find_similar(
                    error_type=category.value,
                    error_message=last_error[:200],
                )
                similar_errors = [e.to_dict() for e in similar]
                if similar:
                    logger.info(
                        f'[TaskRunner] FAILURE_ANALYSIS: found {len(similar)} '
                        f'similar past errors'
                    )
            except Exception:
                pass

        # ── Step 4: Search FixMemory for applicable fix strategies ────────
        suggested_fixes: list[dict[str, Any]] = []
        if self._fix_memory:
            try:
                fixes = self._fix_memory.get_fixes_for(
                    error_type=category.value,
                    error_message=last_error[:200],
                )
                suggested_fixes = [f.to_dict() for f in fixes]
                if fixes:
                    logger.info(
                        f'[TaskRunner] FAILURE_ANALYSIS: found {len(fixes)} '
                        f'applicable fix strategies'
                    )
            except Exception:
                pass

        # ── Step 5: Consult RetryPolicy ───────────────────────────────────
        retry_recommended = False
        retry_strategy = 'escalate'
        if self._retry_policy:
            try:
                decision = self._retry_policy.should_retry(
                    task_id=task.task_id,
                    error=last_error[:500],
                    error_type=category.value,
                    attempt=task.result.retry_count,
                )
                retry_recommended = decision.should_retry
                retry_strategy = decision.strategy.value
            except Exception:
                pass
        else:
            # Default retry logic
            retry_recommended = (
                task.result.retry_count < task.max_retries
                and category in (
                    ErrorCategory.RUNTIME_ERROR,
                    ErrorCategory.TEST_FAILURE,
                    ErrorCategory.TIMEOUT,
                    ErrorCategory.IMPORT_ERROR,
                    ErrorCategory.DEPENDENCY_ERROR,
                )
            )
            retry_strategy = (
                'same_approach' if task.result.retry_count == 0
                else 'different_approach'
            )

        # ── Step 6: Build FailureAnalysisResult ───────────────────────────
        analysis = FailureAnalysisResult(
            category=category,
            root_cause=self._infer_root_cause(last_error, category),
            original_error=last_error[:2000],
            stack_trace=stack_trace,
            affected_files=affected_files,
            similar_past_errors=similar_errors,
            suggested_fixes=suggested_fixes,
            retry_recommended=retry_recommended,
            retry_strategy=retry_strategy,
            confidence=confidence,
        )
        task.context.failure_analysis = analysis
        task.result.error_category = category.value

        # ── Step 7: Record in DecisionMemory ──────────────────────────────
        if self._decision_memory:
            try:
                from openhands.memory.decision_memory import DecisionEntry, DecisionType
                self._decision_memory.record(DecisionEntry(
                    decision_type=DecisionType.FIX_STRATEGY,
                    description=f'Failure analysis: {category.value} — {last_error[:80]}',
                    alternatives_considered=['retry', 'different_approach', 'escalate'],
                    chosen_alternative=retry_strategy,
                    reasoning=(
                        f'confidence={confidence:.2f}, '
                        f'similar_errors={len(similar_errors)}, '
                        f'suggested_fixes={len(suggested_fixes)}, '
                        f'retry_count={task.result.retry_count}'
                    ),
                    task_id=task.task_id,
                ))
            except Exception:
                pass

        # Record error in execution trace
        if self._execution_trace:
            try:
                self._execution_trace.record_error(
                    error=last_error[:500],
                    phase='failure_analysis',
                    recoverable=retry_recommended,
                )
            except Exception:
                pass

        logger.info(
            f'[TaskRunner] FAILURE_ANALYSIS: category={category.value}, '
            f'confidence={confidence:.2f}, retry={retry_recommended}, '
            f'strategy={retry_strategy}, '
            f'similar_errors={len(similar_errors)}, '
            f'suggested_fixes={len(suggested_fixes)}'
        )

        return PhaseResult(
            phase=TaskPhase.FAILURE_ANALYSIS,
            success=True,
            output=analysis.to_dict(),
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
        """ARTIFACT_GENERATION: Generate code diffs, execution logs, test results, summary.

        Strengthened implementation produces a full artifact bundle:
        1. Code diff: git diff of all changes made during execution
        2. Execution log: chronological log of all phase results and step outputs
        3. Test results: structured test result summary
        4. Failure analysis: if any failures occurred
        5. Summary: high-level task summary with key metrics
        6. Delegates to ArtifactBuilder if available for disk persistence
        """
        artifacts: list[TaskArtifact] = []

        # ── 1. Code diff artifact ─────────────────────────────────────────
        diff_content = self._generate_code_diff(task)
        if diff_content:
            artifacts.append(TaskArtifact(
                artifact_type=ArtifactType.CODE_DIFF,
                name='changes.diff',
                content=diff_content,
            ))

        # ── 2. Execution log artifact ─────────────────────────────────────
        exec_log = self._generate_execution_log(task)
        artifacts.append(TaskArtifact(
            artifact_type=ArtifactType.EXECUTION_LOG,
            name='execution_log.txt',
            content=exec_log,
        ))

        # ── 3. Execution trace (phase-by-phase results) ──────────────────
        trace_content = self._generate_execution_trace(task)
        artifacts.append(TaskArtifact(
            artifact_type=ArtifactType.EXECUTION_TRACE,
            name='execution_trace.json',
            content=trace_content,
        ))

        # ── 4. Test results artifact ──────────────────────────────────────
        if task.context.test_result:
            import json
            artifacts.append(TaskArtifact(
                artifact_type=ArtifactType.TEST_RESULT,
                name='test_results.json',
                content=json.dumps(task.context.test_result.to_dict(), indent=2),
            ))

        # ── 5. Failure analysis artifact ──────────────────────────────────
        if task.context.failure_analysis:
            import json
            artifacts.append(TaskArtifact(
                artifact_type=ArtifactType.ERROR_REPORT,
                name='failure_analysis.json',
                content=json.dumps(task.context.failure_analysis.to_dict(), indent=2),
            ))

        # ── 6. Summary artifact ───────────────────────────────────────────
        summary = self._generate_summary(task)
        artifacts.append(TaskArtifact(
            artifact_type=ArtifactType.SUMMARY,
            name='summary.md',
            content=summary,
        ))

        # ── 7. Delegate to ArtifactBuilder for disk persistence ───────────
        if self._artifact_builder:
            try:
                if diff_content:
                    self._artifact_builder.add_diff(diff_content)
                self._artifact_builder.add_log(exec_log)
                self._artifact_builder.add_execution_trace(
                    task.result.phase_results
                )
                if task.context.test_result:
                    self._artifact_builder.add_test_result(
                        task.context.test_result.to_dict()
                    )
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] ArtifactBuilder persistence failed: {exc}'
                )

        # ── 8. Delegate to external artifact_generator if set ─────────────
        if self._artifact_generator:
            try:
                generated = self._artifact_generator(task)
                artifacts.extend(generated)
            except Exception as exc:
                logger.warning(
                    f'[TaskRunner] ARTIFACT_GENERATION integration failed: {exc}'
                )
                artifacts.append(TaskArtifact(
                    artifact_type=ArtifactType.ERROR_REPORT,
                    name='artifact_generation_error',
                    content=str(exc),
                ))

        logger.info(
            f'[TaskRunner] ARTIFACT_GENERATION: {len(artifacts)} artifacts '
            f'(diff={bool(diff_content)}, test={task.context.test_result is not None}, '
            f'failure={task.context.failure_analysis is not None})'
        )

        return PhaseResult(
            phase=TaskPhase.ARTIFACT_GENERATION,
            success=True,
            output={
                'artifact_count': len(artifacts),
                'artifact_names': [a.name for a in artifacts],
            },
            artifacts=artifacts,
        )

    # ── Plan generation helpers ───────────────────────────────────────────

    @staticmethod
    def _dict_to_plan_step(idx: int, raw: dict[str, Any]) -> PlanStep:
        """Convert a raw dict from an external planner into a PlanStep."""
        return PlanStep(
            step_id=raw.get('step', idx),
            action=raw.get('action', 'execute'),
            description=raw.get('description', ''),
            target_files=raw.get('target_files', raw.get('files', [])),
            commands=raw.get('commands', []),
            dependencies=raw.get('dependencies', []),
            tools_allowed=raw.get('tools_allowed', []),
            decision_reasoning=raw.get('reasoning', ''),
        )

    def _generate_bug_fix_plan(
        self,
        task: Task,
        start_id: int,
        desc: str,
        tools: list[str],
        preferred: str,
        avoid: list[str],
    ) -> list[PlanStep]:
        """Generate a multi-step plan for bug fix tasks."""
        steps: list[PlanStep] = []
        sid = start_id

        # Step 1: Analyze the bug — read error context and related files
        steps.append(PlanStep(
            step_id=sid,
            action='analyze',
            description=f'Analyze bug: {desc[:120]}',
            tools_allowed=['file_read', 'search_code'],
            decision_reasoning='Bug fix starts with understanding the error context',
        ))
        sid += 1

        # Step 2: Locate affected files using repo structure
        target_files = self._infer_target_files(task)
        steps.append(PlanStep(
            step_id=sid,
            action='analyze',
            description='Locate affected files and trace error origin',
            target_files=target_files,
            tools_allowed=['file_read', 'search_code'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Need to find exactly which files contain the bug',
        ))
        sid += 1

        # Step 3: Implement the fix
        steps.append(PlanStep(
            step_id=sid,
            action='file_edit',
            description='Apply bug fix to affected files',
            target_files=target_files,
            tools_allowed=['file_edit', 'file_write'],
            dependencies=[str(sid - 1)],
            decision_reasoning=preferred or 'Direct fix based on error analysis',
        ))
        sid += 1

        # Step 4: Run relevant tests
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Run tests to verify the fix',
            commands=self._infer_test_commands(task),
            tools_allowed=['shell_exec', 'run_tests'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Verify fix does not break existing functionality',
        ))
        sid += 1

        # Step 5: Commit changes
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Commit the bug fix',
            commands=['git add -A', f'git commit -m {shlex.quote("fix: " + desc[:60])}'],
            tools_allowed=['shell_exec', 'git_commit'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Commit verified fix',
        ))

        return steps

    def _generate_feature_plan(
        self,
        task: Task,
        start_id: int,
        desc: str,
        tools: list[str],
        preferred: str,
        avoid: list[str],
    ) -> list[PlanStep]:
        """Generate a multi-step plan for feature implementation tasks."""
        steps: list[PlanStep] = []
        sid = start_id

        # Step 1: Understand existing code structure
        steps.append(PlanStep(
            step_id=sid,
            action='analyze',
            description=f'Analyze codebase for feature: {desc[:100]}',
            tools_allowed=['file_read', 'search_code'],
            decision_reasoning='Understand existing patterns before adding new code',
        ))
        sid += 1

        # Step 2: Create or modify files
        target_files = self._infer_target_files(task)
        steps.append(PlanStep(
            step_id=sid,
            action='file_edit',
            description='Implement the feature — create/modify files',
            target_files=target_files,
            tools_allowed=['file_write', 'file_edit'],
            dependencies=[str(sid - 1)],
            decision_reasoning=preferred or 'Implement based on existing patterns',
        ))
        sid += 1

        # Step 3: Install dependencies if needed
        dep_keywords = ['install', 'package', 'dependency', 'import', 'require']
        if any(kw in desc.lower() for kw in dep_keywords):
            steps.append(PlanStep(
                step_id=sid,
                action='install_dep',
                description='Install required dependencies',
                tools_allowed=['shell_exec'],
                dependencies=[str(sid - 1)],
                decision_reasoning='Feature requires new dependencies',
            ))
            sid += 1

        # Step 4: Run tests
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Run tests to verify feature works',
            commands=self._infer_test_commands(task),
            tools_allowed=['shell_exec', 'run_tests'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Verify feature integrates without breaking existing code',
        ))
        sid += 1

        # Step 5: Commit
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Commit feature implementation',
            commands=['git add -A', f'git commit -m {shlex.quote("feat: " + desc[:60])}'],
            tools_allowed=['shell_exec', 'git_commit'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Commit verified feature',
        ))

        return steps

    def _generate_refactor_plan(
        self,
        task: Task,
        start_id: int,
        desc: str,
        tools: list[str],
        preferred: str,
        avoid: list[str],
    ) -> list[PlanStep]:
        """Generate a multi-step plan for refactoring tasks."""
        steps: list[PlanStep] = []
        sid = start_id

        # Step 1: Map files to refactor
        steps.append(PlanStep(
            step_id=sid,
            action='analyze',
            description=f'Map files and dependencies for refactor: {desc[:80]}',
            tools_allowed=['file_read', 'search_code'],
            decision_reasoning='Refactoring requires full impact analysis first',
        ))
        sid += 1

        # Step 2: Run tests before refactor (baseline)
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Run tests before refactor to establish baseline',
            commands=self._infer_test_commands(task),
            tools_allowed=['shell_exec', 'run_tests'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Establish passing baseline before changes',
        ))
        sid += 1

        # Step 3: Apply refactoring changes
        target_files = self._infer_target_files(task)
        steps.append(PlanStep(
            step_id=sid,
            action='file_edit',
            description='Apply refactoring changes',
            target_files=target_files,
            tools_allowed=['file_edit', 'file_write'],
            dependencies=[str(sid - 1)],
            decision_reasoning=preferred or 'Apply targeted refactoring',
        ))
        sid += 1

        # Step 4: Run tests after refactor
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Run tests after refactor to verify no regressions',
            commands=self._infer_test_commands(task),
            tools_allowed=['shell_exec', 'run_tests'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Verify refactoring preserves behavior',
        ))
        sid += 1

        # Step 5: Commit
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Commit refactoring',
            commands=['git add -A', f'git commit -m {shlex.quote("refactor: " + desc[:60])}'],
            tools_allowed=['shell_exec', 'git_commit'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Commit verified refactor with no regressions',
        ))

        return steps

    def _generate_test_plan(
        self,
        task: Task,
        start_id: int,
        desc: str,
        tools: list[str],
        preferred: str,
        avoid: list[str],
    ) -> list[PlanStep]:
        """Generate a multi-step plan for test-related tasks."""
        steps: list[PlanStep] = []
        sid = start_id

        # Step 1: Analyze what needs testing
        steps.append(PlanStep(
            step_id=sid,
            action='analyze',
            description=f'Analyze testing needs: {desc[:100]}',
            tools_allowed=['file_read', 'search_code'],
            decision_reasoning='Identify modules and functions needing tests',
        ))
        sid += 1

        # Step 2: Write test files
        steps.append(PlanStep(
            step_id=sid,
            action='create_file',
            description='Write test files',
            tools_allowed=['file_write'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Create tests based on analysis',
        ))
        sid += 1

        # Step 3: Run new tests
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Run newly created tests',
            commands=self._infer_test_commands(task),
            tools_allowed=['shell_exec', 'run_tests'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Verify tests pass and provide coverage',
        ))
        sid += 1

        # Step 4: Commit
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Commit new tests',
            commands=['git add -A', f'git commit -m {shlex.quote("test: " + desc[:60])}'],
            tools_allowed=['shell_exec', 'git_commit'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Commit passing tests',
        ))

        return steps

    def _generate_generic_plan(
        self,
        task: Task,
        start_id: int,
        desc: str,
        tools: list[str],
        preferred: str,
        avoid: list[str],
    ) -> list[PlanStep]:
        """Generate a multi-step plan for generic/custom tasks."""
        steps: list[PlanStep] = []
        sid = start_id

        # Step 1: Analyze
        steps.append(PlanStep(
            step_id=sid,
            action='analyze',
            description=f'Analyze task: {desc[:120]}',
            tools_allowed=['file_read', 'search_code'],
            decision_reasoning='Understand the task before execution',
        ))
        sid += 1

        # Step 2: Execute main work
        target_files = self._infer_target_files(task)
        steps.append(PlanStep(
            step_id=sid,
            action='file_edit',
            description=f'Execute: {desc[:100]}',
            target_files=target_files,
            tools_allowed=tools,
            dependencies=[str(sid - 1)],
            decision_reasoning=preferred or 'Execute based on analysis',
        ))
        sid += 1

        # Step 3: Verify
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Verify changes work correctly',
            commands=self._infer_test_commands(task),
            tools_allowed=['shell_exec', 'run_tests'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Verify execution results',
        ))
        sid += 1

        # Step 4: Commit
        steps.append(PlanStep(
            step_id=sid,
            action='shell_command',
            description='Commit changes',
            commands=['git add -A', f'git commit -m {shlex.quote("chore: " + desc[:60])}'],
            tools_allowed=['shell_exec', 'git_commit'],
            dependencies=[str(sid - 1)],
            decision_reasoning='Commit verified work',
        ))

        return steps

    def _infer_target_files(self, task: Task) -> list[str]:
        """Infer target files from task context and description."""
        files: list[str] = []

        # From repo analysis impact files
        if task.context.impact_files:
            files.extend(task.context.impact_files[:5])

        # Extract file paths from description
        if task.description:
            path_pattern = re.compile(r'[\w/]+\.(?:py|ts|tsx|js|jsx|rs|go|java|rb|yaml|yml|json|md)')
            matches = path_pattern.findall(task.description)
            for m in matches:
                if m not in files:
                    files.append(m)

        return files[:10]  # Cap at 10

    @staticmethod
    def _infer_test_commands(task: Task) -> list[str]:
        """Infer test commands from repo context."""
        # Check for known test runners in file_map
        commands: list[str] = []
        file_map = task.context.file_map

        if 'pyproject.toml' in file_map or 'setup.py' in file_map:
            commands.append('python -m pytest --tb=short -q')
        elif 'package.json' in file_map:
            commands.append('npm test')
        elif 'Cargo.toml' in file_map:
            commands.append('cargo test')
        elif 'go.mod' in file_map:
            commands.append('go test ./...')

        if not commands:
            # Fallback: check repo path for hints
            repo_path = task.context.repo_path
            if repo_path:
                if os.path.exists(os.path.join(repo_path, 'pyproject.toml')):
                    commands.append('python -m pytest --tb=short -q')
                elif os.path.exists(os.path.join(repo_path, 'package.json')):
                    commands.append('npm test')

        return commands or ['echo "No test runner detected"']

    # ── Execute phase helpers ─────────────────────────────────────────────

    @staticmethod
    def _check_step_dependencies(step: PlanStep, plan: list[PlanStep]) -> bool:
        """Check that all dependency steps are completed."""
        if not step.dependencies:
            return True
        for dep_id in step.dependencies:
            for other in plan:
                if str(other.step_id) == str(dep_id):
                    if other.status not in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                        return False
        return True

    def _execute_single_step(
        self, task: Task, step: PlanStep
    ) -> dict[str, Any]:
        """Execute a single plan step.

        If an executor integration is set, delegates to it with the current
        step context. Otherwise, provides built-in handling for known actions.
        """
        if self._executor:
            # Pass step info to executor
            task.metadata['current_step'] = step.to_dict()
            result = self._executor(task)
            task.metadata.pop('current_step', None)
            return result

        # Built-in step execution for known action types
        action = step.action
        tools_used: list[str] = []

        if action == 'analyze':
            # Analysis step — succeeds with info about what was analyzed
            tools_used = ['file_read', 'search_code']
            return {
                'success': True,
                'tools_used': tools_used,
                'output': f'Analyzed: {step.description}',
                'files_read': step.target_files,
            }

        elif action == 'shell_command':
            # Execute shell commands
            tools_used = ['shell_exec']
            outputs: list[str] = []
            for cmd in step.commands:
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        cwd=task.context.repo_path or None,
                    )
                    outputs.append(result.stdout[-2000:] if result.stdout else '')
                    if result.returncode != 0 and result.stderr:
                        return {
                            'success': False,
                            'tools_used': tools_used,
                            'error': result.stderr[-2000:],
                            'output': '\n'.join(outputs),
                        }
                except subprocess.TimeoutExpired:
                    return {
                        'success': False,
                        'tools_used': tools_used,
                        'error': f'Command timed out: {cmd}',
                    }
                except Exception as exc:
                    return {
                        'success': False,
                        'tools_used': tools_used,
                        'error': str(exc),
                    }
            return {
                'success': True,
                'tools_used': tools_used,
                'output': '\n'.join(outputs),
            }

        elif action in ('file_edit', 'file_write', 'create_file'):
            # File operations — in dry-run mode, just record intent
            tools_used = ['file_edit' if action == 'file_edit' else 'file_write']
            return {
                'success': True,
                'tools_used': tools_used,
                'output': f'File operation: {action} on {step.target_files}',
                'mode': 'dry_run' if not self._executor else 'live',
            }

        elif action == 'install_dep':
            tools_used = ['shell_exec']
            return {
                'success': True,
                'tools_used': tools_used,
                'output': 'Dependency installation step (delegated to executor)',
            }

        else:
            # Unknown action — succeed but flag it
            return {
                'success': True,
                'tools_used': [],
                'output': f'Unknown action type: {action}, treated as no-op',
            }

    # ── Test phase helpers ────────────────────────────────────────────────

    @staticmethod
    def _discover_and_run_tests(task: Task) -> tuple[str, dict[str, Any]]:
        """Attempt to discover and run tests from repo context."""
        repo_path = task.context.repo_path
        if not repo_path or not os.path.isdir(repo_path):
            return '', {'success': True, 'skipped': True, 'reason': 'no_repo_path'}

        # Try common test runners
        test_cmds = [
            ('python -m pytest --tb=short -q', ['pyproject.toml', 'setup.py', 'setup.cfg']),
            ('npm test', ['package.json']),
            ('cargo test', ['Cargo.toml']),
            ('go test ./...', ['go.mod']),
        ]

        for cmd, markers in test_cmds:
            for marker in markers:
                if os.path.exists(os.path.join(repo_path, marker)):
                    try:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=300,
                            cwd=repo_path,
                        )
                        output = (result.stdout or '') + '\n' + (result.stderr or '')
                        return output, {
                            'success': result.returncode == 0,
                            'command': cmd,
                            'returncode': result.returncode,
                            'output': output[-5000:],
                        }
                    except subprocess.TimeoutExpired:
                        return 'Test execution timed out', {
                            'success': False,
                            'error': 'timeout',
                            'command': cmd,
                        }
                    except Exception as exc:
                        return str(exc), {
                            'success': False,
                            'error': str(exc),
                            'command': cmd,
                        }

        return '', {'success': True, 'skipped': True, 'reason': 'no_test_runner_found'}

    @staticmethod
    def _parse_test_output(raw_output: str, test_data: dict[str, Any]) -> TestResult:
        """Parse test output into a structured TestResult.

        Handles pytest, jest/npm, cargo test, and go test output formats.
        Extracts pass/fail counts, failure details, and error classifications.
        """
        result = TestResult(test_output=raw_output[:10000])

        # If test_data already has structured results, use those
        if test_data.get('skipped'):
            return result

        # Try to extract counts from data first
        result.passed = test_data.get('passed', 0)
        result.failed = test_data.get('failed', 0)
        result.errors = test_data.get('errors', 0)
        result.total = test_data.get('total', 0)

        if not raw_output:
            result.total = result.passed + result.failed + result.errors
            return result

        # ── Parse pytest output ──
        # "5 passed, 2 failed, 1 error in 3.45s"
        pytest_summary = re.search(
            r'(\d+)\s+passed(?:,\s*(\d+)\s+failed)?(?:,\s*(\d+)\s+error)?'
            r'(?:,\s*(\d+)\s+skipped)?.*?in\s+([\d.]+)s',
            raw_output,
        )
        if pytest_summary:
            result.passed = int(pytest_summary.group(1))
            result.failed = int(pytest_summary.group(2) or 0)
            result.errors = int(pytest_summary.group(3) or 0)
            result.skipped = int(pytest_summary.group(4) or 0)
            result.duration_s = float(pytest_summary.group(5))
            result.total = result.passed + result.failed + result.errors + result.skipped

        # ── Parse pytest FAILED lines ──
        # "FAILED tests/test_foo.py::test_bar - AssertionError: ..."
        failed_pattern = re.compile(
            r'FAILED\s+([\w/.\-:]+)\s*-\s*(.*?)$', re.MULTILINE
        )
        for match in failed_pattern.finditer(raw_output):
            test_name = match.group(1)
            error_msg = match.group(2).strip()
            file_path = test_name.split('::')[0] if '::' in test_name else ''
            result.failures.append({
                'test_name': test_name,
                'error': error_msg[:300],
                'file': file_path,
                'line': 0,
            })
            # Classify error type
            error_type = _classify_test_error(error_msg)
            result.error_types[error_type] = result.error_types.get(error_type, 0) + 1

        # ── Parse jest/npm output ──
        # "Tests: 2 failed, 5 passed, 7 total"
        jest_summary = re.search(
            r'Tests:\s*(\d+)\s+failed,\s*(\d+)\s+passed,\s*(\d+)\s+total',
            raw_output,
        )
        if jest_summary and not pytest_summary:
            result.failed = int(jest_summary.group(1))
            result.passed = int(jest_summary.group(2))
            result.total = int(jest_summary.group(3))

        # ── Parse go test output ──
        # "ok  	pkg/foo	0.123s"  /  "FAIL	pkg/bar	0.456s"
        go_ok = len(re.findall(r'^ok\s+', raw_output, re.MULTILINE))
        go_fail = len(re.findall(r'^FAIL\s+', raw_output, re.MULTILINE))
        if (go_ok or go_fail) and not pytest_summary and not jest_summary:
            result.passed = go_ok
            result.failed = go_fail
            result.total = go_ok + go_fail

        # ── Parse cargo test output ──
        # "test result: ok. 5 passed; 0 failed; 0 ignored"
        cargo_summary = re.search(
            r'test result:.*?(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored',
            raw_output,
        )
        if cargo_summary:
            result.passed = int(cargo_summary.group(1))
            result.failed = int(cargo_summary.group(2))
            result.skipped = int(cargo_summary.group(3))
            result.total = result.passed + result.failed + result.skipped

        # Ensure total is at least sum of parts
        if result.total == 0:
            result.total = result.passed + result.failed + result.errors + result.skipped

        # Extract coverage if present
        coverage_match = re.search(r'(\d+(?:\.\d+)?)%\s*(?:coverage|cov)', raw_output, re.IGNORECASE)
        if coverage_match:
            result.coverage_percent = float(coverage_match.group(1))

        return result

    # ── Failure analysis helpers ──────────────────────────────────────────

    @staticmethod
    def _classify_error_string(error: str) -> str:
        """Quick error type classification from error string."""
        if not error:
            return 'unknown'
        lower = error.lower()
        if 'syntaxerror' in lower or 'syntax error' in lower:
            return 'syntax_error'
        if 'importerror' in lower or 'modulenotfounderror' in lower:
            return 'import_error'
        if 'typeerror' in lower:
            return 'type_error'
        if 'assertionerror' in lower or 'test' in lower and 'fail' in lower:
            return 'test_failure'
        if 'permissionerror' in lower or 'permission denied' in lower:
            return 'permission_error'
        if 'timeout' in lower:
            return 'timeout'
        if 'connectionerror' in lower or 'network' in lower:
            return 'network_error'
        if any(w in lower for w in ['dependency', 'package', 'install', 'pip', 'npm']):
            return 'dependency_error'
        if 'filenotfounderror' in lower or 'config' in lower:
            return 'configuration_error'
        return 'runtime_error'

    @staticmethod
    def _classify_error_to_category(error: str) -> ErrorCategory:
        """Classify error into structured ErrorCategory enum."""
        if not error:
            return ErrorCategory.UNKNOWN
        lower = error.lower()

        # Exact exception type matching (highest confidence)
        patterns: list[tuple[str, ErrorCategory]] = [
            ('syntaxerror', ErrorCategory.SYNTAX_ERROR),
            ('indentationerror', ErrorCategory.SYNTAX_ERROR),
            ('importerror', ErrorCategory.IMPORT_ERROR),
            ('modulenotfounderror', ErrorCategory.IMPORT_ERROR),
            ('typeerror', ErrorCategory.TYPE_ERROR),
            ('attributeerror', ErrorCategory.TYPE_ERROR),
            ('assertionerror', ErrorCategory.TEST_FAILURE),
            ('permissionerror', ErrorCategory.PERMISSION_ERROR),
            ('permission denied', ErrorCategory.PERMISSION_ERROR),
            ('timeouterror', ErrorCategory.TIMEOUT),
            ('timeout expired', ErrorCategory.TIMEOUT),
            ('connectionerror', ErrorCategory.NETWORK_ERROR),
            ('connectionrefusederror', ErrorCategory.NETWORK_ERROR),
            ('urlerror', ErrorCategory.NETWORK_ERROR),
        ]
        for pattern, cat in patterns:
            if pattern in lower:
                return cat

        # Keyword-based matching (lower confidence)
        if any(w in lower for w in ['syntax', 'parse error', 'unexpected token']):
            return ErrorCategory.SYNTAX_ERROR
        if any(w in lower for w in ['import', 'module', 'no module named']):
            return ErrorCategory.IMPORT_ERROR
        if any(w in lower for w in ['type error', 'not callable', 'not subscriptable']):
            return ErrorCategory.TYPE_ERROR
        if any(w in lower for w in ['assert', 'test fail', 'expected', 'failed']):
            if 'test' in lower:
                return ErrorCategory.TEST_FAILURE
        if any(w in lower for w in ['install', 'dependency', 'package', 'pip', 'npm', 'poetry']):
            return ErrorCategory.DEPENDENCY_ERROR
        if any(w in lower for w in ['timeout', 'timed out']):
            return ErrorCategory.TIMEOUT
        if any(w in lower for w in ['permission', 'access denied', 'forbidden']):
            return ErrorCategory.PERMISSION_ERROR
        if any(w in lower for w in ['config', 'configuration', 'setting', 'env var']):
            return ErrorCategory.CONFIGURATION_ERROR
        if any(w in lower for w in ['network', 'connection', 'dns', 'socket']):
            return ErrorCategory.NETWORK_ERROR

        return ErrorCategory.RUNTIME_ERROR

    @staticmethod
    def _compute_classification_confidence(error: str, category: ErrorCategory) -> float:
        """Compute confidence score for the error classification."""
        if not error:
            return 0.0
        lower = error.lower()

        # Exact exception name gives highest confidence
        exception_names = {
            ErrorCategory.SYNTAX_ERROR: ['syntaxerror', 'indentationerror'],
            ErrorCategory.IMPORT_ERROR: ['importerror', 'modulenotfounderror'],
            ErrorCategory.TYPE_ERROR: ['typeerror', 'attributeerror'],
            ErrorCategory.TEST_FAILURE: ['assertionerror'],
            ErrorCategory.PERMISSION_ERROR: ['permissionerror'],
            ErrorCategory.TIMEOUT: ['timeouterror', 'timeoutexpired'],
            ErrorCategory.NETWORK_ERROR: ['connectionerror', 'connectionrefusederror'],
        }
        for cat, names in exception_names.items():
            if cat == category:
                for name in names:
                    if name in lower:
                        return 0.95
                break

        # Keyword match gives medium confidence
        if category != ErrorCategory.UNKNOWN:
            return 0.7

        return 0.3

    @staticmethod
    def _extract_stack_trace(error: str) -> str:
        """Extract stack trace from error text."""
        if not error:
            return ''
        # Look for Python traceback
        tb_match = re.search(
            r'(Traceback \(most recent call last\):.*?)(?:\n\n|\Z)',
            error,
            re.DOTALL,
        )
        if tb_match:
            return tb_match.group(1)[:3000]
        # Look for Node.js stack trace
        node_match = re.search(r'((?:    at .+\n)+)', error)
        if node_match:
            return node_match.group(1)[:3000]
        return ''

    @staticmethod
    def _extract_affected_files(error: str) -> list[str]:
        """Extract file paths mentioned in error text."""
        if not error:
            return []
        # Match file paths with line numbers
        pattern = re.compile(r'["\']?([\w/.\-]+\.(?:py|ts|tsx|js|jsx|rs|go|java|rb))["\']?(?::(\d+))?')
        files: list[str] = []
        for match in pattern.finditer(error):
            f = match.group(1)
            if f not in files and not f.startswith('http'):
                files.append(f)
        return files[:10]

    @staticmethod
    def _infer_root_cause(error: str, category: ErrorCategory) -> str:
        """Infer a human-readable root cause from the error and category."""
        if not error:
            return 'Unknown error'

        root_causes = {
            ErrorCategory.SYNTAX_ERROR: 'Code has a syntax error — invalid Python/JS/etc syntax',
            ErrorCategory.IMPORT_ERROR: 'Missing module or package — needs installation or path fix',
            ErrorCategory.TYPE_ERROR: 'Type mismatch — wrong argument type or missing attribute',
            ErrorCategory.TEST_FAILURE: 'Test assertion failed — expected value does not match actual',
            ErrorCategory.DEPENDENCY_ERROR: 'Missing or incompatible dependency — needs install/update',
            ErrorCategory.PERMISSION_ERROR: 'Insufficient permissions — file/network access denied',
            ErrorCategory.TIMEOUT: 'Operation timed out — process took too long',
            ErrorCategory.CONFIGURATION_ERROR: 'Configuration issue — missing or invalid settings',
            ErrorCategory.NETWORK_ERROR: 'Network connectivity issue — cannot reach remote service',
            ErrorCategory.RUNTIME_ERROR: 'Runtime error during execution',
            ErrorCategory.UNKNOWN: 'Unclassified error — needs manual investigation',
        }
        base = root_causes.get(category, 'Unknown error type')

        # Try to extract the specific error message
        # Python: "ErrorType: message"
        specific = re.search(r'(?:Error|Exception):\s*(.+?)(?:\n|$)', error)
        if specific:
            return f'{base}: {specific.group(1)[:150]}'
        return base

    # ── Artifact generation helpers ───────────────────────────────────────

    @staticmethod
    def _generate_code_diff(task: Task) -> str:
        """Generate git diff of all changes made during execution."""
        repo_path = task.context.repo_path
        if not repo_path or not os.path.isdir(os.path.join(repo_path, '.git')):
            return ''
        try:
            base = task.context.base_branch or 'main'
            result = subprocess.run(
                ['git', 'diff', base, '--stat'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=repo_path,
            )
            stat_output = result.stdout or ''

            result2 = subprocess.run(
                ['git', 'diff', base],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=repo_path,
            )
            full_diff = result2.stdout or ''

            return f'# Diff Summary\n{stat_output}\n\n# Full Diff\n{full_diff[:50000]}'
        except Exception:
            return ''

    @staticmethod
    def _generate_execution_log(task: Task) -> str:
        """Generate a chronological execution log."""
        lines: list[str] = []
        lines.append(f'# Execution Log: {task.task_id}')
        lines.append(f'Task: {task.title}')
        lines.append(f'Type: {task.task_type.value}')
        lines.append(f'Duration: {task.duration_s:.2f}s')
        lines.append(f'Retries: {task.result.retry_count}/{task.max_retries}')
        lines.append('')

        # Phase results
        lines.append('## Phase Results')
        for phase_name, phase_data in task.result.phase_results.items():
            status = 'OK' if phase_data.get('success') else 'FAIL'
            detail = phase_data.get('detail', '')[:100]
            lines.append(f'  [{status}] {phase_name}: {detail}')
        lines.append('')

        # Step results
        if task.context.step_results:
            lines.append('## Step-by-Step Execution')
            for step_data in task.context.step_results:
                status = step_data.get('status', 'unknown')
                desc = step_data.get('description', '')[:100]
                duration = step_data.get('duration_s', 0)
                tools = step_data.get('tools_used', [])
                error = step_data.get('error', '')
                lines.append(
                    f'  Step {step_data.get("step_id", "?")}: [{status}] '
                    f'{desc} ({duration:.2f}s) tools={tools}'
                )
                if error:
                    lines.append(f'    ERROR: {error[:200]}')
            lines.append('')

        # Test results
        if task.context.test_result:
            tr = task.context.test_result
            lines.append('## Test Results')
            lines.append(
                f'  Total: {tr.total}, Passed: {tr.passed}, '
                f'Failed: {tr.failed}, Errors: {tr.errors}'
            )
            if tr.failures:
                lines.append('  Failures:')
                for f in tr.failures[:5]:
                    lines.append(f'    - {f.get("test_name", "?")}: {f.get("error", "")[:100]}')
            lines.append('')

        # Failure analysis
        if task.context.failure_analysis:
            fa = task.context.failure_analysis
            lines.append('## Failure Analysis')
            lines.append(f'  Category: {fa.category.value}')
            lines.append(f'  Root cause: {fa.root_cause}')
            lines.append(f'  Retry recommended: {fa.retry_recommended}')
            lines.append(f'  Strategy: {fa.retry_strategy}')
            lines.append(f'  Confidence: {fa.confidence:.2f}')
            lines.append('')

        return '\n'.join(lines)

    @staticmethod
    def _generate_execution_trace(task: Task) -> str:
        """Generate JSON execution trace from phase results."""
        import json
        trace = {
            'task_id': task.task_id,
            'title': task.title,
            'task_type': task.task_type.value,
            'duration_s': task.duration_s,
            'success': task.result.success,
            'retry_count': task.result.retry_count,
            'phase_results': task.result.phase_results,
            'step_results': task.context.step_results,
        }
        return json.dumps(trace, indent=2, default=str)

    @staticmethod
    def _generate_summary(task: Task) -> str:
        """Generate a high-level markdown summary of the task execution."""
        lines: list[str] = []
        status = 'SUCCESS' if task.result.success else 'FAILED'

        lines.append(f'# Task Summary: {task.title}')
        lines.append(f'**Status:** {status}')
        lines.append(f'**Type:** {task.task_type.value}')
        lines.append(f'**Duration:** {task.duration_s:.2f}s')
        lines.append(f'**Retries:** {task.result.retry_count}/{task.max_retries}')
        lines.append('')

        # Plan summary
        plan = task.context.structured_plan
        if plan:
            lines.append(f'## Plan ({len(plan)} steps)')
            for step in plan:
                icon = {
                    StepStatus.COMPLETED: '[DONE]',
                    StepStatus.FAILED: '[FAIL]',
                    StepStatus.SKIPPED: '[SKIP]',
                    StepStatus.RUNNING: '[....]',
                    StepStatus.PENDING: '[    ]',
                }.get(step.status, '[    ]')
                lines.append(f'  {icon} Step {step.step_id}: {step.description[:80]}')
            lines.append('')

        # Test summary
        if task.context.test_result:
            tr = task.context.test_result
            lines.append(f'## Tests: {tr.passed}/{tr.total} passed')
            if tr.error_types:
                lines.append(f'  Error types: {tr.error_types}')
            lines.append('')

        # Failure summary
        if task.context.failure_analysis:
            fa = task.context.failure_analysis
            lines.append(f'## Failure: {fa.category.value}')
            lines.append(f'  {fa.root_cause}')
            lines.append(f'  Strategy: {fa.retry_strategy}')
            lines.append('')

        # Artifact count
        artifact_count = len(task.result.artifacts)
        lines.append(f'## Artifacts: {artifact_count} generated')
        for art in task.result.artifacts[:5]:
            lines.append(f'  - {art.name} ({art.artifact_type.value})')
        lines.append('')

        if task.result.error:
            lines.append(f'## Error')
            lines.append(f'```\n{task.result.error[:500]}\n```')

        return '\n'.join(lines)


# ── Module-level helpers ──────────────────────────────────────────────────────


def _classify_test_error(error_msg: str) -> str:
    """Classify a test error message into an error type."""
    lower = error_msg.lower()
    if 'assertionerror' in lower or 'assert' in lower:
        return 'assertion_error'
    if 'typeerror' in lower:
        return 'type_error'
    if 'attributeerror' in lower:
        return 'attribute_error'
    if 'importerror' in lower or 'modulenotfound' in lower:
        return 'import_error'
    if 'timeout' in lower:
        return 'timeout'
    if 'valueerror' in lower:
        return 'value_error'
    return 'unknown'


def _import_decision_type(name: str) -> Any:
    """Import DecisionType enum value by name."""
    try:
        from openhands.memory.decision_memory import DecisionType
        return getattr(DecisionType, name)
    except Exception:
        return name
