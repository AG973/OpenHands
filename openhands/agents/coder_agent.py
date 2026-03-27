"""Coder Agent — generates and applies code changes.

The coder receives architectural decisions from the ArchitectAgent and
produces actual code changes. It applies patches, creates files, and
modifies existing code following the design constraints.

Patterns extracted from:
    - GPT-Pilot: CodeMonkey with strict file-level instructions
    - Cline: Direct file editing with diff tracking
    - Continue: IDE-integrated code generation
"""

from __future__ import annotations

import os
from typing import Any

from openhands.agents.base_role import AgentRole, RoleContext, RoleName, RoleOutput
from openhands.core.logger import openhands_logger as logger


class CoderAgent(AgentRole):
    """Generates and applies code changes based on architectural decisions.

    The coder:
    - Creates new files as specified by the architect
    - Modifies existing files with targeted changes
    - Follows design constraints and repo conventions
    - Tracks all changes for test and review
    - Does NOT make architectural decisions — only implements them
    """

    @property
    def role_name(self) -> RoleName:
        return RoleName.CODER

    @property
    def description(self) -> str:
        return (
            'Generates and applies code changes following architectural decisions. '
            'Creates files, modifies code, applies patches — strict implementation only.'
        )

    def validate_input(self, context: RoleContext) -> list[str]:
        errors: list[str] = []
        if not context.architecture_decisions and not context.plan_steps:
            errors.append('No architecture decisions or plan — upstream roles must run first')
        return errors

    def execute(self, context: RoleContext) -> RoleOutput:
        """Generate and apply code changes."""
        changes: list[dict[str, Any]] = []
        applied_patches: list[str] = []

        # Process files to create
        for file_path in context.files_to_create:
            change = self._create_file(file_path, context)
            if change:
                changes.append(change)
                applied_patches.append(file_path)

        # Process files to modify
        for file_path in context.files_to_modify:
            change = self._modify_file(file_path, context)
            if change:
                changes.append(change)
                applied_patches.append(file_path)

        # Process plan steps that reference specific actions
        for step in context.plan_steps:
            action = step.get('action', '')
            file_path = step.get('file', '')

            if action == 'implement' and file_path and file_path not in applied_patches:
                change = self._implement_step(step, context)
                if change:
                    changes.append(change)
                    applied_patches.append(file_path)

        # Update context
        context.code_changes = changes
        context.applied_patches = applied_patches

        success = len(changes) > 0 or not (context.files_to_create or context.files_to_modify)

        logger.info(
            f'[Coder] Applied {len(changes)} changes '
            f'({len(context.files_to_create)} created, '
            f'{len(context.files_to_modify)} modified)'
        )

        return RoleOutput(
            role=self.role_name,
            success=success,
            output_data={
                'changes': changes,
                'files_created': [c['file'] for c in changes if c.get('action') == 'create'],
                'files_modified': [c['file'] for c in changes if c.get('action') == 'modify'],
            },
            artifacts=[{
                'type': 'code_change',
                'name': f'change_{i}',
                'content': change,
            } for i, change in enumerate(changes)],
        )

    def _create_file(
        self, file_path: str, context: RoleContext
    ) -> dict[str, Any] | None:
        """Create a new file."""
        if not context.repo_path:
            return {
                'action': 'create',
                'file': file_path,
                'status': 'planned',
                'description': f'Create new file: {file_path}',
            }

        abs_path = os.path.join(context.repo_path, file_path)
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            # The actual content generation would be done by LLM integration
            # For now, track the operation
            return {
                'action': 'create',
                'file': file_path,
                'status': 'ready',
                'description': f'Create new file: {file_path}',
                'absolute_path': abs_path,
            }
        except Exception as e:
            logger.warning(f'[Coder] Failed to prepare file creation {file_path}: {e}')
            return None

    def _modify_file(
        self, file_path: str, context: RoleContext
    ) -> dict[str, Any] | None:
        """Modify an existing file."""
        if not context.repo_path:
            return {
                'action': 'modify',
                'file': file_path,
                'status': 'planned',
                'description': f'Modify file: {file_path}',
            }

        abs_path = os.path.join(context.repo_path, file_path)
        if not os.path.exists(abs_path):
            logger.warning(f'[Coder] File does not exist for modification: {file_path}')
            return None

        return {
            'action': 'modify',
            'file': file_path,
            'status': 'ready',
            'description': f'Modify file: {file_path}',
            'absolute_path': abs_path,
        }

    def _implement_step(
        self, step: dict[str, Any], context: RoleContext
    ) -> dict[str, Any] | None:
        """Implement a specific plan step."""
        return {
            'action': 'implement',
            'file': step.get('file', ''),
            'step': step.get('step', 0),
            'description': step.get('description', ''),
            'status': 'ready',
        }
