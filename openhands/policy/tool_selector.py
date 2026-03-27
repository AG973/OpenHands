"""Tool Selector — chooses the right tool for each task phase.

Selects tools based on task type, phase, available capabilities,
and past success rates from decision memory. Filters out tools
that are too risky or inappropriate for the current context.

Patterns extracted from:
    - OpenHands: ActionSpace tool filtering
    - CrewAI: Agent tool assignment
    - LangChain: Tool selection with descriptions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class ToolCategory(Enum):
    """Categories of tools available in the system."""

    FILE_READ = 'file_read'
    FILE_WRITE = 'file_write'
    FILE_EDIT = 'file_edit'
    SHELL_EXEC = 'shell_exec'
    GIT_OP = 'git_op'
    BROWSER = 'browser'
    SEARCH = 'search'
    LLM_CALL = 'llm_call'
    TEST_RUN = 'test_run'
    DEPLOY = 'deploy'


class ToolRisk(Enum):
    """Risk level of a tool operation."""

    SAFE = 'safe'  # Read-only, no side effects
    LOW = 'low'  # Reversible side effects
    MEDIUM = 'medium'  # Potentially destructive but recoverable
    HIGH = 'high'  # Destructive or irreversible
    CRITICAL = 'critical'  # System-level, requires explicit approval


@dataclass
class ToolSpec:
    """Specification of an available tool."""

    name: str
    category: ToolCategory
    risk: ToolRisk = ToolRisk.LOW
    description: str = ''
    applicable_phases: list[str] = field(default_factory=list)
    requires_approval: bool = False
    enabled: bool = True
    success_rate: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'category': self.category.value,
            'risk': self.risk.value,
            'description': self.description,
            'enabled': self.enabled,
        }


# Default tool registry
DEFAULT_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name='file_read',
        category=ToolCategory.FILE_READ,
        risk=ToolRisk.SAFE,
        description='Read file contents',
        applicable_phases=['context_build', 'repo_analysis', 'plan', 'execute', 'review'],
    ),
    ToolSpec(
        name='file_write',
        category=ToolCategory.FILE_WRITE,
        risk=ToolRisk.MEDIUM,
        description='Write/create files',
        applicable_phases=['execute'],
    ),
    ToolSpec(
        name='file_edit',
        category=ToolCategory.FILE_EDIT,
        risk=ToolRisk.MEDIUM,
        description='Edit existing files with targeted changes',
        applicable_phases=['execute', 'retry_or_fix'],
    ),
    ToolSpec(
        name='shell_exec',
        category=ToolCategory.SHELL_EXEC,
        risk=ToolRisk.MEDIUM,
        description='Execute shell commands',
        applicable_phases=['execute', 'test', 'retry_or_fix'],
    ),
    ToolSpec(
        name='git_commit',
        category=ToolCategory.GIT_OP,
        risk=ToolRisk.LOW,
        description='Git commit changes',
        applicable_phases=['execute', 'artifact_generation'],
    ),
    ToolSpec(
        name='git_push',
        category=ToolCategory.GIT_OP,
        risk=ToolRisk.MEDIUM,
        description='Git push to remote',
        applicable_phases=['artifact_generation'],
    ),
    ToolSpec(
        name='git_branch',
        category=ToolCategory.GIT_OP,
        risk=ToolRisk.LOW,
        description='Create/switch git branches',
        applicable_phases=['intake', 'execute'],
    ),
    ToolSpec(
        name='browser_navigate',
        category=ToolCategory.BROWSER,
        risk=ToolRisk.LOW,
        description='Navigate to URL in browser',
        applicable_phases=['execute', 'test'],
    ),
    ToolSpec(
        name='search_code',
        category=ToolCategory.SEARCH,
        risk=ToolRisk.SAFE,
        description='Search code in repository',
        applicable_phases=['context_build', 'repo_analysis', 'plan', 'execute', 'failure_analysis'],
    ),
    ToolSpec(
        name='run_tests',
        category=ToolCategory.TEST_RUN,
        risk=ToolRisk.LOW,
        description='Execute test suite',
        applicable_phases=['test', 'retry_or_fix'],
    ),
    ToolSpec(
        name='deploy',
        category=ToolCategory.DEPLOY,
        risk=ToolRisk.CRITICAL,
        description='Deploy application',
        applicable_phases=['artifact_generation'],
        requires_approval=True,
    ),
]


class ToolSelector:
    """Selects appropriate tools for each task phase.

    Usage:
        selector = ToolSelector()
        tools = selector.select_tools(phase='execute', task_type='bug_fix')
        for tool in tools:
            if selector.is_allowed(tool.name, phase='execute', risk_level='medium'):
                # Use tool
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._phase_allowlist: dict[str, set[str]] = {}
        self._risk_ceiling: ToolRisk = ToolRisk.HIGH  # Max risk without approval

        # Register default tools
        for tool in DEFAULT_TOOLS:
            self.register_tool(tool)

    def register_tool(self, spec: ToolSpec) -> None:
        """Register a tool in the selector."""
        self._tools[spec.name] = spec
        for phase in spec.applicable_phases:
            if phase not in self._phase_allowlist:
                self._phase_allowlist[phase] = set()
            self._phase_allowlist[phase].add(spec.name)

    def select_tools(
        self,
        phase: str,
        task_type: str = '',
        max_risk: ToolRisk = ToolRisk.HIGH,
    ) -> list[ToolSpec]:
        """Select applicable tools for a phase.

        Filters by:
        1. Phase applicability
        2. Risk ceiling
        3. Tool enabled status
        4. Success rate (deprioritize low-success tools)
        """
        allowed_names = self._phase_allowlist.get(phase, set())
        risk_order = [ToolRisk.SAFE, ToolRisk.LOW, ToolRisk.MEDIUM, ToolRisk.HIGH, ToolRisk.CRITICAL]
        max_idx = risk_order.index(max_risk)

        selected: list[ToolSpec] = []
        for name in allowed_names:
            tool = self._tools.get(name)
            if tool is None or not tool.enabled:
                continue
            tool_idx = risk_order.index(tool.risk)
            if tool_idx <= max_idx:
                selected.append(tool)

        # Sort by risk (safest first), then by success rate
        selected.sort(key=lambda t: (risk_order.index(t.risk), -t.success_rate))
        return selected

    def is_allowed(
        self,
        tool_name: str,
        phase: str,
        risk_override: ToolRisk | None = None,
    ) -> bool:
        """Check if a tool is allowed in the current context."""
        tool = self._tools.get(tool_name)
        if tool is None or not tool.enabled:
            return False

        # Check phase allowlist
        allowed = self._phase_allowlist.get(phase, set())
        if tool_name not in allowed:
            return False

        # Check risk ceiling
        max_risk = risk_override or self._risk_ceiling
        risk_order = [ToolRisk.SAFE, ToolRisk.LOW, ToolRisk.MEDIUM, ToolRisk.HIGH, ToolRisk.CRITICAL]
        if risk_order.index(tool.risk) > risk_order.index(max_risk):
            return False

        return True

    def update_success_rate(self, tool_name: str, success: bool) -> None:
        """Update a tool's success rate based on usage outcome."""
        tool = self._tools.get(tool_name)
        if tool:
            alpha = 0.2
            result = 1.0 if success else 0.0
            tool.success_rate = alpha * result + (1 - alpha) * tool.success_rate

    def disable_tool(self, tool_name: str) -> None:
        """Disable a tool (e.g., after repeated failures)."""
        tool = self._tools.get(tool_name)
        if tool:
            tool.enabled = False
            logger.info(f'[ToolSelector] Disabled tool: {tool_name}')

    def enable_tool(self, tool_name: str) -> None:
        """Re-enable a tool."""
        tool = self._tools.get(tool_name)
        if tool:
            tool.enabled = True

    def set_risk_ceiling(self, max_risk: ToolRisk) -> None:
        """Set the maximum risk level allowed without approval."""
        self._risk_ceiling = max_risk

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools."""
        return [t.to_dict() for t in self._tools.values()]

    def stats(self) -> dict[str, Any]:
        """Get selector statistics."""
        return {
            'total_tools': len(self._tools),
            'enabled_tools': sum(1 for t in self._tools.values() if t.enabled),
            'by_category': {
                cat.value: sum(
                    1 for t in self._tools.values() if t.category == cat
                )
                for cat in ToolCategory
            },
            'risk_ceiling': self._risk_ceiling.value,
        }
