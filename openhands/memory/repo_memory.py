"""Repo Memory — persistent knowledge about repository structure and patterns.

Stores learned patterns about a repository: hot files, common change patterns,
architecture conventions, dependency quirks, and test reliability data.

This memory persists across tasks so the system gets smarter about each
repo over time. Memory MUST change decisions — repo memory influences
file selection, risk assessment, and approach planning.

Patterns extracted from:
    - Continue: Codebase indexing with embeddings
    - OpenHands: Workspace context and microagent knowledge
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class FileKnowledge:
    """Accumulated knowledge about a specific file."""

    file_path: str = ''
    change_count: int = 0
    last_modified: float = 0.0
    error_prone: bool = False
    error_count: int = 0
    test_reliability: float = 1.0  # 0.0 = always fails, 1.0 = always passes
    common_changes: list[str] = field(default_factory=list)
    dependencies_stable: bool = True
    notes: list[str] = field(default_factory=list)


@dataclass
class RepoProfile:
    """Accumulated knowledge about a repository."""

    repo_path: str = ''
    primary_language: str = ''
    frameworks: list[str] = field(default_factory=list)
    test_framework: str = ''
    build_command: str = ''
    test_command: str = ''
    lint_command: str = ''
    entry_points: list[str] = field(default_factory=list)
    hot_files: list[str] = field(default_factory=list)  # Frequently changed
    fragile_files: list[str] = field(default_factory=list)  # Error-prone
    architecture_notes: list[str] = field(default_factory=list)
    last_analyzed: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'repo_path': self.repo_path,
            'primary_language': self.primary_language,
            'frameworks': self.frameworks,
            'test_framework': self.test_framework,
            'hot_files': self.hot_files[:10],
            'fragile_files': self.fragile_files[:10],
        }


class RepoMemory:
    """Persistent repository knowledge that influences decision-making.

    Usage:
        mem = RepoMemory()
        mem.set_profile(RepoProfile(
            repo_path='/workspace/myapp',
            primary_language='python',
            test_framework='pytest',
        ))
        mem.record_file_change('/workspace/myapp', 'src/auth.py')
        mem.record_file_error('/workspace/myapp', 'src/auth.py')

        # Later, when planning:
        profile = mem.get_profile('/workspace/myapp')
        hot = mem.get_hot_files('/workspace/myapp')
        fragile = mem.get_fragile_files('/workspace/myapp')
    """

    def __init__(self) -> None:
        self._profiles: dict[str, RepoProfile] = {}
        self._file_knowledge: dict[str, dict[str, FileKnowledge]] = {}

    def set_profile(self, profile: RepoProfile) -> None:
        """Set or update a repo profile."""
        self._profiles[profile.repo_path] = profile
        logger.info(
            f'[RepoMemory] Profile set: {profile.repo_path} '
            f'({profile.primary_language})'
        )

    def get_profile(self, repo_path: str) -> RepoProfile | None:
        """Get the profile for a repository."""
        return self._profiles.get(repo_path)

    def record_file_change(self, repo_path: str, file_path: str) -> None:
        """Record that a file was changed (tracks hot files)."""
        fk = self._get_or_create_fk(repo_path, file_path)
        fk.change_count += 1
        fk.last_modified = time.time()

        # Update hot files in profile
        profile = self._profiles.get(repo_path)
        if profile:
            self._update_hot_files(profile, repo_path)

    def record_file_error(self, repo_path: str, file_path: str, error: str = '') -> None:
        """Record that a file caused an error."""
        fk = self._get_or_create_fk(repo_path, file_path)
        fk.error_count += 1
        fk.error_prone = fk.error_count >= 3
        if error:
            fk.notes.append(f'Error: {error[:100]}')

        # Update fragile files in profile
        profile = self._profiles.get(repo_path)
        if profile:
            self._update_fragile_files(profile, repo_path)

    def record_test_result(
        self, repo_path: str, file_path: str, passed: bool
    ) -> None:
        """Record a test result for a file (updates reliability score)."""
        fk = self._get_or_create_fk(repo_path, file_path)
        # Exponential moving average
        alpha = 0.3
        result = 1.0 if passed else 0.0
        fk.test_reliability = alpha * result + (1 - alpha) * fk.test_reliability

    def get_hot_files(self, repo_path: str, limit: int = 10) -> list[str]:
        """Get the most frequently changed files.

        Hot files indicate areas of active development — useful for
        prioritizing analysis and impact assessment.
        """
        files = self._file_knowledge.get(repo_path, {})
        sorted_files = sorted(
            files.values(),
            key=lambda f: f.change_count,
            reverse=True,
        )
        return [f.file_path for f in sorted_files[:limit]]

    def get_fragile_files(self, repo_path: str, limit: int = 10) -> list[str]:
        """Get error-prone files.

        Fragile files need extra care — changes to these should trigger
        more thorough testing and review.
        """
        files = self._file_knowledge.get(repo_path, {})
        sorted_files = sorted(
            files.values(),
            key=lambda f: f.error_count,
            reverse=True,
        )
        return [f.file_path for f in sorted_files[:limit] if f.error_count > 0]

    def get_unreliable_tests(
        self, repo_path: str, threshold: float = 0.7
    ) -> list[str]:
        """Get test files with low reliability scores.

        Unreliable tests may need to be investigated separately
        rather than blocking the pipeline.
        """
        files = self._file_knowledge.get(repo_path, {})
        return [
            f.file_path for f in files.values()
            if f.test_reliability < threshold and 'test' in f.file_path.lower()
        ]

    def should_increase_scrutiny(self, repo_path: str, file_path: str) -> bool:
        """Determine if a file needs extra scrutiny based on history.

        This is where MEMORY CHANGES DECISIONS — files with high error
        rates get more thorough review and testing.
        """
        fk = self._file_knowledge.get(repo_path, {}).get(file_path)
        if fk is None:
            return False

        return fk.error_prone or fk.test_reliability < 0.5

    def add_architecture_note(self, repo_path: str, note: str) -> None:
        """Add an architecture note for a repository."""
        profile = self._profiles.get(repo_path)
        if profile:
            profile.architecture_notes.append(note)

    def stats(self, repo_path: str) -> dict[str, Any]:
        """Get memory statistics for a repository."""
        profile = self._profiles.get(repo_path)
        files = self._file_knowledge.get(repo_path, {})
        return {
            'has_profile': profile is not None,
            'files_tracked': len(files),
            'hot_files': self.get_hot_files(repo_path, 5),
            'fragile_files': self.get_fragile_files(repo_path, 5),
            'primary_language': profile.primary_language if profile else '',
        }

    def _get_or_create_fk(self, repo_path: str, file_path: str) -> FileKnowledge:
        """Get or create file knowledge entry."""
        if repo_path not in self._file_knowledge:
            self._file_knowledge[repo_path] = {}
        repo_files = self._file_knowledge[repo_path]

        if file_path not in repo_files:
            repo_files[file_path] = FileKnowledge(file_path=file_path)
        return repo_files[file_path]

    def _update_hot_files(self, profile: RepoProfile, repo_path: str) -> None:
        """Update the hot files list in the profile."""
        profile.hot_files = self.get_hot_files(repo_path, 20)

    def _update_fragile_files(self, profile: RepoProfile, repo_path: str) -> None:
        """Update the fragile files list in the profile."""
        profile.fragile_files = self.get_fragile_files(repo_path, 20)
