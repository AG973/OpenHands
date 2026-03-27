"""Branch Manager — creates and manages task-specific branches.

Every task gets its own branch. This ensures isolation and clean
git history. Branch naming follows a deterministic convention.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.workflow.git_manager import GitManager, GitResult


@dataclass
class BranchInfo:
    """Information about a task branch."""

    branch_name: str
    task_id: str
    base_branch: str = 'main'
    created_at: float = field(default_factory=time.time)
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            'branch_name': self.branch_name,
            'task_id': self.task_id,
            'base_branch': self.base_branch,
            'created_at': self.created_at,
            'is_active': self.is_active,
        }


class BranchManager:
    """Manages task-specific branches.

    Usage:
        bm = BranchManager(git_manager)
        info = bm.create_task_branch("task-abc123", base="main")
        # ... do work ...
        bm.cleanup_branch("task-abc123")
    """

    def __init__(self, git: GitManager) -> None:
        self._git = git
        self._branches: dict[str, BranchInfo] = {}

    def create_task_branch(
        self,
        task_id: str,
        base_branch: str = 'main',
        prefix: str = 'task',
    ) -> BranchInfo:
        """Create a new branch for a task.

        Args:
            task_id: The task ID
            base_branch: Branch to base off of
            prefix: Branch name prefix

        Returns:
            BranchInfo for the created branch
        """
        timestamp = int(time.time())
        branch_name = f'{prefix}/{timestamp}-{task_id}'

        # Ensure we're on the base branch first
        self._git.checkout(base_branch)
        self._git.pull(base_branch)

        # Create and checkout the task branch
        result = self._git.checkout(branch_name, create=True)
        if not result.success:
            raise RuntimeError(
                f'Failed to create branch {branch_name}: {result.stderr}'
            )

        info = BranchInfo(
            branch_name=branch_name,
            task_id=task_id,
            base_branch=base_branch,
        )
        self._branches[task_id] = info

        logger.info(
            f'[BranchManager] Created branch {branch_name} for task {task_id}'
        )
        return info

    def get_branch(self, task_id: str) -> BranchInfo | None:
        """Get branch info for a task."""
        return self._branches.get(task_id)

    def switch_to_task(self, task_id: str) -> bool:
        """Switch to a task's branch."""
        info = self._branches.get(task_id)
        if info is None:
            return False
        result = self._git.checkout(info.branch_name)
        return result.success

    def cleanup_branch(self, task_id: str) -> bool:
        """Clean up a task branch after completion."""
        info = self._branches.get(task_id)
        if info is None:
            return False

        # Switch to base branch first
        self._git.checkout(info.base_branch)

        # Delete the task branch
        result = self._git._run(
            ['git', 'branch', '-d', info.branch_name]
        )
        if result.success:
            info.is_active = False
            logger.info(
                f'[BranchManager] Cleaned up branch {info.branch_name}'
            )
        return result.success

    def list_branches(self) -> list[BranchInfo]:
        """List all managed branches."""
        return list(self._branches.values())

    def get_active_branches(self) -> list[BranchInfo]:
        """Get all active (non-cleaned-up) branches."""
        return [b for b in self._branches.values() if b.is_active]
