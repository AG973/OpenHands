"""Base Agent Role — foundation for all specialized agent roles.

Every agent role in the system inherits from AgentRole. Roles are
state-driven executors, NOT chat-loop participants. Each role:

1. Receives a task + context
2. Performs its specific function (plan, code, test, etc.)
3. Returns structured output
4. Passes control to the next role in the pipeline

The role flow is STRICT and deterministic:
    Planner -> Architect -> Coder -> Tester -> Debugger -> Reviewer -> Manager

Patterns extracted from:
    - GPT-Pilot: 14 specialized agents with strict hand-off
    - CrewAI: Agent-Task-Crew with role/goal/backstory
    - LangGraph: StateGraph for deterministic orchestration
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class RoleName(Enum):
    """Enumeration of all agent roles in the system."""

    PLANNER = 'planner'
    ARCHITECT = 'architect'
    CODER = 'coder'
    TESTER = 'tester'
    DEBUGGER = 'debugger'
    REVIEWER = 'reviewer'
    MANAGER = 'manager'


# Strict role execution order — NO deviation allowed
ROLE_EXECUTION_ORDER: list[RoleName] = [
    RoleName.PLANNER,
    RoleName.ARCHITECT,
    RoleName.CODER,
    RoleName.TESTER,
    RoleName.DEBUGGER,
    RoleName.REVIEWER,
    RoleName.MANAGER,
]


@dataclass
class RoleContext:
    """Context passed to each agent role during execution.

    This is the shared state that flows through the role pipeline.
    Each role reads from and writes to this context.
    """

    # Task information
    task_id: str = ''
    task_title: str = ''
    task_description: str = ''
    task_type: str = ''
    repo_path: str = ''

    # Repo intelligence (populated by REPO_ANALYSIS phase)
    file_map: dict[str, Any] = field(default_factory=dict)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    test_map: dict[str, list[str]] = field(default_factory=dict)
    api_map: dict[str, Any] = field(default_factory=dict)
    impact_files: list[str] = field(default_factory=list)

    # Plan (populated by PlannerAgent)
    plan_steps: list[dict[str, Any]] = field(default_factory=list)

    # Architecture decisions (populated by ArchitectAgent)
    architecture_decisions: list[str] = field(default_factory=list)
    files_to_create: list[str] = field(default_factory=list)
    files_to_modify: list[str] = field(default_factory=list)
    design_constraints: list[str] = field(default_factory=list)

    # Code changes (populated by CoderAgent)
    code_changes: list[dict[str, Any]] = field(default_factory=list)
    applied_patches: list[str] = field(default_factory=list)

    # Test results (populated by TesterAgent)
    test_passed: bool = False
    test_output: str = ''
    failed_tests: list[str] = field(default_factory=list)

    # Debug findings (populated by DebuggerAgent)
    debug_analysis: str = ''
    suggested_fixes: list[dict[str, Any]] = field(default_factory=list)

    # Review results (populated by ReviewerAgent)
    review_passed: bool = False
    review_comments: list[str] = field(default_factory=list)
    review_score: float = 0.0

    # Memory (populated by memory system)
    error_memory: list[dict[str, Any]] = field(default_factory=list)
    fix_memory: list[dict[str, Any]] = field(default_factory=list)
    decision_memory: list[dict[str, Any]] = field(default_factory=list)
    repo_memory: dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleOutput:
    """Output from an agent role execution.

    Every role returns this structured output. The success flag determines
    whether the pipeline continues to the next role or routes to failure handling.
    """

    role: RoleName
    success: bool = True
    error: str = ''
    output_data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    next_role_hint: RoleName | None = None
    duration_s: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'role': self.role.value,
            'success': self.success,
            'error': self.error,
            'duration_s': self.duration_s,
            'artifacts_count': len(self.artifacts),
        }


class AgentRole(ABC):
    """Base class for all specialized agent roles.

    Subclasses must implement the execute() method which performs the
    role's specific function and returns a RoleOutput.

    Usage:
        class MyRole(AgentRole):
            def execute(self, context: RoleContext) -> RoleOutput:
                # Do role-specific work
                return RoleOutput(role=self.role_name, success=True)

        role = MyRole()
        output = role.run(context)
    """

    def __init__(self) -> None:
        self._initialized = False

    @property
    @abstractmethod
    def role_name(self) -> RoleName:
        """The name of this role."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this role does."""
        ...

    @abstractmethod
    def execute(self, context: RoleContext) -> RoleOutput:
        """Execute the role's function.

        This is where the actual work happens. Each role implementation
        provides its own logic here.

        Args:
            context: The shared role context with all accumulated state

        Returns:
            RoleOutput with success/failure and any produced artifacts
        """
        ...

    def validate_input(self, context: RoleContext) -> list[str]:
        """Validate that the context has required data for this role.

        Override in subclasses to add role-specific validation.

        Returns:
            List of validation error messages (empty = valid)
        """
        return []

    def run(self, context: RoleContext) -> RoleOutput:
        """Run this role with full lifecycle management.

        This is the main entry point. It handles:
        1. Input validation
        2. Pre-execution setup
        3. Execution with timing
        4. Error handling
        5. Post-execution logging

        Args:
            context: The shared role context

        Returns:
            RoleOutput from execution
        """
        logger.info(
            f'[{self.role_name.value}] Starting: {context.task_title or context.task_id}'
        )

        # Validate input
        errors = self.validate_input(context)
        if errors:
            error_msg = f'Validation failed: {"; ".join(errors)}'
            logger.warning(f'[{self.role_name.value}] {error_msg}')
            return RoleOutput(
                role=self.role_name,
                success=False,
                error=error_msg,
            )

        # Execute with timing and error handling
        start_time = time.time()
        try:
            output = self.execute(context)
            output.duration_s = time.time() - start_time

            logger.info(
                f'[{self.role_name.value}] Completed in {output.duration_s:.2f}s '
                f'(success={output.success})'
            )
            return output

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f'{type(e).__name__}: {str(e)}'
            logger.error(
                f'[{self.role_name.value}] Failed after {duration:.2f}s: {error_msg}'
            )
            return RoleOutput(
                role=self.role_name,
                success=False,
                error=error_msg,
                duration_s=duration,
            )

    def get_next_role(self) -> RoleName | None:
        """Get the next role in the execution order."""
        try:
            idx = ROLE_EXECUTION_ORDER.index(self.role_name)
            if idx + 1 < len(ROLE_EXECUTION_ORDER):
                return ROLE_EXECUTION_ORDER[idx + 1]
        except ValueError:
            pass
        return None
