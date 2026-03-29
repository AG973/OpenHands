"""Task data models — the core data structures for the execution engine.

Every task that enters the system is represented as a Task object with
full context, artifacts, and results. These models are the single source
of truth for what the system did, why, and what it produced.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskPriority(Enum):
    """Task priority levels."""

    CRITICAL = 'critical'
    HIGH = 'high'
    NORMAL = 'normal'
    LOW = 'low'


class TaskType(Enum):
    """Classification of task types."""

    FEATURE = 'feature'
    BUG_FIX = 'bug_fix'
    REFACTOR = 'refactor'
    TEST = 'test'
    DOCUMENTATION = 'documentation'
    INVESTIGATION = 'investigation'
    DEPLOYMENT = 'deployment'
    REVIEW = 'review'
    CUSTOM = 'custom'


class ArtifactType(Enum):
    """Types of artifacts produced by task execution."""

    CODE_DIFF = 'code_diff'
    TEST_RESULT = 'test_result'
    LOG = 'log'
    SCREENSHOT = 'screenshot'
    PR_URL = 'pr_url'
    BUILD_OUTPUT = 'build_output'
    ANALYSIS_REPORT = 'analysis_report'
    EXECUTION_TRACE = 'execution_trace'
    ERROR_REPORT = 'error_report'
    EXECUTION_LOG = 'execution_log'
    SUMMARY = 'summary'


class StepStatus(Enum):
    """Status of a single plan step during execution."""

    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'


@dataclass
class PlanStep:
    """A single step in the execution plan.

    Generated during the PLAN phase and executed one-by-one during EXECUTE.
    Each step tracks its own status, output, tool usage, and timing.
    """

    step_id: int = 0
    action: str = ''  # 'file_edit', 'shell_command', 'install_dep', 'create_file', 'analyze'
    description: str = ''
    target_files: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # other step_ids this depends on
    tools_allowed: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ''
    started_at: float = 0.0
    completed_at: float = 0.0
    decision_reasoning: str = ''  # why this step was chosen

    @property
    def duration_s(self) -> float:
        if self.started_at == 0.0:
            return 0.0
        end = self.completed_at if self.completed_at > 0 else time.time()
        return end - self.started_at

    def to_dict(self) -> dict[str, Any]:
        return {
            'step_id': self.step_id,
            'action': self.action,
            'description': self.description[:200],
            'target_files': self.target_files,
            'commands': self.commands,
            'tools_used': self.tools_used,
            'status': self.status.value,
            'error': self.error[:200] if self.error else '',
            'duration_s': self.duration_s,
        }


class ErrorCategory(Enum):
    """Structured error classification for failure analysis."""

    SYNTAX_ERROR = 'syntax_error'
    RUNTIME_ERROR = 'runtime_error'
    IMPORT_ERROR = 'import_error'
    TYPE_ERROR = 'type_error'
    DEPENDENCY_ERROR = 'dependency_error'
    TEST_FAILURE = 'test_failure'
    PERMISSION_ERROR = 'permission_error'
    TIMEOUT = 'timeout'
    CONFIGURATION_ERROR = 'configuration_error'
    NETWORK_ERROR = 'network_error'
    UNKNOWN = 'unknown'


@dataclass
class FailureAnalysisResult:
    """Structured result from failure analysis phase."""

    category: ErrorCategory = ErrorCategory.UNKNOWN
    root_cause: str = ''
    original_error: str = ''
    stack_trace: str = ''
    affected_files: list[str] = field(default_factory=list)
    similar_past_errors: list[dict[str, Any]] = field(default_factory=list)
    suggested_fixes: list[dict[str, Any]] = field(default_factory=list)
    retry_recommended: bool = False
    retry_strategy: str = ''  # 'same_approach', 'different_approach', 'simplified', 'escalate'
    confidence: float = 0.0  # 0.0-1.0 how confident is the classification

    def to_dict(self) -> dict[str, Any]:
        return {
            'category': self.category.value,
            'root_cause': self.root_cause,
            'original_error': self.original_error[:500],
            'affected_files': self.affected_files,
            'similar_past_errors_count': len(self.similar_past_errors),
            'suggested_fixes_count': len(self.suggested_fixes),
            'retry_recommended': self.retry_recommended,
            'retry_strategy': self.retry_strategy,
            'confidence': self.confidence,
        }


@dataclass
class TestResult:
    """Structured test execution result."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_s: float = 0.0
    test_output: str = ''
    failures: list[dict[str, Any]] = field(default_factory=list)  # [{test_name, error, file, line}]
    error_types: dict[str, int] = field(default_factory=dict)  # {error_type: count}
    coverage_percent: float = 0.0

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.errors == 0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            'total': self.total,
            'passed': self.passed,
            'failed': self.failed,
            'skipped': self.skipped,
            'errors': self.errors,
            'duration_s': self.duration_s,
            'pass_rate': self.pass_rate,
            'failures': self.failures[:10],
            'error_types': self.error_types,
            'coverage_percent': self.coverage_percent,
        }


