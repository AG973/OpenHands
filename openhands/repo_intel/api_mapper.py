"""API Mapper — discovers API routes and endpoints in the repository.

Parses source files to find HTTP endpoints, GraphQL resolvers,
gRPC services, and other API surface areas. Used for understanding
what the system exposes and for impact analysis.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.repo_intel.indexer import RepoIndex


# Patterns for detecting API routes
_FLASK_ROUTE = re.compile(
    r'@\w+\.route\(\s*[\'"]([^\'"]+)[\'"](?:.*?methods\s*=\s*\[([^\]]+)\])?',
    re.MULTILINE,
)
_FASTAPI_ROUTE = re.compile(
    r'@\w+\.(get|post|put|delete|patch|options|head)\(\s*[\'"]([^\'"]+)[\'"]',
    re.MULTILINE,
)
_EXPRESS_ROUTE = re.compile(
    r'(?:app|router)\.(get|post|put|delete|patch|all)\(\s*[\'"]([^\'"]+)[\'"]',
    re.MULTILINE,
)
_DJANGO_URL = re.compile(
    r'(?:path|re_path|url)\(\s*[\'"]([^\'"]+)[\'"]',
    re.MULTILINE,
)
_SPRING_MAPPING = re.compile(
    r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\(\s*(?:value\s*=\s*)?[\'"]([^\'"]+)[\'"]',
    re.MULTILINE,
)
_GO_HTTP = re.compile(
    r'(?:http\.HandleFunc|mux\.HandleFunc|r\.HandleFunc|Handle)\(\s*"([^"]+)"',
    re.MULTILINE,
)


@dataclass
class APIEndpoint:
    """A discovered API endpoint."""

    path: str
    method: str = 'GET'
    file_path: str = ''
    line_number: int = 0
    handler_name: str = ''
    framework: str = ''
    parameters: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'path': self.path,
            'method': self.method.upper(),
            'file_path': self.file_path,
            'line_number': self.line_number,
            'handler_name': self.handler_name,
            'framework': self.framework,
        }


class APIMapper:
    """Discovers API endpoints across a repository.

    Usage:
        mapper = APIMapper()
        endpoints = mapper.map(repo_index)
        for ep in endpoints:
            print(f"{ep.method} {ep.path} -> {ep.file_path}")
    """

    def __init__(self) -> None:
        self._endpoints: list[APIEndpoint] = []

    def map(self, repo_index: RepoIndex) -> list[APIEndpoint]:
        """Discover all API endpoints in the repository.

        Args:
            repo_index: The indexed repository

        Returns:
            List of discovered API endpoints
        """
        self._endpoints.clear()

        for path, entry in repo_index.files.items():
            if entry.language not in ('python', 'javascript', 'typescript', 'java', 'go'):
                continue

            try:
                with open(entry.absolute_path, 'r', errors='ignore') as f:
                    content = f.read()
            except OSError:
                continue

            endpoints = self._extract_endpoints(content, path, entry.language)
            self._endpoints.extend(endpoints)

        logger.info(f'[APIMapper] Found {len(self._endpoints)} API endpoints')
        return self._endpoints

    def get_endpoints_for_file(self, file_path: str) -> list[APIEndpoint]:
        """Get all endpoints defined in a specific file."""
        return [ep for ep in self._endpoints if ep.file_path == file_path]

    def get_endpoints_by_method(self, method: str) -> list[APIEndpoint]:
        """Get all endpoints with a specific HTTP method."""
        return [
            ep for ep in self._endpoints
            if ep.method.upper() == method.upper()
        ]

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Export as dict keyed by path."""
        result: dict[str, dict[str, Any]] = {}
        for ep in self._endpoints:
            key = f'{ep.method.upper()} {ep.path}'
            result[key] = ep.to_dict()
        return result

    def _extract_endpoints(
        self, content: str, file_path: str, language: str
    ) -> list[APIEndpoint]:
        """Extract API endpoints from file content."""
        endpoints: list[APIEndpoint] = []

        if language == 'python':
            endpoints.extend(self._extract_flask(content, file_path))
            endpoints.extend(self._extract_fastapi(content, file_path))
            endpoints.extend(self._extract_django(content, file_path))
        elif language in ('javascript', 'typescript'):
            endpoints.extend(self._extract_express(content, file_path))
        elif language == 'java':
            endpoints.extend(self._extract_spring(content, file_path))
        elif language == 'go':
            endpoints.extend(self._extract_go_http(content, file_path))

        return endpoints

    def _extract_flask(
        self, content: str, file_path: str
    ) -> list[APIEndpoint]:
        endpoints: list[APIEndpoint] = []
        for match in _FLASK_ROUTE.finditer(content):
            route = match.group(1)
            methods_str = match.group(2) or "'GET'"
            methods = re.findall(r"'(\w+)'", methods_str)
            for method in methods or ['GET']:
                endpoints.append(
                    APIEndpoint(
                        path=route,
                        method=method.upper(),
                        file_path=file_path,
                        framework='flask',
                    )
                )
        return endpoints

    def _extract_fastapi(
        self, content: str, file_path: str
    ) -> list[APIEndpoint]:
        endpoints: list[APIEndpoint] = []
        for match in _FASTAPI_ROUTE.finditer(content):
            method = match.group(1).upper()
            route = match.group(2)
            endpoints.append(
                APIEndpoint(
                    path=route,
                    method=method,
                    file_path=file_path,
                    framework='fastapi',
                )
            )
        return endpoints

    def _extract_express(
        self, content: str, file_path: str
    ) -> list[APIEndpoint]:
        endpoints: list[APIEndpoint] = []
        for match in _EXPRESS_ROUTE.finditer(content):
            method = match.group(1).upper()
            route = match.group(2)
            endpoints.append(
                APIEndpoint(
                    path=route,
                    method=method,
                    file_path=file_path,
                    framework='express',
                )
            )
        return endpoints

    def _extract_django(
        self, content: str, file_path: str
    ) -> list[APIEndpoint]:
        endpoints: list[APIEndpoint] = []
        for match in _DJANGO_URL.finditer(content):
            route = match.group(1)
            endpoints.append(
                APIEndpoint(
                    path=route,
                    method='ANY',
                    file_path=file_path,
                    framework='django',
                )
            )
        return endpoints

    def _extract_spring(
        self, content: str, file_path: str
    ) -> list[APIEndpoint]:
        endpoints: list[APIEndpoint] = []
        for match in _SPRING_MAPPING.finditer(content):
            route = match.group(1)
            endpoints.append(
                APIEndpoint(
                    path=route,
                    method='ANY',
                    file_path=file_path,
                    framework='spring',
                )
            )
        return endpoints

    def _extract_go_http(
        self, content: str, file_path: str
    ) -> list[APIEndpoint]:
        endpoints: list[APIEndpoint] = []
        for match in _GO_HTTP.finditer(content):
            route = match.group(1)
            endpoints.append(
                APIEndpoint(
                    path=route,
                    method='ANY',
                    file_path=file_path,
                    framework='go-http',
                )
            )
        return endpoints
