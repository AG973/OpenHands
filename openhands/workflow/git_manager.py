"""Git Manager — safe git operations for the workflow engine.

All git operations are centralized here. No other module should
execute git commands directly. This ensures safety, logging, and
consistent error handling.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class GitResult:
    """Result of a git operation."""

    success: bool
    stdout: str = ''
    stderr: str = ''
    return_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'stdout': self.stdout[:500],
            'stderr': self.stderr[:500],
            'return_code': self.return_code,
        }


@dataclass
class GitStatus:
    """Current git status of a repository."""

    branch: str = ''
    clean: bool = True
    staged_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0


class GitManager:
    """Safe git operations for the workflow engine.

    Usage:
        git = GitManager("/path/to/repo")
        status = git.status()
        git.add(["src/main.py"])
        git.commit("Fix login bug")
        git.push()
    """

    def __init__(self, repo_path: str) -> None:
        self._repo_path = os.path.abspath(repo_path)
        if not os.path.isdir(os.path.join(self._repo_path, '.git')):
            raise ValueError(f'Not a git repository: {self._repo_path}')

    @property
    def repo_path(self) -> str:
        return self._repo_path

    def status(self) -> GitStatus:
        """Get current git status."""
        result = self._run(['git', 'status', '--porcelain', '-b'])
        if not result.success:
            return GitStatus()

        status = GitStatus()
        lines = result.stdout.strip().split('\n')

        for line in lines:
            if not line:
                continue
            if line.startswith('##'):
                # Parse branch info
                branch_info = line[3:]
                if '...' in branch_info:
                    status.branch = branch_info.split('...')[0]
                else:
                    status.branch = branch_info
            elif line.startswith('A ') or line.startswith('M ') or line.startswith('D '):
                status.staged_files.append(line[3:].strip())
            elif line.startswith(' M'):
                status.modified_files.append(line[3:].strip())
            elif line.startswith('??'):
                status.untracked_files.append(line[3:].strip())

        status.clean = (
            not status.staged_files
            and not status.modified_files
            and not status.untracked_files
        )

        return status

    def current_branch(self) -> str:
        """Get the current branch name."""
        result = self._run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        return result.stdout.strip() if result.success else ''

    def add(self, files: list[str]) -> GitResult:
        """Stage files for commit."""
        if not files:
            return GitResult(success=False, stderr='No files to add')
        return self._run(['git', 'add'] + files)

    def commit(self, message: str) -> GitResult:
        """Create a commit with the given message."""
        if not message:
            return GitResult(success=False, stderr='Commit message required')
        return self._run(['git', 'commit', '-m', message])

    def push(self, branch: str = '', remote: str = 'origin') -> GitResult:
        """Push to remote."""
        cmd = ['git', 'push', remote]
        if branch:
            cmd.append(branch)
        return self._run(cmd)

    def pull(self, branch: str = '', remote: str = 'origin') -> GitResult:
        """Pull from remote."""
        cmd = ['git', 'pull', remote]
        if branch:
            cmd.append(branch)
        return self._run(cmd)

    def checkout(self, branch: str, create: bool = False) -> GitResult:
        """Checkout a branch."""
        cmd = ['git', 'checkout']
        if create:
            cmd.append('-b')
        cmd.append(branch)
        return self._run(cmd)

    def diff(self, staged: bool = False, files: list[str] | None = None) -> str:
        """Get diff output."""
        cmd = ['git', 'diff']
        if staged:
            cmd.append('--staged')
        if files:
            cmd.extend(files)
        result = self._run(cmd)
        return result.stdout if result.success else ''

    def log(self, count: int = 10, oneline: bool = True) -> list[str]:
        """Get recent commit log."""
        cmd = ['git', 'log', f'-{count}']
        if oneline:
            cmd.append('--oneline')
        result = self._run(cmd)
        if result.success:
            return [line for line in result.stdout.strip().split('\n') if line]
        return []

    def stash(self) -> GitResult:
        """Stash current changes."""
        return self._run(['git', 'stash'])

    def stash_pop(self) -> GitResult:
        """Pop stashed changes."""
        return self._run(['git', 'stash', 'pop'])

    def get_changed_files(self, base_branch: str = 'main') -> list[str]:
        """Get files changed compared to a base branch."""
        result = self._run(
            ['git', 'diff', '--name-only', f'{base_branch}...HEAD']
        )
        if result.success:
            return [f for f in result.stdout.strip().split('\n') if f]
        return []

    def get_remote_url(self) -> str:
        """Get the remote URL."""
        result = self._run(['git', 'remote', 'get-url', 'origin'])
        return result.stdout.strip() if result.success else ''

    def _run(self, cmd: list[str]) -> GitResult:
        """Execute a git command safely."""
        try:
            proc = subprocess.run(
                cmd,
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            success = proc.returncode == 0
            if not success:
                logger.warning(
                    f'[GitManager] Command failed: {" ".join(cmd)}\n'
                    f'stderr: {proc.stderr[:200]}'
                )
            return GitResult(
                success=success,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            logger.error(f'[GitManager] Command timed out: {" ".join(cmd)}')
            return GitResult(success=False, stderr='Command timed out')
        except Exception as e:
            logger.error(f'[GitManager] Command error: {e}')
            return GitResult(success=False, stderr=str(e))
