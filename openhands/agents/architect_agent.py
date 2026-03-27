"""Architect Agent — makes design decisions and defines file-level changes.

The architect receives the plan from the PlannerAgent and translates it into
concrete architectural decisions: which files to create/modify, what patterns
to use, what constraints to enforce.

Patterns extracted from:
    - GPT-Pilot: TechLead architecture decisions
    - CrewAI: Role-based task delegation with backstory context
"""

from __future__ import annotations

from typing import Any

from openhands.agents.base_role import AgentRole, RoleContext, RoleName, RoleOutput
from openhands.core.logger import openhands_logger as logger


class ArchitectAgent(AgentRole):
    """Translates execution plans into architectural decisions.

    The architect:
    - Decides which files to create vs modify
    - Chooses implementation patterns
    - Defines module boundaries
    - Sets design constraints for the coder
    - Uses repo intelligence to ensure consistency
    """

    @property
    def role_name(self) -> RoleName:
        return RoleName.ARCHITECT

    @property
    def description(self) -> str:
        return (
            'Translates execution plans into concrete architectural decisions, '
            'file-level change specifications, and design constraints.'
        )

    def validate_input(self, context: RoleContext) -> list[str]:
        errors: list[str] = []
        if not context.plan_steps:
            errors.append('No execution plan found — PlannerAgent must run first')
        return errors

    def execute(self, context: RoleContext) -> RoleOutput:
        """Make architectural decisions based on the execution plan."""
        decisions: list[str] = []
        files_to_create: list[str] = []
        files_to_modify: list[str] = []
        constraints: list[str] = []

        # Analyze each plan step and make architectural decisions
        for step in context.plan_steps:
            action = step.get('action', '')
            file_path = step.get('file', '')

            if action == 'create' and file_path:
                files_to_create.append(file_path)
                decisions.append(f'Create new file: {file_path}')
            elif action == 'modify' and file_path:
                files_to_modify.append(file_path)
                decisions.append(f'Modify existing file: {file_path}')
            elif action == 'implement' and file_path:
                # Determine if file exists
                if file_path in context.file_map:
                    files_to_modify.append(file_path)
                    decisions.append(f'Modify: {file_path}')
                else:
                    files_to_create.append(file_path)
                    decisions.append(f'Create: {file_path}')

        # Infer design constraints from repo patterns
        constraints.extend(self._infer_constraints(context))

        # Detect potential architectural risks
        risks = self._detect_risks(context, files_to_create, files_to_modify)

        # Update context for downstream roles
        context.architecture_decisions = decisions
        context.files_to_create = files_to_create
        context.files_to_modify = files_to_modify
        context.design_constraints = constraints

        logger.info(
            f'[Architect] Decisions: {len(decisions)} changes '
            f'({len(files_to_create)} new, {len(files_to_modify)} modified), '
            f'{len(constraints)} constraints'
        )

        return RoleOutput(
            role=self.role_name,
            success=True,
            output_data={
                'decisions': decisions,
                'files_to_create': files_to_create,
                'files_to_modify': files_to_modify,
                'constraints': constraints,
                'risks': risks,
            },
            artifacts=[{
                'type': 'architecture_decision',
                'name': 'architecture_decisions',
                'content': {
                    'decisions': decisions,
                    'constraints': constraints,
                    'risks': risks,
                },
            }],
        )

    def _infer_constraints(self, context: RoleContext) -> list[str]:
        """Infer design constraints from the repo structure."""
        constraints: list[str] = []

        # Detect language-specific conventions
        file_map = context.file_map
        has_python = any(f.endswith('.py') for f in file_map)
        has_typescript = any(f.endswith('.ts') or f.endswith('.tsx') for f in file_map)
        has_tests = any('test' in f.lower() for f in file_map)

        if has_python:
            constraints.append('Follow existing Python code style and conventions')
            if has_tests:
                constraints.append('Add corresponding test files for new modules')

        if has_typescript:
            constraints.append('Follow existing TypeScript patterns and type definitions')

        # Check for configuration patterns
        if any('pyproject.toml' in f for f in file_map):
            constraints.append('Update pyproject.toml if adding new dependencies')
        if any('package.json' in f for f in file_map):
            constraints.append('Update package.json if adding new dependencies')

        # General constraints
        constraints.append('Preserve existing public APIs — no breaking changes')
        constraints.append('Use existing import patterns and module structure')

        return constraints

    def _detect_risks(
        self,
        context: RoleContext,
        files_to_create: list[str],
        files_to_modify: list[str],
    ) -> list[str]:
        """Detect architectural risks in the proposed changes."""
        risks: list[str] = []

        # High fan-out files are risky to modify
        dep_graph = context.dependency_graph
        for f in files_to_modify:
            dependents = dep_graph.get(f, [])
            if len(dependents) > 10:
                risks.append(
                    f'High-impact file {f}: {len(dependents)} dependents will be affected'
                )

        # Creating many new files is risky
        if len(files_to_create) > 10:
            risks.append(
                f'Large scope: {len(files_to_create)} new files — consider phased delivery'
            )

        # Cross-service changes
        if context.metadata.get('affected_services', []):
            services = context.metadata['affected_services']
            if len(services) > 1:
                risks.append(f'Cross-service change affecting: {", ".join(services)}')

        return risks
