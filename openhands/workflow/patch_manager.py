"""Patch Manager — applies and manages code patches safely.

Handles unified diff application, conflict detection, and rollback.
Used by the execution engine when applying code changes.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class PatchResult:
    """Result of a patch application."""

    success: bool = False
    files_modified: list[str] = field(default_factory=list)
    files_failed: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    stdout: str = ''
    stderr: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'files_modified': self.files_modified,
            'files_failed': self.files_failed,
            'conflicts': self.conflicts,
        }


class PatchManager:
    """Applies and manages code patches.

    Usage:
        pm = PatchManager("/path/to/repo")
        result = pm.apply_diff(diff_content)
        if not result.success:
            pm.rollback()
    """

    def __init__(self, repo_path: str) -> None:
        self._repo_path = os.path.abspath(repo_path)
        self._applied_patches: list[str] = []

    def apply_diff(self, diff_content: str) -> PatchResult:
        """Apply a unified diff to the repository.

        Args:
            diff_content: Unified diff content

        Returns:
            PatchResult with success/failure details
        """
        if not diff_content.strip():
            return PatchResult(success=True, stdout='Empty diff, nothing to apply')

        # Write diff to temp file
        patch_file = os.path.join(self._repo_path, '.tmp_patch')
        try:
            with open(patch_file, 'w') as f:
                f.write(diff_content)

            # Try to apply
            result = self._run_patch(patch_file)
            if result.success:
                self._applied_patches.append(diff_content)

            return result
        finally:
            if os.path.exists(patch_file):
                os.unlink(patch_file)

    def apply_file_change(
        self, file_path: str, new_content: str
    ) -> PatchResult:
        """Apply a direct file content change.

        Args:
            file_path: Relative path to the file
            new_content: New file content

        Returns:
            PatchResult
        """
        abs_path = os.path.join(self._repo_path, file_path)
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'w') as f:
                f.write(new_content)

            return PatchResult(
                success=True,
                files_modified=[file_path],
            )
        except Exception as e:
            return PatchResult(
                success=False,
                files_failed=[file_path],
                stderr=str(e),
            )

    def check_conflicts(self, diff_content: str) -> list[str]:
        """Check if a diff would cause conflicts without applying it.

        Returns:
            List of conflicting file paths (empty = no conflicts)
        """
        if not diff_content.strip():
            return []

        patch_file = os.path.join(self._repo_path, '.tmp_patch_check')
        try:
            with open(patch_file, 'w') as f:
                f.write(diff_content)

            proc = subprocess.run(
                ['git', 'apply', '--check', patch_file],
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                # Parse conflicting files from stderr
                conflicts: list[str] = []
                for line in proc.stderr.split('\n'):
                    if 'error:' in line and 'patch' in line:
                        conflicts.append(line.strip())
                return conflicts or [proc.stderr[:200]]
            return []
        except Exception as e:
            return [str(e)]
        finally:
            if os.path.exists(patch_file):
                os.unlink(patch_file)

    def rollback_last(self) -> bool:
        """Rollback the last applied patch."""
        if not self._applied_patches:
            return False

        last_patch = self._applied_patches.pop()
        patch_file = os.path.join(self._repo_path, '.tmp_rollback')
        try:
            with open(patch_file, 'w') as f:
                f.write(last_patch)

            proc = subprocess.run(
                ['git', 'apply', '--reverse', patch_file],
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return proc.returncode == 0
        except Exception:
            return False
        finally:
            if os.path.exists(patch_file):
                os.unlink(patch_file)

    def _run_patch(self, patch_file: str) -> PatchResult:
        """Apply a patch file using git apply."""
        try:
            proc = subprocess.run(
                ['git', 'apply', '--verbose', patch_file],
                cwd=self._repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if proc.returncode == 0:
                # Parse modified files from verbose output
                modified: list[str] = []
                for line in proc.stderr.split('\n'):
                    if line.startswith('Applied patch'):
                        modified.append(line)
                return PatchResult(
                    success=True,
                    files_modified=modified,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                )
            else:
                return PatchResult(
                    success=False,
                    stderr=proc.stderr,
                    stdout=proc.stdout,
                )
        except subprocess.TimeoutExpired:
            return PatchResult(
                success=False,
                stderr='Patch application timed out',
            )
        except Exception as e:
            return PatchResult(
                success=False,
                stderr=str(e),
            )