@dataclass
class TaskArtifact:
    """An artifact produced during task execution."""

    artifact_id: str = field(default_factory=lambda: f'art-{uuid.uuid4().hex[:12]}')
    artifact_type: ArtifactType = ArtifactType.LOG
    name: str = ''
    content: str = ''
    path: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        art_type = (
            self.artifact_type.value
            if isinstance(self.artifact_type, ArtifactType)
            else str(self.artifact_type)
        )
        return {
            'artifact_id': self.artifact_id,
            'artifact_type': art_type,
            'name': self.name,
            'content': self.content[:500] if self.content else '',
            'path': self.path,
            'metadata': self.metadata,
            'created_at': self.created_at,
        }


@dataclass
class TaskContext:
    """Context gathered before execution — repo state, memory, analysis results.

    Built during CONTEXT_BUILD and REPO_ANALYSIS phases and passed
    to all subsequent phases so they have full situational awareness.
    """

    task_id: str = ''
    repo_path: str = ''
    repo_name: str = ''
    branch_name: str = ''
    base_branch: str = 'main'

    # Repo intelligence results (populated during REPO_ANALYSIS)
    file_map: dict[str, Any] = field(default_factory=dict)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    test_map: dict[str, list[str]] = field(default_factory=dict)
    api_map: dict[str, dict[str, Any]] = field(default_factory=dict)
    impact_files: list[str] = field(default_factory=list)
    service_boundaries: list[dict[str, Any]] = field(default_factory=list)

    # Memory context (populated during CONTEXT_BUILD)
    error_memory: list[dict[str, Any]] = field(default_factory=list)
    fix_memory: list[dict[str, Any]] = field(default_factory=list)
    decision_memory: list[dict[str, Any]] = field(default_factory=list)
    repo_memory: dict[str, Any] = field(default_factory=dict)

    # Plan (populated during PLAN phase)
    plan_steps: list[dict[str, Any]] = field(default_factory=list)
    structured_plan: list['PlanStep'] = field(default_factory=list)

    # Execution tracking (populated during EXECUTE phase)
    step_results: list[dict[str, Any]] = field(default_factory=list)
    current_step_index: int = 0

    # Failure analysis (populated during FAILURE_ANALYSIS)
    failure_analysis: 'FailureAnalysisResult | None' = None

    # Test results (populated during TEST phase)
    test_result: 'TestResult | None' = None

    # Environment info
    runtime_id: str = ''
    working_dir: str = ''
    available_tools: list[str] = field(default_factory=list)

    # LLM config
    model_name: str = ''
    provider: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'repo_path': self.repo_path,
            'repo_name': self.repo_name,
            'branch_name': self.branch_name,
            'base_branch': self.base_branch,
            'file_count': len(self.file_map),
            'dependency_count': len(self.dependency_graph),
            'test_count': len(self.test_map),
            'impact_files': self.impact_files[:10],
            'plan_step_count': len(self.structured_plan),
            'step_results': self.step_results,
            'current_step_index': self.current_step_index,
            'available_tools': self.available_tools,
            'model_name': self.model_name,
            'provider': self.provider,
        }


@dataclass
class TaskResult:
    """Result of task execution — success/failure with details."""

    success: bool = False
    message: str = ''
    error: str = ''
    error_category: str = ''
    retry_count: int = 0
    max_retries: int = 3
    phase_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: list[TaskArtifact] = field(default_factory=list)
    duration_s: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0

    def add_artifact(self, artifact: TaskArtifact) -> None:
        self.artifacts.append(artifact)

    def set_phase_result(
        self, phase: str, success: bool, detail: str = ''
    ) -> None:
        self.phase_results[phase] = {
            'success': success,
            'detail': detail,
            'timestamp': time.time(),
        }

    @property
    def can_retry(self) -> bool:
        return not self.success and self.retry_count < self.max_retries

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'error': self.error,
            'error_category': self.error_category,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'phase_results': self.phase_results,
            'artifacts': [a.to_dict() for a in self.artifacts],
            'duration_s': self.duration_s,
            'tokens_used': self.tokens_used,
            'cost_usd': self.cost_usd,
        }


@dataclass
class Task:
    """A task in the execution engine — the fundamental unit of work.

    Every user request, issue, or automated trigger becomes a Task that
    flows through the execution engine's state machine.
    """

    task_id: str = field(default_factory=lambda: f'task-{uuid.uuid4().hex[:12]}')
    title: str = ''
    description: str = ''
    task_type: TaskType = TaskType.CUSTOM
    priority: TaskPriority = TaskPriority.NORMAL
    source: str = 'user'

    # Relationships
    parent_task_id: str = ''
    child_task_ids: list[str] = field(default_factory=list)

    # Execution state
    context: TaskContext = field(default_factory=TaskContext)
    result: TaskResult = field(default_factory=TaskResult)

    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0

    # Configuration
    max_retries: int = 3
    timeout_s: float = 600.0
    require_tests: bool = True
    require_review: bool = True
    auto_pr: bool = True

    # Tags and metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        if self.started_at == 0.0:
            return 0.0
        end = self.completed_at if self.completed_at > 0 else time.time()
        return end - self.started_at

    @property
    def is_subtask(self) -> bool:
        return bool(self.parent_task_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'title': self.title,
            'description': self.description[:200] if self.description else '',
            'task_type': self.task_type.value,
            'priority': self.priority.value,
            'source': self.source,
            'parent_task_id': self.parent_task_id,
            'child_task_ids': self.child_task_ids,
            'context': self.context.to_dict(),
            'result': self.result.to_dict(),
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'duration_s': self.duration_s,
            'max_retries': self.max_retries,
            'tags': self.tags,
        }
