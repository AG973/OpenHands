"""Worktree Manager — isolated worktrees for parallel task execution.

Each task can get its own git worktree, enabling parallel execution
without conflicts. Falls back to branch-only mode if worktrees
aren't supported or practical.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.workflow.git_manager import GitManager


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    path: str
    branch: str
    task_id: str
    created_at: float = field(default_factory=time.time)
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            'path': self.path,
            'branch': self.branch,
            'task_id': self.task_id,
            'created_at': self.created_at,
            'is_active': self.is_active,
        }


class WorktreeManager:
    """Manages git worktrees for isolated task execution.

    Usage:
        wm = WorktreeManager(git_manager, "/tmp/worktrees")
        info = wm.create("task-abc123", "task/123-fix-bug")
        # ... do work in info.path ...
        wm.remove("task-abc123")
    """

    def __init__(self, git: GitManager, worktree_base: str = '') -> None:
        self._git = git
        self._worktree_base = worktree_base or os.path.join(
            os.path.dirname(git.repo_path), '.worktrees'
        )
        self._worktrees: dict[str, WorktreeInfo] = {}

    def create(self, task_id: str, branch: str) -> WorktreeInfo:
        """Create a new worktree for a task.

        Args:
            task_id: The task ID
            branch: Branch name for the worktree

        Returns:
            WorktreeInfo with the worktree path
        """
        os.makedirs(self._worktree_base, exist_ok=True)
        worktree_path = os.path.join(self._worktree_base, task_id)

        if os.path.exists(worktree_path):
            logger.warning(
                f'[WorktreeManager] Worktree path exists, removing: {worktree_path}'
            )
            self._force_remove(worktree_path)

        result = self._git._run(
            ['git', 'worktree', 'add', worktree_path, branch]
        )
        if not result.success:
            # Fallback: try creating worktree with new branch
            result = self._git._run(
                ['git', 'worktree', 'add', '-b', branch, worktree_path]
            )
            if not result.success:
                raise RuntimeError(
                    f'Failed to create worktree: {result.stderr}'
                )

        info = WorktreeInfo(
            path=worktree_path,
            branch=branch,
            task_id=task_id,
        )
        self._worktrees[task_id] = info

        logger.info(
            f'[WorktreeManager] Created worktree at {worktree_path} '
            f'for task {task_id}'
        )
        return info

    def get(self, task_id: str) -> WorktreeInfo | None:
        """Get worktree info for a task."""
        return self._worktrees.get(task_id)

    def remove(self, task_id: str) -> bool:
        """Remove a worktree."""
        info = self._worktrees.get(task_id)
        if info is None:
            return False

        result = self._git._run(
            ['git', 'worktree', 'remove', info.path, '--force']
        )
        if result.success:
            info.is_active = False
            logger.info(f'[WorktreeManager] Removed worktree for task {task_id}')
        else:
            # Fallback: manual removal
            self._force_remove(info.path)
            self._git._run(['git', 'worktree', 'prune'])
            info.is_active = False

        return True

    def list_worktrees(self) -> list[WorktreeInfo]:
        """List all managed worktrees."""
        return list(self._worktrees.values())

    def cleanup_all(self) -> int:
        """Remove all worktrees. Returns count removed."""
        count = 0
        for task_id in list(self._worktrees.keys()):
            if self.remove(task_id):
                count += 1
        return count

    def _force_remove(self, path: str) -> None:
        """Force remove a worktree directory."""
        try:
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
        except Exception as e:
            logger.warning(f'[WorktreeManager] Force remove failed: {e}')
