"""Engineering OS — unified entry point wiring all 8 subsystems together.

This module is the top-level orchestrator that connects:
    Phase 1: Execution Engine (openhands/execution/)
    Phase 2: Repo Intelligence (openhands/repo_intel/)
    Phase 3: Workflow Engine (openhands/workflow/)
    Phase 4: Multi-Agent Roles (openhands/agents/)
    Phase 5: Memory System (openhands/memory/)
    Phase 6: Policy Engine (openhands/policy/)
    Phase 7: Observability (openhands/observability/)
    Phase 8: Platform (openhands/platform/)

Usage:
    from openhands.engineering_os import EngineeringOS

    eos = EngineeringOS(repo_path='/workspace/myapp')
    result = eos.run_task(
        title='Fix login bug',
        description='Users cannot log in with email',
        task_type='bug_fix',
    )
"""

from __future__ import annotations

import time
from typing import Any

from openhands.core.logger import openhands_logger as logger

# Phase 1: Execution Engine
from openhands.execution.task_engine import TaskEngine
from openhands.execution.task_models import Task, TaskContext, TaskType

# Phase 2: Repo Intelligence
from openhands.repo_intel.indexer import RepoIndexer
from openhands.repo_intel.dependency_graph import DependencyGraph
from openhands.repo_intel.api_mapper import APIMapper
from openhands.repo_intel.test_mapper import TestMapper
from openhands.repo_intel.service_mapper import ServiceMapper
from openhands.repo_intel.impact_analysis import ImpactAnalyzer

# Phase 3: Workflow Engine
from openhands.workflow.git_manager import GitManager
from openhands.workflow.branch_manager import BranchManager
from openhands.workflow.worktree_manager import WorktreeManager
from openhands.workflow.test_runner import WorkflowTestRunner
from openhands.workflow.patch_manager import PatchManager
from openhands.workflow.pr_generator import PRGenerator

# Phase 4: Multi-Agent Roles
from openhands.agents.base_role import RoleContext, ROLE_EXECUTION_ORDER
from openhands.agents.planner_agent import PlannerAgent
from openhands.agents.architect_agent import ArchitectAgent
from openhands.agents.coder_agent import CoderAgent
from openhands.agents.tester_agent import TesterAgent
from openhands.agents.debugger_agent import DebuggerAgent
from openhands.agents.reviewer_agent import ReviewerAgent
from openhands.agents.manager_agent import ManagerAgent

# Phase 5: Memory System
from openhands.memory.error_memory import ErrorMemory
from openhands.memory.fix_memory import FixMemory
from openhands.memory.repo_memory import RepoMemory
from openhands.memory.decision_memory import DecisionMemory

# Phase 6: Policy Engine
from openhands.policy.tool_selector import ToolSelector
from openhands.policy.risk_engine import RiskEngine
from openhands.policy.retry_policy import RetryPolicy
from openhands.policy.escalation_policy import EscalationPolicy

# Phase 7: Observability
from openhands.observability.execution_trace import ExecutionTrace
from openhands.observability.artifact_builder import ArtifactBuilder
from openhands.observability.log_collector import LogCollector, LogSource
from openhands.observability.metrics import MetricsCollector

# Phase 8: Platform
from openhands.platform.task_queue import TaskQueue
from openhands.platform.project_registry import ProjectRegistry, ProjectConfig
from openhands.platform.run_store import RunStore
from openhands.platform.artifact_store import ArtifactStore


# Task type mapping
_TASK_TYPE_MAP: dict[str, TaskType] = {
    'feature': TaskType.FEATURE,
    'bug_fix': TaskType.BUG_FIX,
    'refactor': TaskType.REFACTOR,
    'test': TaskType.TEST,
    'documentation': TaskType.DOCUMENTATION,
    'investigation': TaskType.INVESTIGATION,
    'deployment': TaskType.DEPLOYMENT,
    'review': TaskType.REVIEW,
    'custom': TaskType.CUSTOM,
}


