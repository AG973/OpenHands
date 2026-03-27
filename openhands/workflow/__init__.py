"""Engineering Workflow Engine — automated git, branch, test, and PR workflows.

This module handles all engineering workflow automation:
- Branch per task (isolated worktrees)
- Git operations (commit, push, merge)
- Patch application
- Test execution
- PR generation

NO DIRECT EDITING ON MAIN WORKSPACE — all work happens in isolated branches.
"""

from openhands.workflow.git_manager import GitManager
from openhands.workflow.branch_manager import BranchManager
from openhands.workflow.worktree_manager import WorktreeManager
from openhands.workflow.test_runner import WorkflowTestRunner
from openhands.workflow.patch_manager import PatchManager
from openhands.workflow.pr_generator import PRGenerator

__all__ = [
    'BranchManager',
    'GitManager',
    'PatchManager',
    'PRGenerator',
    'WorkflowTestRunner',
    'WorktreeManager',
]
