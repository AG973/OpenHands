"""Service Mapper — detects service boundaries in the repository.

Identifies microservices, packages, and modules that form distinct
service boundaries. Used for understanding system architecture and
limiting change impact.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.repo_intel.indexer import FileCategory, RepoIndex


# Markers that indicate a service boundary
_SERVICE_MARKERS = {
    'Dockerfile',
    'docker-compose.yml',
    'docker-compose.yaml',
    'Procfile',
    'serverless.yml',
    'serverless.yaml',
    'app.yaml',
    'app.yml',
}

# Package markers that indicate a module boundary
_PACKAGE_MARKERS = {
    'package.json',
    'pyproject.toml',
    'setup.py',
    'setup.cfg',
    'Cargo.toml',
    'go.mod',
    'pom.xml',
    'build.gradle',
    'Gemfile',
    'composer.json',
}


@dataclass
class ServiceBoundary:
    """A detected service or module boundary."""

    name: str
    path: str  # Relative path to service root
    service_type: str = 'unknown'  # microservice, package, module, monolith
    marker_file: str = ''  # File that identified this as a service
    file_count: int = 0
    languages: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    test_dirs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'path': self.path,
            'service_type': self.service_type,
            'marker_file': self.marker_file,
            'file_count': self.file_count,
            'languages': self.languages,
            'entry_points': self.entry_points,
        }


class ServiceMapper:
    """Detects service boundaries in a repository.

    Usage:
        mapper = ServiceMapper()
        services = mapper.map(repo_index)
        for svc in services:
            print(svc.name, svc.path, svc.service_type)
    """

    def __init__(self) -> None:
        self._services: list[ServiceBoundary] = []

    def map(self, repo_index: RepoIndex) -> list[ServiceBoundary]:
        """Detect service boundaries in the repository.

        Args:
            repo_index: The indexed repository

        Returns:
            List of detected service boundaries
        """
        self._services.clear()
        seen_paths: set[str] = set()

        # Look for service markers (Dockerfile, docker-compose, etc.)
        for path, entry in repo_index.files.items():
            if entry.name in _SERVICE_MARKERS:
                svc_path = os.path.dirname(path) or '.'
                if svc_path not in seen_paths:
                    seen_paths.add(svc_path)
                    svc = self._build_service(
                        repo_index, svc_path, entry.name, 'microservice'
                    )
                    self._services.append(svc)

        # Look for package markers (package.json, pyproject.toml, etc.)
        for path, entry in repo_index.files.items():
            if entry.name in _PACKAGE_MARKERS:
                pkg_path = os.path.dirname(path) or '.'
                if pkg_path not in seen_paths:
                    seen_paths.add(pkg_path)
                    svc = self._build_service(
                        repo_index, pkg_path, entry.name, 'package'
                    )
                    self._services.append(svc)

        # If no services found, treat root as monolith
        if not self._services:
            svc = self._build_service(repo_index, '.', '', 'monolith')
            self._services.append(svc)

        logger.info(
            f'[ServiceMapper] Found {len(self._services)} service boundaries'
        )
        return self._services

    def get_service_for_file(self, file_path: str) -> ServiceBoundary | None:
        """Find which service a file belongs to."""
        best_match: ServiceBoundary | None = None
        best_depth = -1

        for svc in self._services:
            if file_path.startswith(svc.path) or svc.path == '.':
                depth = svc.path.count('/')
                if depth > best_depth:
                    best_depth = depth
                    best_match = svc

        return best_match

    def _build_service(
        self,
        repo_index: RepoIndex,
        svc_path: str,
        marker_file: str,
        service_type: str,
    ) -> ServiceBoundary:
        """Build a ServiceBoundary from a detected path."""
        name = os.path.basename(svc_path) if svc_path != '.' else repo_index.repo_name
        prefix = svc_path + '/' if svc_path != '.' else ''

        # Count files and detect languages
        file_count = 0
        languages: set[str] = set()
        entry_points: list[str] = []
        config_files: list[str] = []
        test_dirs: set[str] = set()

        for path, entry in repo_index.files.items():
            if not path.startswith(prefix) and svc_path != '.':
                continue

            file_count += 1
            if entry.language:
                languages.add(entry.language)

            if entry.category == FileCategory.CONFIG:
                config_files.append(path)

            if entry.category == FileCategory.TEST:
                test_dir = os.path.dirname(path)
                test_dirs.add(test_dir)

            # Detect entry points
            if entry.name in (
                'main.py',
                'app.py',
                '__main__.py',
                'index.ts',
                'index.js',
                'main.go',
                'Main.java',
                'main.rs',
                'server.py',
                'server.ts',
                'server.js',
            ):
                entry_points.append(path)

        return ServiceBoundary(
            name=name,
            path=svc_path,
            service_type=service_type,
            marker_file=marker_file,
            file_count=file_count,
            languages=sorted(languages),
            entry_points=entry_points,
            config_files=config_files[:10],
            test_dirs=sorted(test_dirs)[:10],
        )
