"""Planner Agent — decomposes tasks into executable step plans.

The planner is the FIRST role in the pipeline. It receives the raw task
description and repo context, then produces a structured execution plan.

Patterns extracted from:
    - GPT-Pilot: ProductOwner + TechLead decomposition
    - LangGraph: DAG workflow planning with checkpoints
    - Cline: Task decomposition with file-level granularity
"""

from __future__ import annotations

from typing import Any

from openhands.agents.base_role import AgentRole, RoleContext, RoleName, RoleOutput
from openhands.core.logger import openhands_logger as logger


class PlannerAgent(AgentRole):
    """Decomposes tasks into structured, executable step plans.

    The planner analyzes the task description against the repo context
    and produces a sequence of steps that the downstream roles will execute.

    Each step specifies:
    - What to do (action description)
    - Which files are involved
    - Dependencies on other steps
    - Expected outcome
    - Verification criteria
    """

    @property
    def role_name(self) -> RoleName:
        return RoleName.PLANNER

    @property
    def description(self) -> str:
        return (
            'Decomposes tasks into structured execution plans with '
            'file-level granularity, dependency ordering, and verification criteria.'
        )

    def validate_input(self, context: RoleContext) -> list[str]:
        errors: list[str] = []
        if not context.task_description and not context.task_title:
            errors.append('Task must have a title or description')
        return errors

    def execute(self, context: RoleContext) -> RoleOutput:
        """Create an execution plan for the task.

        Uses repo intelligence (file map, dependency graph, test map)
        to create a context-aware plan.
        """
        plan_steps: list[dict[str, Any]] = []

        # Step 1: Analyze task requirements
        task_analysis = self._analyze_task(context)

        # Step 2: Identify affected files using repo intelligence
        target_files = self._identify_target_files(context)

        # Step 3: Order operations by dependency
        ordered_ops = self._order_by_dependency(target_files, context)

        # Step 4: Build step-by-step plan
        step_num = 1

        # If we have specific files to modify, create per-file steps
        if ordered_ops:
            for file_path, operation in ordered_ops:
                plan_steps.append({
                    'step': step_num,
                    'action': operation,
                    'file': file_path,
                    'description': f'{operation} {file_path}',
                    'dependencies': [],
                    'verification': f'File {file_path} updated correctly',
                })
                step_num += 1
        else:
            # Generic plan based on task type
            plan_steps.extend(self._build_generic_plan(context, step_num))

        # Always add test and review steps
        plan_steps.append({
            'step': len(plan_steps) + 1,
            'action': 'run_tests',
            'file': '',
            'description': 'Run test suite to verify changes',
            'dependencies': [s['step'] for s in plan_steps],
            'verification': 'All tests pass',
        })
        plan_steps.append({
            'step': len(plan_steps) + 1,
            'action': 'review',
            'file': '',
            'description': 'Review all changes for quality and correctness',
            'dependencies': [len(plan_steps)],
            'verification': 'Code review passes',
        })

        # Store plan in context for downstream roles
        context.plan_steps = plan_steps

        logger.info(
            f'[Planner] Created {len(plan_steps)}-step plan for: '
            f'{context.task_title or context.task_id}'
        )

        return RoleOutput(
            role=self.role_name,
            success=True,
            output_data={
                'plan_steps': plan_steps,
                'task_analysis': task_analysis,
                'target_file_count': len(target_files),
            },
            artifacts=[{
                'type': 'plan',
                'name': 'execution_plan',
                'content': plan_steps,
            }],
        )

    def _analyze_task(self, context: RoleContext) -> dict[str, Any]:
        """Analyze the task to determine scope and complexity."""
        desc = (context.task_description or context.task_title).lower()

        # Classify task characteristics
        is_bug_fix = any(w in desc for w in ('bug', 'fix', 'error', 'crash', 'broken'))
        is_feature = any(w in desc for w in ('add', 'implement', 'create', 'build', 'new'))
        is_refactor = any(w in desc for w in ('refactor', 'cleanup', 'reorganize', 'improve'))
        is_test = any(w in desc for w in ('test', 'coverage', 'spec'))

        # Estimate complexity based on repo context
        file_count = len(context.file_map)
        complexity = 'simple'
        if file_count > 100:
            complexity = 'complex'
        elif file_count > 30:
            complexity = 'moderate'

        return {
            'is_bug_fix': is_bug_fix,
            'is_feature': is_feature,
            'is_refactor': is_refactor,
            'is_test': is_test,
            'complexity': complexity,
            'repo_file_count': file_count,
        }

    def _identify_target_files(
        self, context: RoleContext
    ) -> list[str]:
        """Identify files that need to be modified for the task."""
        targets: list[str] = []

        # Use impact files if already computed
        if context.impact_files:
            targets.extend(context.impact_files)

        # Use files_to_modify if set by upstream
        if context.files_to_modify:
            targets.extend(context.files_to_modify)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for f in targets:
            if f not in seen:
                seen.add(f)
                unique.append(f)

        return unique

    def _order_by_dependency(
        self,
        files: list[str],
        context: RoleContext,
    ) -> list[tuple[str, str]]:
        """Order file operations by dependency graph."""
        if not files:
            return []

        # Build operation list with dependency-aware ordering
        operations: list[tuple[str, str]] = []
        dep_graph = context.dependency_graph

        # Files that are depended on by others should be modified first
        dependency_count: dict[str, int] = {}
        for f in files:
            dependents = dep_graph.get(f, [])
            dependency_count[f] = len([d for d in dependents if d in files])

        # Sort: most depended-on files first (foundational changes first)
        sorted_files = sorted(files, key=lambda f: dependency_count.get(f, 0), reverse=True)

        for f in sorted_files:
            if f in context.files_to_create:
                operations.append((f, 'create'))
            else:
                operations.append((f, 'modify'))

        return operations

    def _build_generic_plan(
        self, context: RoleContext, start_step: int
    ) -> list[dict[str, Any]]:
        """Build a generic plan when no specific files are identified."""
        steps: list[dict[str, Any]] = []
        step = start_step

        steps.append({
            'step': step,
            'action': 'analyze',
            'file': '',
            'description': 'Analyze codebase to identify implementation targets',
            'dependencies': [],
            'verification': 'Target files identified',
        })
        step += 1

        steps.append({
            'step': step,
            'action': 'implement',
            'file': '',
            'description': f'Implement changes: {context.task_title}',
            'dependencies': [step - 1],
            'verification': 'Implementation complete',
        })

        return steps
