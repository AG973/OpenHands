"""Manager Agent — orchestrates the full role pipeline.

The manager is the top-level orchestrator that drives tasks through
the entire role pipeline: Planner -> Architect -> Coder -> Tester ->
Debugger -> Reviewer. It handles role transitions, failure routing,
retry logic, and final result aggregation.

Patterns extracted from:
    - GPT-Pilot: Orchestrator driving 14 agents in sequence
    - CrewAI: Crew.kickoff() with sequential/hierarchical process
    - LangGraph: StateGraph with conditional edges
    - AutoGen: GroupChat manager with speaker selection
"""

from __future__ import annotations

import time
from typing import Any

from openhands.agents.base_role import (
    ROLE_EXECUTION_ORDER,
    AgentRole,
    RoleContext,
    RoleName,
    RoleOutput,
)
from openhands.core.logger import openhands_logger as logger


# Default retry limits
MAX_DEBUG_RETRIES = 3
MAX_TOTAL_RETRIES = 5


class ManagerAgent(AgentRole):
    """Orchestrates the full agent role pipeline.

    The manager:
    - Drives tasks through Planner -> Architect -> Coder -> Tester -> Debugger -> Reviewer
    - Routes failures to the Debugger for analysis
    - Manages retry loops (Debugger -> Coder -> Tester)
    - Aggregates results from all roles
    - Produces final execution summary
    - NO CHAT LOOP — strict state-driven execution only
    """

    def __init__(self) -> None:
        super().__init__()
        self._roles: dict[RoleName, AgentRole] = {}
        self._max_debug_retries = MAX_DEBUG_RETRIES
        self._max_total_retries = MAX_TOTAL_RETRIES

    @property
    def role_name(self) -> RoleName:
        return RoleName.MANAGER

    @property
    def description(self) -> str:
        return (
            'Orchestrates the full agent role pipeline with strict state-driven '
            'execution. Manages role transitions, failure routing, and retry logic.'
        )

    def register_role(self, role: AgentRole) -> None:
        """Register an agent role for the pipeline."""
        self._roles[role.role_name] = role
        logger.info(f'[Manager] Registered role: {role.role_name.value}')

    def register_all_roles(self, roles: list[AgentRole]) -> None:
        """Register multiple roles at once."""
        for role in roles:
            self.register_role(role)

    def set_retry_limits(
        self, debug_retries: int = MAX_DEBUG_RETRIES, total_retries: int = MAX_TOTAL_RETRIES
    ) -> None:
        """Configure retry limits."""
        self._max_debug_retries = debug_retries
        self._max_total_retries = total_retries

    def execute(self, context: RoleContext) -> RoleOutput:
        """Drive the task through the full role pipeline.

        Execution order:
            1. Planner — creates execution plan
            2. Architect — makes design decisions
            3. Coder — implements changes
            4. Tester — runs tests
            5. (on failure) Debugger — analyzes failure, suggests fix
            6. (retry) Coder -> Tester loop
            7. Reviewer — validates quality
        """
        pipeline_start = time.time()
        role_results: list[RoleOutput] = []
        retry_count = 0

        # Phase 1: Planning
        planner_output = self._run_role(RoleName.PLANNER, context)
        role_results.append(planner_output)
        if not planner_output.success:
            return self._build_final_output(
                role_results, context, pipeline_start,
                error=f'Planning failed: {planner_output.error}',
            )

        # Phase 2: Architecture
        architect_output = self._run_role(RoleName.ARCHITECT, context)
        role_results.append(architect_output)
        if not architect_output.success:
            return self._build_final_output(
                role_results, context, pipeline_start,
                error=f'Architecture failed: {architect_output.error}',
            )

        # Phase 3-5: Code -> Test -> (Debug -> Retry) loop
        while retry_count < self._max_total_retries:
            # Code
            coder_output = self._run_role(RoleName.CODER, context)
            role_results.append(coder_output)
            if not coder_output.success:
                return self._build_final_output(
                    role_results, context, pipeline_start,
                    error=f'Coding failed: {coder_output.error}',
                )

            # Test
            tester_output = self._run_role(RoleName.TESTER, context)
            role_results.append(tester_output)

            if tester_output.success:
                # Tests passed — move to review
                break

            # Tests failed — route to debugger
            retry_count += 1
            if retry_count >= self._max_total_retries:
                logger.warning(
                    f'[Manager] Max retries ({self._max_total_retries}) reached'
                )
                return self._build_final_output(
                    role_results, context, pipeline_start,
                    error=f'Max retries exceeded after {retry_count} attempts',
                )

            # Debug
            debugger_output = self._run_role(RoleName.DEBUGGER, context)
            role_results.append(debugger_output)

            if not debugger_output.success:
                return self._build_final_output(
                    role_results, context, pipeline_start,
                    error=f'Debug analysis failed: {debugger_output.error}',
                )

            logger.info(f'[Manager] Retry {retry_count}/{self._max_total_retries}')

        # Phase 6: Review
        reviewer_output = self._run_role(RoleName.REVIEWER, context)
        role_results.append(reviewer_output)

        if not reviewer_output.success:
            return self._build_final_output(
                role_results, context, pipeline_start,
                error=f'Review failed: {reviewer_output.error}',
            )

        # All phases passed
        return self._build_final_output(role_results, context, pipeline_start)

    def _run_role(self, role_name: RoleName, context: RoleContext) -> RoleOutput:
        """Run a specific role from the registry."""
        role = self._roles.get(role_name)
        if role is None:
            logger.warning(f'[Manager] Role {role_name.value} not registered — skipping')
            return RoleOutput(
                role=role_name,
                success=True,
                metadata={'note': f'Role {role_name.value} not registered, skipped'},
            )

        logger.info(f'[Manager] Running role: {role_name.value}')
        return role.run(context)

    def _build_final_output(
        self,
        role_results: list[RoleOutput],
        context: RoleContext,
        start_time: float,
        error: str = '',
    ) -> RoleOutput:
        """Build the final aggregated output from all role results."""
        duration = time.time() - start_time
        success = not error

        # Aggregate artifacts from all roles
        all_artifacts: list[dict[str, Any]] = []
        for result in role_results:
            all_artifacts.extend(result.artifacts)

        # Build execution summary
        summary: dict[str, Any] = {
            'total_duration_s': duration,
            'role_count': len(role_results),
            'roles_executed': [r.role.value for r in role_results],
            'role_durations': {r.role.value: r.duration_s for r in role_results},
            'success': success,
            'error': error,
            'retry_count': sum(1 for r in role_results if r.role == RoleName.DEBUGGER),
        }

        logger.info(
            f'[Manager] Pipeline {"COMPLETED" if success else "FAILED"} in {duration:.2f}s '
            f'({len(role_results)} roles executed)'
        )

        return RoleOutput(
            role=self.role_name,
            success=success,
            error=error,
            output_data=summary,
            artifacts=all_artifacts,
            duration_s=duration,
        )
