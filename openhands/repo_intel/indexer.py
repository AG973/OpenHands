"""Repository Indexer — builds a full file map of the repository.

Walks the repository tree and creates a structured index of all files,
their types, sizes, and relationships. This is the foundation that all
other repo intelligence modules build on.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from openhands.core.logger import openhands_logger as logger


class FileCategory(Enum):
    """Classification of file types in a repository."""

    SOURCE = 'source'
    TEST = 'test'
    CONFIG = 'config'
    DOCUMENTATION = 'documentation'
    BUILD = 'build'
    ASSET = 'asset'
    DATA = 'data'
    GENERATED = 'generated'
    UNKNOWN = 'unknown'


# File extension to category mapping
_EXTENSION_CATEGORIES: dict[str, FileCategory] = {
    '.py': FileCategory.SOURCE,
    '.js': FileCategory.SOURCE,
    '.ts': FileCategory.SOURCE,
    '.tsx': FileCategory.SOURCE,
    '.jsx': FileCategory.SOURCE,
    '.java': FileCategory.SOURCE,
    '.go': FileCategory.SOURCE,
    '.rs': FileCategory.SOURCE,
    '.rb': FileCategory.SOURCE,
    '.php': FileCategory.SOURCE,
    '.c': FileCategory.SOURCE,
    '.cpp': FileCategory.SOURCE,
    '.h': FileCategory.SOURCE,
    '.cs': FileCategory.SOURCE,
    '.swift': FileCategory.SOURCE,
    '.kt': FileCategory.SOURCE,
    '.scala': FileCategory.SOURCE,
    '.json': FileCategory.CONFIG,
    '.yaml': FileCategory.CONFIG,
    '.yml': FileCategory.CONFIG,
    '.toml': FileCategory.CONFIG,
    '.ini': FileCategory.CONFIG,
    '.cfg': FileCategory.CONFIG,
    '.env': FileCategory.CONFIG,
    '.md': FileCategory.DOCUMENTATION,
    '.rst': FileCategory.DOCUMENTATION,
    '.txt': FileCategory.DOCUMENTATION,
    '.html': FileCategory.SOURCE,
    '.css': FileCategory.SOURCE,
    '.scss': FileCategory.SOURCE,
    '.less': FileCategory.SOURCE,
    '.sql': FileCategory.DATA,
    '.csv': FileCategory.DATA,
    '.png': FileCategory.ASSET,
    '.jpg': FileCategory.ASSET,
    '.svg': FileCategory.ASSET,
    '.gif': FileCategory.ASSET,
    '.ico': FileCategory.ASSET,
    '.lock': FileCategory.GENERATED,
}

# Directories to skip during indexing
_SKIP_DIRS = {
    '.git',
    '__pycache__',
    'node_modules',
    '.venv',
    'venv',
    '.env',
    '.tox',
    '.mypy_cache',
    '.pytest_cache',
    '.ruff_cache',
    'dist',
    'build',
    '.next',
    '.nuxt',
    'coverage',
    '.coverage',
    'htmlcov',
    'egg-info',
    '.eggs',
}

MAX_FILE_SIZE_BYTES = 1_000_000  # 1MB — skip files larger than this
MAX_FILES = 50_000  # Safety limit


@dataclass
class FileEntry:
    """A single file in the repository index."""

    path: str  # Relative to repo root
    absolute_path: str
    name: str
    extension: str
    category: FileCategory
    size_bytes: int = 0
    line_count: int = 0
    language: str = ''
    symbols: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'path': self.path,
            'name': self.name,
            'extension': self.extension,
            'category': self.category.value,
            'size_bytes': self.size_bytes,
            'line_count': self.line_count,
            'language': self.language,
        }


@dataclass
class RepoIndex:
    """Complete index of a repository."""

    repo_path: str
    repo_name: str = ''
    indexed_at: float = field(default_factory=time.time)
    files: dict[str, FileEntry] = field(default_factory=dict)
    directories: list[str] = field(default_factory=list)
    total_lines: int = 0
    total_size_bytes: int = 0

    @property
    def file_count(self) -> int:
        return len(self.files)

    def get_files_by_category(self, category: FileCategory) -> list[FileEntry]:
        return [f for f in self.files.values() if f.category == category]

    def get_files_by_extension(self, ext: str) -> list[FileEntry]:
        return [f for f in self.files.values() if f.extension == ext]

    def get_source_files(self) -> list[FileEntry]:
        return self.get_files_by_category(FileCategory.SOURCE)

    def get_test_files(self) -> list[FileEntry]:
        return self.get_files_by_category(FileCategory.TEST)

    def to_dict(self) -> dict[str, Any]:
        return {
            'repo_path': self.repo_path,
            'repo_name': self.repo_name,
            'indexed_at': self.indexed_at,
            'file_count': self.file_count,
            'total_lines': self.total_lines,
            'total_size_bytes': self.total_size_bytes,
            'categories': {
                cat.value: len(self.get_files_by_category(cat))
                for cat in FileCategory
            },
        }


class RepoIndexer:
    """Builds a complete file index of a repository.

    Usage:
        indexer = RepoIndexer()
        index = indexer.index("/path/to/repo")
        print(index.file_count, index.total_lines)
    """

    def __init__(self) -> None:
        self._skip_dirs = set(_SKIP_DIRS)
        self._max_file_size = MAX_FILE_SIZE_BYTES

    def index(self, repo_path: str, repo_name: str = '') -> RepoIndex:
        """Index a repository and return a complete file map.

        Args:
            repo_path: Absolute path to the repository root
            repo_name: Optional repository name

        Returns:
            RepoIndex with all files indexed
        """
        start_time = time.time()
        repo_path = os.path.abspath(repo_path)

        if not os.path.isdir(repo_path):
            raise ValueError(f'Repository path does not exist: {repo_path}')

        if not repo_name:
            repo_name = os.path.basename(repo_path)

        index = RepoIndex(repo_path=repo_path, repo_name=repo_name)

        file_count = 0
        for root, dirs, files in os.walk(repo_path):
            # Skip excluded directories
            dirs[:] = [
                d for d in dirs
                if d not in self._skip_dirs and not d.startswith('.')
            ]

            rel_dir = os.path.relpath(root, repo_path)
            if rel_dir != '.':
                index.directories.append(rel_dir)

            for filename in files:
                if file_count >= MAX_FILES:
                    logger.warning(f'File limit ({MAX_FILES}) reached for {repo_path}')
                    break

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, repo_path)

                entry = self._index_file(filepath, rel_path)
                if entry is not None:
                    index.files[rel_path] = entry
                    index.total_lines += entry.line_count
                    index.total_size_bytes += entry.size_bytes
                    file_count += 1

        duration = time.time() - start_time
        logger.info(
            f'[RepoIndexer] Indexed {repo_name}: '
            f'{index.file_count} files, {index.total_lines} lines '
            f'in {duration:.2f}s'
        )

        return index

    def _index_file(self, filepath: str, rel_path: str) -> FileEntry | None:
        """Index a single file."""
        try:
            stat = os.stat(filepath)
            if stat.st_size > self._max_file_size:
                return None
            if stat.st_size == 0:
                return None

            name = os.path.basename(filepath)
            ext = os.path.splitext(name)[1].lower()

            category = self._categorize_file(rel_path, ext, name)
            language = self._detect_language(ext)

            # Count lines for text files
            line_count = 0
            if category in (
                FileCategory.SOURCE,
                FileCategory.TEST,
                FileCategory.CONFIG,
                FileCategory.DOCUMENTATION,
            ):
                try:
                    with open(filepath, 'r', errors='ignore') as f:
                        line_count = sum(1 for _ in f)
                except (OSError, UnicodeDecodeError):
                    pass

            return FileEntry(
                path=rel_path,
                absolute_path=filepath,
                name=name,
                extension=ext,
                category=category,
                size_bytes=stat.st_size,
                line_count=line_count,
                language=language,
            )
        except OSError:
            return None

    def _categorize_file(
        self, rel_path: str, ext: str, name: str
    ) -> FileCategory:
        """Categorize a file based on path, extension, and name."""
        # Test files
        path_lower = rel_path.lower()
        if (
            '/test' in path_lower
            or '/tests/' in path_lower
            or name.startswith('test_')
            or name.endswith('_test.py')
            or name.endswith('.test.ts')
            or name.endswith('.test.js')
            or name.endswith('.spec.ts')
            or name.endswith('.spec.js')
        ):
            return FileCategory.TEST

        # Build files
        if name in (
            'Makefile',
            'Dockerfile',
            'docker-compose.yml',
            'Jenkinsfile',
            'Procfile',
        ):
            return FileCategory.BUILD

        # Config files
        if name in (
            '.gitignore',
            '.dockerignore',
            '.editorconfig',
            '.eslintrc',
            '.prettierrc',
            'tsconfig.json',
            'pyproject.toml',
            'setup.cfg',
            'setup.py',
            'package.json',
            'Cargo.toml',
            'go.mod',
        ):
            return FileCategory.CONFIG

        return _EXTENSION_CATEGORIES.get(ext, FileCategory.UNKNOWN)

    def _detect_language(self, ext: str) -> str:
        """Detect programming language from file extension."""
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.cs': 'csharp',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.html': 'html',
            '.css': 'css',
            '.sql': 'sql',
            '.sh': 'shell',
            '.bash': 'shell',
        }
        return lang_map.get(ext, '')
