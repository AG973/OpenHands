"""Test Mapper — maps test files to the source files they cover.

Builds a bidirectional mapping between source files and their test files.
Used for determining which tests to run when a source file changes.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.repo_intel.indexer import FileCategory, RepoIndex


@dataclass
class TestMapping:
    """A mapping between a source file and its test files."""

    source_file: str
    test_files: list[str] = field(default_factory=list)
    test_framework: str = ''
    confidence: float = 0.0  # 0.0 to 1.0 — how confident we are in the mapping

    def to_dict(self) -> dict[str, Any]:
        return {
            'source_file': self.source_file,
            'test_files': self.test_files,
            'test_framework': self.test_framework,
            'confidence': self.confidence,
        }


class TestMapper:
    """Maps test files to source files they test.

    Uses naming conventions and import analysis to build the mapping.

    Usage:
        mapper = TestMapper()
        mappings = mapper.map(repo_index)
        tests = mapper.get_tests_for("src/auth/login.py")
    """

    def __init__(self) -> None:
        self._mappings: dict[str, TestMapping] = {}  # source -> TestMapping
        self._reverse: dict[str, list[str]] = {}  # test -> sources

    def map(self, repo_index: RepoIndex) -> dict[str, TestMapping]:
        """Build test-to-source mappings.

        Args:
            repo_index: The indexed repository

        Returns:
            Dict of source_path -> TestMapping
        """
        self._mappings.clear()
        self._reverse.clear()

        source_files = repo_index.get_source_files()
        test_files = repo_index.get_test_files()

        # Build mappings using naming conventions
        for source in source_files:
            mapping = TestMapping(source_file=source.path)

            for test in test_files:
                score = self._compute_match_score(source.path, test.path)
                if score > 0.3:
                    mapping.test_files.append(test.path)
                    mapping.confidence = max(mapping.confidence, score)

                    # Reverse mapping
                    if test.path not in self._reverse:
                        self._reverse[test.path] = []
                    self._reverse[test.path].append(source.path)

            # Detect test framework from test files
            if mapping.test_files:
                mapping.test_framework = self._detect_framework(
                    repo_index, mapping.test_files[0]
                )

            if mapping.test_files:
                self._mappings[source.path] = mapping

        logger.info(
            f'[TestMapper] Mapped {len(self._mappings)} source files to tests '
            f'({len(test_files)} test files found)'
        )
        return self._mappings

    def get_tests_for(self, source_path: str) -> list[str]:
        """Get test files that cover a source file."""
        mapping = self._mappings.get(source_path)
        return list(mapping.test_files) if mapping else []

    def get_sources_for_test(self, test_path: str) -> list[str]:
        """Get source files that a test file covers."""
        return list(self._reverse.get(test_path, []))

    def get_affected_tests(self, changed_files: list[str]) -> list[str]:
        """Get all test files that should run for a set of changed files."""
        tests: set[str] = set()
        for file_path in changed_files:
            mapping = self._mappings.get(file_path)
            if mapping:
                tests.update(mapping.test_files)
        return sorted(tests)

    def to_dict(self) -> dict[str, list[str]]:
        """Export as source -> test files dict."""
        return {
            source: mapping.test_files
            for source, mapping in self._mappings.items()
        }

    def _compute_match_score(
        self, source_path: str, test_path: str
    ) -> float:
        """Compute how likely a test file tests a source file.

        Uses naming conventions:
        - test_foo.py tests foo.py (0.9)
        - foo_test.py tests foo.py (0.9)
        - foo.test.ts tests foo.ts (0.9)
        - tests/test_foo.py tests src/foo.py (0.7)
        - Same directory bonus (0.1)
        """
        source_name = os.path.splitext(os.path.basename(source_path))[0]
        test_name = os.path.splitext(os.path.basename(test_path))[0]

        # Remove test extensions (.test, .spec)
        test_name_clean = re.sub(r'\.(test|spec)$', '', test_name)

        score = 0.0

        # Direct name match: test_foo <-> foo
        if test_name == f'test_{source_name}':
            score = 0.9
        elif test_name == f'{source_name}_test':
            score = 0.9
        elif test_name_clean == source_name:
            score = 0.9
        elif source_name in test_name:
            score = 0.5
        elif test_name_clean in source_name:
            score = 0.4

        # Same directory bonus
        if os.path.dirname(source_path) == os.path.dirname(test_path):
            score += 0.1

        # Parallel directory structure bonus (src/foo.py <-> tests/foo.py)
        source_parts = source_path.split('/')
        test_parts = test_path.split('/')
        if len(source_parts) > 1 and len(test_parts) > 1:
            # Check if they share subdirectory structure
            source_sub = '/'.join(source_parts[1:])
            test_sub = '/'.join(test_parts[1:])
            if source_sub == test_sub:
                score += 0.1

        return min(score, 1.0)

    def _detect_framework(
        self, repo_index: RepoIndex, test_path: str
    ) -> str:
        """Detect test framework from a test file."""
        entry = repo_index.files.get(test_path)
        if entry is None:
            return ''

        try:
            with open(entry.absolute_path, 'r', errors='ignore') as f:
                content = f.read(2000)  # Read first 2KB
        except OSError:
            return ''

        if entry.language == 'python':
            if 'import pytest' in content or '@pytest' in content:
                return 'pytest'
            if 'import unittest' in content:
                return 'unittest'
        elif entry.language in ('javascript', 'typescript'):
            if 'describe(' in content or 'it(' in content:
                if 'jest' in content.lower() or 'expect(' in content:
                    return 'jest'
                if 'mocha' in content.lower():
                    return 'mocha'
                return 'jest'  # Default for JS/TS
            if 'vitest' in content.lower():
                return 'vitest'
        elif entry.language == 'go':
            if 'testing.T' in content:
                return 'go-test'
        elif entry.language == 'java':
            if '@Test' in content:
                if 'org.junit.jupiter' in content:
                    return 'junit5'
                return 'junit'
        elif entry.language == 'rust':
            if '#[test]' in content:
                return 'cargo-test'

        return ''
