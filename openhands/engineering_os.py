"""Engineering OS — the CANONICAL runtime entry point for OpenHands.

This is the single source of truth for task execution. ALL execution paths
(CLI, server, programmatic) route through EngineeringOS.

Architecture:
    EngineeringOS (canonical entry point)
    └── TaskEngine (phase orchestration)
        └── TaskRunner (phase execution)
            ├── Memory subsystems (ErrorMemory, FixMemory, DecisionMemory)
            ├── Policy subsystems (RetryPolicy, ToolSelector)
            ├── Observability (ExecutionTrace, ArtifactBuilder)
            ├── Plugin lifecycle (HookRunner)
            └── AgentController (EXECUTE phase backend — the actual LLM agent loop)

Flow:
    1. EngineeringOS.run_task() → synchronous task execution through phases
    2. EngineeringOS.run_controller_async() → async execution wrapping AgentController
       Pre-phases: INTAKE → CONTEXT_BUILD → REPO_ANALYSIS → PLAN
       Execution:  AgentController step loop (the actual LLM agent)
       Post-phases: TEST → REVIEW → ARTIFACT_GENERATION → COMPLETE

All subsystems are MANDATORY — if any fail to initialize, they are logged
as DEGRADED but the system continues with reduced functionality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openhands.core.logger import openhands_logger as logger
from openhands.execution.task_engine import TaskEngine
from openhands.execution.task_models import (
    TaskPriority,
    TaskResult,
    TaskType,
)
from openhands.execution.task_runner import PhaseResult
from openhands.execution.task_state_machine import TaskPhase
from openhands.plugins.hook_runner import HookRunner
from openhands.plugins.plugin_registry import PluginRegistry

if TYPE_CHECKING:
    from openhands.controller.state.state import State
    from openhands.core.config import OpenHandsConfig
    from openhands.events.action.action import Action


class EngineeringOS:
    """Top-level orchestrator — the CANONICAL runtime for OpenHands.

    Owns all subsystems and wires them into the execution engine:
    - ErrorMemory: past errors and their resolutions
    - FixMemory: successful fix strategies
    - DecisionMemory: past decisions and outcomes
    - RetryPolicy: retry/escalate logic
    - ToolSelector: per-step tool filtering
    - ExecutionTrace: full execution recording
    - ArtifactBuilder: artifact persistence
    - PluginRegistry + HookRunner: plugin lifecycle
    - RepoIntel: repository intelligence (mandatory gate before PLAN)
    - Metrics + LogCollector: observability layer
    """

    def __init__(self) -> None:
        self._engine = TaskEngine()

        # ── Memory subsystems (MANDATORY spine) ────────────────────────────
        self._error_memory = self._create_error_memory()
        self._fix_memory = self._create_fix_memory()
        self._decision_memory = self._create_decision_memory()

        # ── Policy subsystems (MANDATORY spine) ────────────────────────────
        self._retry_policy = self._create_retry_policy()
        self._tool_selector = self._create_tool_selector()

        # ── Observability subsystems (MANDATORY spine) ─────────────────────
        self._execution_trace = self._create_execution_trace()
        self._artifact_builder = self._create_artifact_builder()

        # ── Plugin lifecycle (MANDATORY spine) ─────────────────────────────
        self._plugin_registry = self._create_plugin_registry()
        self._hook_runner = self._create_hook_runner()

        # ── Repo intelligence (MANDATORY gate before PLAN) ─────────────────
        self._repo_intel = self._create_repo_intel()

        # ── Metrics + Log Collector (observability layer) ──────────────────
        self._metrics = self._create_metrics()
        self._log_collector = self._create_log_collector()

        # ── Wire everything into the TaskRunner ────────────────────────────
        self._wire_subsystems()

        # Register observability callbacks
        self._engine.on_phase_start(self._log_phase_start)
        self._engine.on_phase_end(self._log_phase_end)
        self._engine.on_task_complete(self._log_task_complete)

        # Track initialization
        self._subsystem_report = self._build_subsystem_report()
        logger.info(
            f'[EngineeringOS] Initialized — {self._subsystem_report}'
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

        # Fire pre-task plugin hook
        if self._hook_runner:
            self._hook_runner.fire('pre_task', description=description)

        result = self._engine.run(task_id)

        # Fire post-task plugin hook
        if self._hook_runner:
            self._hook_runner.fire(
                'post_task',
                task_id=task_id,
                success=result.success,
            )

        return result

    async def run_controller_async(
        self,
        config: 'OpenHandsConfig',
        initial_user_action: 'Action',
        sid: str | None = None,
        exit_on_message: bool = False,
        fake_user_response_fn: Any = None,
        headless_mode: bool = True,
        memory: Any = None,
        conversation_instructions: str | None = None,
    ) -> 'State | None':
        """CANONICAL async entry point — drives execution through TaskEngine phases.

        This is the single authoritative execution flow. ALL entry points
        (CLI, server, programmatic) route through here.

        Architecture (Fix #1, #2, #3):
          1. PRE-PHASES: INTAKE -> CONTEXT_BUILD -> REPO_ANALYSIS -> PLAN
             Driven by TaskEngine through TaskRunner. These run BEFORE
             AgentController touches anything.
          2. EXECUTE PHASE: Delegates to AgentController for the LLM agent loop.
             AgentController is ONLY the execution adapter — it receives the
             parent EOS instance and does not create its own.
          3. POST-PHASES: TEST -> REVIEW -> ARTIFACT_GENERATION -> COMPLETE
             Driven by TaskEngine after AgentController finishes.

        Fix #6: Plugin hooks fire at every phase boundary (pre_task, pre_phase,
                post_phase, post_task) through the HookRunner.
        Fix #7: REPO_ANALYSIS is a mandatory gate — if repo_path is set and
                analysis fails, PLAN is blocked.
        Fix #8: Memory populates CONTEXT_BUILD, policy drives EXECUTE decisions.

        The AgentController receives THIS EngineeringOS instance (not a new one)
        to avoid circular creation and ensure a single subsystem spine.
        """
        # Import here to avoid circular imports at module level
        from openhands.core.main import run_controller

        logger.info(
            '[EngineeringOS] run_controller_async: canonical TaskEngine path'
        )

        # ── Fire pre-task plugin hooks (Fix #6: lifecycle ownership) ───────
        if self._hook_runner:
            self._hook_runner.fire('pre_task', description='async_controller')

        # ── Submit task to TaskEngine for phase tracking ──────────────────
        task_desc = ''
        if hasattr(initial_user_action, 'content'):
            task_desc = str(initial_user_action.content)[:500]

        # Determine repo path from config for mandatory gate enforcement
        repo_path = ''
        if hasattr(config, 'sandbox') and hasattr(config.sandbox, 'selected_repo'):
            repo_path = config.sandbox.selected_repo or ''

        task_id = self._engine.submit(
            title=task_desc[:100] or 'Agent task',
            description=task_desc,
            repo_path=repo_path,
        )

        task = self._engine.get_task(task_id)
        sm = self._engine.get_state_machine(task_id)
        if task:
            task.metadata['controller_mode'] = True
            task.metadata['sid'] = sid or ''
            task.metadata['canonical_path'] = True  # Mark as canonical

        # ══════════════════════════════════════════════════════════════════
        # PRE-PHASES: INTAKE -> CONTEXT_BUILD -> REPO_ANALYSIS -> PLAN
        # These run through TaskEngine BEFORE AgentController is invoked.
        # Fix #1: TaskEngine drives phases, not just observability tracking.
        # Fix #7: REPO_ANALYSIS is a mandatory gate before PLAN.
        # Fix #8: Memory populates CONTEXT_BUILD context.
        # ══════════════════════════════════════════════════════════════════
        pre_phases_ok = True
        if task and sm:
            pre_phases = [
                TaskPhase.INTAKE,
                TaskPhase.CONTEXT_BUILD,
                TaskPhase.REPO_ANALYSIS,
                TaskPhase.PLAN,
            ]
            repo_analysis_passed = False

            for phase in pre_phases:
                # Note: pre_phase/post_phase hooks are fired inside
                # TaskRunner.run_phase() — do NOT fire them here to
                # avoid duplicate hook execution.

                # Fix #7: REPO_ANALYSIS mandatory gate
                if (
                    phase == TaskPhase.PLAN
                    and not repo_analysis_passed
                    and repo_path
                ):
                    logger.error(
                        f'[EngineeringOS] PLAN blocked: REPO_ANALYSIS gate '
                        f'not passed for task {task_id}'
                    )
                    task.result.error = (
                        'PLAN blocked: REPO_ANALYSIS must pass first '
                        '(Fix #7: mandatory gate)'
                    )
                    pre_phases_ok = False
                    break

                # Execute phase through TaskRunner
                result = self._engine.runner.run_phase(phase, task)
                task.result.set_phase_result(
                    phase.value,
                    result.success,
                    result.error or str(result.output)[:500],
                )

                # Track REPO_ANALYSIS gate
                if phase == TaskPhase.REPO_ANALYSIS and result.success:
                    repo_analysis_passed = True

                # Transition state machine
                if not sm.is_terminal:
                    next_idx = pre_phases.index(phase) + 1
                    if next_idx < len(pre_phases):
                        try:
                            sm.transition_to(
                                pre_phases[next_idx], success=result.success
                            )
                        except Exception as exc:
                            logger.warning(
                                f'[EngineeringOS] SM transition warning: {exc}'
                            )

                if not result.success:
                    logger.warning(
                        f'[EngineeringOS] Pre-phase {phase.value} failed: '
                        f'{result.error}'
                    )
                    # Non-critical pre-phases: log but continue
                    # Only REPO_ANALYSIS gate blocks (handled above)

            if pre_phases_ok:
                logger.info(
                    f'[EngineeringOS] Pre-phases complete for {task_id}, '
                    f'proceeding to EXECUTE'
                )
            else:
                logger.warning(
                    f'[EngineeringOS] Pre-phases blocked for {task_id}, '
                    f'skipping EXECUTE'
                )

        # ══════════════════════════════════════════════════════════════════
        # EXECUTE PHASE: Delegate to AgentController (Fix #2: adapter only)
        # AgentController receives THIS EOS instance — single spine.
        # Fix #8: RetryPolicy consulted for retry decisions.
        # Fix #7: Skip EXECUTE if pre-phases failed (mandatory gate).
        # ══════════════════════════════════════════════════════════════════
        state: State | None = None
        try:
            if not pre_phases_ok:
                logger.warning(
                    f'[EngineeringOS] Skipping EXECUTE: pre-phases failed for {task_id}'
                )
                if task:
                    task.result.success = False
                    # task.result.error already set by the gate that failed
            else:
                try:
                    state = await run_controller(
                        config=config,
                        initial_user_action=initial_user_action,
                        sid=sid,
                        exit_on_message=exit_on_message,
                        fake_user_response_fn=fake_user_response_fn,
                        headless_mode=headless_mode,
                        memory=memory,
                        conversation_instructions=conversation_instructions,
                        eos=self,  # Pass THIS instance — single spine (Fix #2)
                    )
                except Exception:
                    if task:
                        task.result.success = False
                        task.result.error = 'AgentController raised an exception'
                    raise
                finally:
                    # Record EXECUTE phase result
                    execute_success = False
                    if state and hasattr(state, 'agent_state'):
                        from openhands.core.schema import AgentState
                        execute_success = state.agent_state == AgentState.FINISHED

                    if task:
                        task.result.set_phase_result(
                            'execute',
                            execute_success,
                            f'Agent state: {state.agent_state if state and hasattr(state, "agent_state") else "unknown"}',
                        )

                    # ══════════════════════════════════════════════════════
                    # POST-PHASES: TEST -> REVIEW -> ARTIFACT_GENERATION
                    # Run through TaskEngine AFTER AgentController finishes.
                    # Fix #1: TaskEngine owns the full lifecycle.
                    # Hooks fired inside TaskRunner.run_phase().
                    # ══════════════════════════════════════════════════════
                    if task and sm and not sm.is_terminal:
                        post_phases = [
                            TaskPhase.TEST,
                            TaskPhase.REVIEW,
                            TaskPhase.ARTIFACT_GENERATION,
                        ]
                        for phase in post_phases:
                            post_result = self._engine.runner.run_phase(
                                phase, task
                            )
                            task.result.set_phase_result(
                                phase.value,
                                post_result.success,
                                post_result.error
                                or str(post_result.output)[:500],
                            )

                            # Collect artifacts
                            for artifact in post_result.artifacts:
                                task.result.add_artifact(artifact)

                    # Record final task result
                    if task and not task.result.error:
                        if state and hasattr(state, 'agent_state'):
                            from openhands.core.schema import AgentState
                            task.result.success = (
                                state.agent_state == AgentState.FINISHED
                            )
                            task.result.message = (
                                f'Agent finished in state: {state.agent_state}'
                            )
                        else:
                            task.result.success = False
                            task.result.error = (
                                'No state returned from controller'
                            )
        finally:
            # ── Fire post-task hook (Fix #6: symmetric lifecycle) ──────────
            # Guaranteed to fire whenever pre_task fired, regardless of
            # whether pre-phases failed or AgentController raised.
            if self._hook_runner:
                self._hook_runner.fire(
                    'post_task',
                    task_id=task_id,
                    success=task.result.success if task else False,
                )

        return state

    def run_orchestrated(
        self,
        task_title: str,
        task_description: str,
        repo_path: str = '',
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Run a task through the multi-agent orchestration pipeline (Fix #8).

        This drives the task through the full role pipeline with state-driven
        transitions and evidence passing between roles:
            Planner -> Architect -> Coder -> Tester -> Debugger -> Reviewer -> Manager

        Each role receives the shared RoleContext which accumulates evidence
        from previous roles. The ManagerAgent handles failure routing and
        retry logic (Debugger -> Coder -> Tester loops).

        Returns:
            dict with 'success', 'error', 'role_results', 'duration_s'
        """
        try:
            from openhands.agents import (
                ArchitectAgent,
                CoderAgent,
                DebuggerAgent,
                ManagerAgent,
                PlannerAgent,
                ReviewerAgent,
                TesterAgent,
            )
            from openhands.agents.base_role import RoleContext
        except ImportError as exc:
            logger.warning(f'[EngineeringOS] Multi-agent system not available: {exc}')
            return {
                'success': False,
                'error': f'Multi-agent system not available: {exc}',
                'role_results': [],
                'duration_s': 0.0,
            }

        # Build shared context with evidence from memory subsystems
        context = RoleContext(
            task_title=task_title,
            task_description=task_description,
            repo_path=repo_path,
        )

        # Populate context from memory subsystems (evidence passing)
        if self._error_memory:
            try:
                recent = self._error_memory.get_recent(limit=10)
                context.error_memory = [
                    {'type': e.error_type, 'message': e.error_message}
                    for e in recent
                ]
            except Exception:
                pass

        if self._fix_memory:
            try:
                recent = self._fix_memory.get_recent(limit=10)
                context.fix_memory = [
                    {'error_type': f.error_type, 'fix': f.fix_description}
                    for f in recent
                ]
            except Exception:
                pass

        # Create and register all roles
        manager = ManagerAgent()
        manager.set_retry_limits(debug_retries=max_retries, total_retries=max_retries)
        manager.register_all_roles([
            PlannerAgent(),
            ArchitectAgent(),
            CoderAgent(),
            TesterAgent(),
            DebuggerAgent(),
            ReviewerAgent(),
        ])

        # Fire pre-orchestration hook
        if self._hook_runner:
            self._hook_runner.fire('pre_orchestration', task_title=task_title)

        logger.info(
            f'[EngineeringOS] Starting orchestrated execution: "{task_title}"'
        )

        # Run the full pipeline through ManagerAgent
        result = manager.run(context)

        # Fire post-orchestration hook
        if self._hook_runner:
            self._hook_runner.fire(
                'post_orchestration',
                task_title=task_title,
                success=result.success,
            )

        # Record in metrics
        if self._metrics:
            try:
                self._metrics.increment(
                    'orchestrated_tasks',
                    labels={'success': str(result.success)},
                )
            except Exception:
                pass

        return {
            'success': result.success,
            'error': result.error,
            'role_results': result.output_data,
            'duration_s': result.duration_s,
        }

    def get_task_status(self, task_id: str) -> dict[str, Any]:
        """Get current status of a running or completed task."""
        return self._engine.get_task_status(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all tasks with their current status."""
        return self._engine.list_tasks()

    # ── Subsystem accessors (MANDATORY — all must exist) ─────────────────

    @property
    def error_memory(self) -> Any:
        return self._error_memory

    @property
    def fix_memory(self) -> Any:
        return self._fix_memory

    @property
    def decision_memory(self) -> Any:
        return self._decision_memory

    @property
    def retry_policy(self) -> Any:
        return self._retry_policy

    @property
    def tool_selector(self) -> Any:
        return self._tool_selector

    @property
    def execution_trace(self) -> Any:
        return self._execution_trace

    @property
    def artifact_builder(self) -> Any:
        return self._artifact_builder

    @property
    def plugin_registry(self) -> PluginRegistry | None:
        return self._plugin_registry

    @property
    def hook_runner(self) -> HookRunner | None:
        return self._hook_runner

    @property
    def repo_intel(self) -> Any:
        return self._repo_intel

    @property
    def metrics(self) -> Any:
        return self._metrics

    @property
    def log_collector(self) -> Any:
        return self._log_collector

    # ── Subsystem creation (MANDATORY — log DEGRADED on failure) ──────────

    @staticmethod
    def _create_error_memory() -> Any:
        try:
            from openhands.memory.error_memory import ErrorMemory
            mem = ErrorMemory()
            logger.info('[EngineeringOS] ErrorMemory: ACTIVE')
            return mem
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ErrorMemory: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_fix_memory() -> Any:
        try:
            from openhands.memory.fix_memory import FixMemory
            mem = FixMemory()
            logger.info('[EngineeringOS] FixMemory: ACTIVE')
            return mem
        except Exception as exc:
            logger.warning(f'[EngineeringOS] FixMemory: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_decision_memory() -> Any:
        try:
            from openhands.memory.decision_memory import DecisionMemory
            mem = DecisionMemory()
            logger.info('[EngineeringOS] DecisionMemory: ACTIVE')
            return mem
        except Exception as exc:
            logger.warning(f'[EngineeringOS] DecisionMemory: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_retry_policy() -> Any:
        try:
            from openhands.policy.retry_policy import RetryPolicy
            policy = RetryPolicy()
            logger.info('[EngineeringOS] RetryPolicy: ACTIVE')
            return policy
        except Exception as exc:
            logger.warning(f'[EngineeringOS] RetryPolicy: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_tool_selector() -> Any:
        try:
            from openhands.policy.tool_selector import ToolSelector
            selector = ToolSelector()
            logger.info('[EngineeringOS] ToolSelector: ACTIVE')
            return selector
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ToolSelector: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_execution_trace() -> Any:
        try:
            from openhands.observability.execution_trace import ExecutionTrace
            trace = ExecutionTrace()
            logger.info('[EngineeringOS] ExecutionTrace: ACTIVE')
            return trace
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ExecutionTrace: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_artifact_builder() -> Any:
        try:
            from openhands.observability.artifact_builder import ArtifactBuilder
            builder = ArtifactBuilder()
            logger.info('[EngineeringOS] ArtifactBuilder: ACTIVE')
            return builder
        except Exception as exc:
            logger.warning(f'[EngineeringOS] ArtifactBuilder: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_plugin_registry() -> PluginRegistry | None:
        try:
            registry = PluginRegistry()
            logger.info('[EngineeringOS] PluginRegistry: ACTIVE')
            return registry
        except Exception as exc:
            logger.warning(f'[EngineeringOS] PluginRegistry: DEGRADED ({exc})')
            return None

    def _create_hook_runner(self) -> HookRunner | None:
        if self._plugin_registry is None:
            logger.warning('[EngineeringOS] HookRunner: DEGRADED (no registry)')
            return None
        try:
            runner = HookRunner(self._plugin_registry)
            logger.info('[EngineeringOS] HookRunner: ACTIVE')
            return runner
        except Exception as exc:
            logger.warning(f'[EngineeringOS] HookRunner: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_repo_intel() -> Any:
        """Create repo intelligence subsystem (mandatory gate before PLAN)."""
        try:
            from openhands.repo_intel.indexer import RepoIndexer
            indexer = RepoIndexer()
            logger.info('[EngineeringOS] RepoIntel: ACTIVE')
            return indexer
        except Exception as exc:
            logger.warning(f'[EngineeringOS] RepoIntel: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_metrics() -> Any:
        try:
            from openhands.observability.metrics import MetricsCollector
            m = MetricsCollector()
            logger.info('[EngineeringOS] Metrics: ACTIVE')
            return m
        except Exception as exc:
            logger.warning(f'[EngineeringOS] Metrics: DEGRADED ({exc})')
            return None

    @staticmethod
    def _create_log_collector() -> Any:
        try:
            from openhands.observability.log_collector import LogCollector
            lc = LogCollector()
            logger.info('[EngineeringOS] LogCollector: ACTIVE')
            return lc
        except Exception as exc:
            logger.warning(f'[EngineeringOS] LogCollector: DEGRADED ({exc})')
            return None

    def _wire_subsystems(self) -> None:
        """Wire ALL subsystems into the TaskRunner.

        This is the key integration point — connects every subsystem
        to the execution engine. All subsystems are MANDATORY; missing
        ones are logged as DEGRADED with a warning but don't block
        initialization (fail-open for resilience).

        Fix #5: Plugin lifecycle (HookRunner) is now wired into TaskRunner
        so hooks fire at every phase boundary (pre_phase / post_phase).

        Fix #6: Every subsystem is treated as MANDATORY. Missing subsystems
        are logged at WARNING level to make spine gaps visible.
        """
        runner = self._engine.runner
        missing: list[str] = []

        # Wire memory subsystems (MANDATORY)
        if self._error_memory:
            runner.set_error_memory(self._error_memory)
        else:
            missing.append('ErrorMemory')

        if self._fix_memory:
            runner.set_fix_memory(self._fix_memory)
        else:
            missing.append('FixMemory')

        if self._decision_memory:
            runner.set_decision_memory(self._decision_memory)
        else:
            missing.append('DecisionMemory')

        # Wire policy subsystems (MANDATORY)
        if self._retry_policy:
            runner.set_retry_policy(self._retry_policy)
        else:
            missing.append('RetryPolicy')

        if self._tool_selector:
            runner.set_tool_selector(self._tool_selector)
        else:
            missing.append('ToolSelector')

        # Wire observability subsystems (MANDATORY)
        if self._execution_trace:
            runner.set_execution_trace(self._execution_trace)
        else:
            missing.append('ExecutionTrace')

        if self._artifact_builder:
            runner.set_artifact_builder(self._artifact_builder)
        else:
            missing.append('ArtifactBuilder')

        # Wire plugin lifecycle into TaskRunner (Fix #5)
        if self._hook_runner:
            runner.set_hook_runner(self._hook_runner)
        else:
            missing.append('HookRunner')

        # Log mandatory spine status
        if missing:
            logger.warning(
                f'[EngineeringOS] MANDATORY spine gaps: {", ".join(missing)} — '
                f'system running in DEGRADED mode'
            )
        else:
            logger.info('[EngineeringOS] All mandatory spine subsystems wired')

    def _build_subsystem_report(self) -> str:
        """Build a human-readable report of subsystem status."""
        subsystems = {
            'ErrorMemory': self._error_memory,
            'FixMemory': self._fix_memory,
            'DecisionMemory': self._decision_memory,
            'RetryPolicy': self._retry_policy,
            'ToolSelector': self._tool_selector,
            'ExecutionTrace': self._execution_trace,
            'ArtifactBuilder': self._artifact_builder,
            'PluginRegistry': self._plugin_registry,
            'HookRunner': self._hook_runner,
            'RepoIntel': self._repo_intel,
            'Metrics': self._metrics,
            'LogCollector': self._log_collector,
        }
        active = sum(1 for v in subsystems.values() if v is not None)
        total = len(subsystems)
        degraded = [k for k, v in subsystems.items() if v is None]
        report = f'{active}/{total} subsystems ACTIVE'
        if degraded:
            report += f', DEGRADED: {", ".join(degraded)}'
        return report

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