class EngineeringOS:
    """Unified Engineering Operating System.

    Wires all 8 subsystems into a single coherent system.
    This is the ONLY execution path — no legacy paths.
    """

    def __init__(
        self,
        repo_path: str = '',
        project_name: str = '',
        storage_dir: str = '',
    ) -> None:
        self._repo_path = repo_path
        self._project_name = project_name or 'default'
        self._storage_dir = storage_dir
        self._initialized = False

        # Phase 1: Execution Engine
        self._task_engine = TaskEngine()

        # Phase 2: Repo Intelligence
        self._indexer = RepoIndexer()
        self._dep_graph = DependencyGraph()
        self._api_mapper = APIMapper()
        self._test_mapper = TestMapper()
        self._service_mapper = ServiceMapper()
        self._impact_analyzer = ImpactAnalyzer()

        # Phase 3: Workflow Engine
        self._git_manager = GitManager(repo_path) if repo_path else None
        self._branch_manager = BranchManager(repo_path) if repo_path else None
        self._worktree_manager = WorktreeManager(repo_path) if repo_path else None
        self._test_runner = WorkflowTestRunner()
        self._patch_manager = PatchManager(repo_path) if repo_path else None
        self._pr_generator = PRGenerator()

        # Phase 4: Multi-Agent Roles
        self._planner = PlannerAgent()
        self._architect = ArchitectAgent()
        self._coder = CoderAgent()
        self._tester = TesterAgent()
        self._debugger = DebuggerAgent()
        self._reviewer = ReviewerAgent()
        self._manager = ManagerAgent()

        # Register all roles with manager
        self._manager.register_all_roles([
            self._planner,
            self._architect,
            self._coder,
            self._tester,
            self._debugger,
            self._reviewer,
        ])

        # Phase 5: Memory System
        self._error_memory = ErrorMemory()
        self._fix_memory = FixMemory()
        self._repo_memory = RepoMemory()
        self._decision_memory = DecisionMemory()

        # Phase 6: Policy Engine
        self._tool_selector = ToolSelector()
        self._risk_engine = RiskEngine()
        self._retry_policy = RetryPolicy()
        self._escalation_policy = EscalationPolicy()

        # Phase 7: Observability
        self._log_collector = LogCollector()
        self._metrics = MetricsCollector()

        # Phase 8: Platform
        self._task_queue = TaskQueue()
        self._project_registry = ProjectRegistry()
        self._run_store = RunStore()
        self._artifact_store = ArtifactStore(storage_dir=storage_dir)

        logger.info('[EngineeringOS] All 8 subsystems initialized')

    def initialize(self) -> dict[str, Any]:
        """Initialize the system by indexing the repository.

        This MUST be called before running tasks. It:
        1. Indexes the repository file map
        2. Builds the dependency graph
        3. Maps API endpoints
        4. Maps test ownership
        5. Detects service boundaries
        6. Registers the project
        """
        if not self._repo_path:
            logger.warning('[EngineeringOS] No repo path — skipping initialization')
            return {'initialized': False, 'reason': 'no_repo_path'}

        start = time.time()
        self._log_collector.info(
            LogSource.SYSTEM, 'Initializing Engineering OS', task_id='system'
        )

        # Index repository
        file_map = self._indexer.index(self._repo_path)
        dep_graph = self._dep_graph.build(self._repo_path, file_map)
        api_map = self._api_mapper.map(self._repo_path, file_map)
        test_map = self._test_mapper.map(self._repo_path, file_map)
        services = self._service_mapper.map(self._repo_path)

        # Register project
        project = self._project_registry.register(
            name=self._project_name,
            repo_path=self._repo_path,
            config=ProjectConfig(
                language=self._detect_language(file_map),
            ),
        )

        # Set repo memory profile
        from openhands.memory.repo_memory import RepoProfile
        self._repo_memory.set_profile(RepoProfile(
            repo_path=self._repo_path,
            primary_language=self._detect_language(file_map),
            last_analyzed=time.time(),
        ))

        self._initialized = True
        duration = time.time() - start

        self._metrics.record_duration(
            'initialization', duration, labels={'project': self._project_name}
        )

        result = {
            'initialized': True,
            'duration_s': duration,
            'files_indexed': len(file_map),
            'dependencies': dep_graph.node_count if hasattr(dep_graph, 'node_count') else 0,
            'api_endpoints': len(api_map) if isinstance(api_map, list) else 0,
            'test_mappings': len(test_map) if isinstance(test_map, dict) else 0,
            'services': len(services) if isinstance(services, list) else 0,
            'project_id': project.project_id,
        }

        logger.info(
            f'[EngineeringOS] Initialized in {duration:.2f}s — '
            f'{result["files_indexed"]} files, '
            f'{result["api_endpoints"]} endpoints'
        )

        return result

    def run_task(
        self,
        title: str,
        description: str = '',
        task_type: str = 'feature',
        priority: str = 'normal',
    ) -> dict[str, Any]:
        """Run a task through the full Engineering OS pipeline.

        Pipeline:
            1. Submit to queue
            2. Create execution trace
            3. Build role context from repo intelligence + memory
            4. Run through agent pipeline (Plan → Arch → Code → Test → Debug → Review)
            5. Generate artifacts
            6. Record run in store

        Args:
            title: Task title
            description: Task description
            task_type: Type (feature, bug_fix, refactor, test, etc.)
            priority: Priority level

        Returns:
            Task execution result with all artifacts
        """
        task_start = time.time()

        # Create trace
        trace = ExecutionTrace(task_id=title)
        trace.record_phase_start('intake')

        # Log
        self._log_collector.info(
            LogSource.EXECUTION, f'Task started: {title}', task_id=title
        )
        self._metrics.increment('tasks_started', labels={'type': task_type})

        # Submit to queue
        queue_entry = self._task_queue.submit(
            title=title,
            description=description,
        )

        # Create run record
        run = self._run_store.create_run(
            task_id=queue_entry.task_id,
            title=title,
        )

        # Build role context
        context = self._build_role_context(title, description, task_type)
        trace.record_phase_end('intake', success=True)

        # Run through agent pipeline
        trace.record_phase_start('agent_pipeline')
        pipeline_result = self._manager.run(context)
        trace.record_phase_end('agent_pipeline', success=pipeline_result.success)

        # Build artifacts
        trace.record_phase_start('artifact_generation')
        builder = ArtifactBuilder(task_id=queue_entry.task_id)
        builder.add_execution_trace(trace.get_summary())

        if pipeline_result.artifacts:
            for art in pipeline_result.artifacts:
                builder.add_custom(
                    artifact_type=type(art).__name__ if not isinstance(art, dict) else 'dict',
                    name=art.get('name', 'artifact') if isinstance(art, dict) else 'artifact',
                    content=art,
                )

        bundle = builder.build(
            output_dir=f'{self._storage_dir}/{queue_entry.task_id}'
            if self._storage_dir else ''
        )
        trace.record_phase_end('artifact_generation', success=True)

        # Update run store
        self._run_store.update_status(
            run.run_id,
            __import__('openhands.platform.run_store', fromlist=['RunStatus']).RunStatus.COMPLETED
            if pipeline_result.success
            else __import__('openhands.platform.run_store', fromlist=['RunStatus']).RunStatus.FAILED,
        )
        self._run_store.complete_run(
            run.run_id, success=pipeline_result.success
        )

        # Complete queue entry
        self._task_queue.complete(queue_entry.queue_id, success=pipeline_result.success)

        # Metrics
        duration = time.time() - task_start
        self._metrics.record_duration('task_duration', duration, labels={'type': task_type})
        self._metrics.increment(
            'tasks_completed' if pipeline_result.success else 'tasks_failed',
            labels={'type': task_type},
        )

        result = {
            'success': pipeline_result.success,
            'task_id': queue_entry.task_id,
            'run_id': run.run_id,
            'duration_s': duration,
            'pipeline_output': pipeline_result.output_data,
            'artifact_count': bundle.artifact_count if hasattr(bundle, 'artifact_count') else len(bundle.artifacts),
            'trace_summary': trace.get_summary(),
            'error': pipeline_result.error,
        }

        logger.info(
            f'[EngineeringOS] Task {"COMPLETED" if pipeline_result.success else "FAILED"}: '
            f'{title} ({duration:.2f}s)'
        )

        return result

    def _build_role_context(
        self, title: str, description: str, task_type: str
    ) -> RoleContext:
        """Build role context from repo intelligence and memory."""
        # Get repo intelligence data
        file_map: dict[str, Any] = {}
        dep_graph: dict[str, Any] = {}
        test_map: dict[str, Any] = {}
        api_map: dict[str, Any] = {}

        if self._repo_path and self._initialized:
            try:
                indexed = self._indexer.index(self._repo_path)
                file_map = {
                    entry.path: entry
                    for entry in indexed
                } if isinstance(indexed, list) else indexed
            except Exception:
                pass

        # Get memory data
        error_memory_data = [
            e.to_dict() for e in self._error_memory.get_recurring_errors()
        ]
        fix_memory_data = [
            f.to_dict() for f in self._fix_memory.get_all_fixes()
        ]

        return RoleContext(
            task_id=title,
            task_title=title,
            task_description=description,
            task_type=task_type,
            repo_path=self._repo_path,
            file_map=file_map,
            dependency_graph=dep_graph,
            test_map=test_map,
            api_map=api_map,
            error_memory=error_memory_data,
            fix_memory=fix_memory_data,
        )

    def _detect_language(self, file_map: Any) -> str:
        """Detect the primary language of the repository."""
        extensions: dict[str, int] = {}
        entries = file_map if isinstance(file_map, list) else []
        for entry in entries:
            ext = getattr(entry, 'extension', '') or ''
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1

        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.rb': 'ruby',
            '.cpp': 'cpp',
            '.c': 'c',
        }

        if not extensions:
            return 'unknown'

        top_ext = max(extensions, key=extensions.get)  # type: ignore[arg-type]
        return lang_map.get(top_ext, 'unknown')

    # --- Subsystem access ---

    @property
    def task_engine(self) -> TaskEngine:
        return self._task_engine

    @property
    def error_memory(self) -> ErrorMemory:
        return self._error_memory

    @property
    def fix_memory(self) -> FixMemory:
        return self._fix_memory

    @property
    def repo_memory(self) -> RepoMemory:
        return self._repo_memory

    @property
    def decision_memory(self) -> DecisionMemory:
        return self._decision_memory

    @property
    def tool_selector(self) -> ToolSelector:
        return self._tool_selector

    @property
    def risk_engine(self) -> RiskEngine:
        return self._risk_engine

    @property
    def retry_policy(self) -> RetryPolicy:
        return self._retry_policy

    @property
    def metrics(self) -> MetricsCollector:
        return self._metrics

    @property
    def log_collector(self) -> LogCollector:
        return self._log_collector

    @property
    def task_queue(self) -> TaskQueue:
        return self._task_queue

    @property
    def project_registry(self) -> ProjectRegistry:
        return self._project_registry

    @property
    def run_store(self) -> RunStore:
        return self._run_store

    @property
    def artifact_store(self) -> ArtifactStore:
        return self._artifact_store

    def stats(self) -> dict[str, Any]:
        """Get comprehensive system statistics."""
        return {
            'initialized': self._initialized,
            'repo_path': self._repo_path,
            'memory': {
                'errors': self._error_memory.stats(),
                'fixes': self._fix_memory.stats(),
                'repo': self._repo_memory.stats(self._repo_path) if self._repo_path else {},
                'decisions': self._decision_memory.stats(),
            },
            'policy': {
                'tools': self._tool_selector.stats(),
                'risk': self._risk_engine.stats(),
                'retry': self._retry_policy.stats(),
                'escalation': self._escalation_policy.stats(),
            },
            'platform': {
                'queue': self._task_queue.stats(),
                'projects': self._project_registry.stats(),
                'runs': self._run_store.stats(),
                'artifacts': self._artifact_store.stats(),
            },
            'metrics': self._metrics.get_report(),
        }
