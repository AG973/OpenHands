"""Dependency Graph — maps import/require relationships between files.

Builds a directed graph of file dependencies by parsing import statements.
Used by the impact analysis module to determine change propagation.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.repo_intel.indexer import FileCategory, FileEntry, RepoIndex


# Import patterns for different languages
_PYTHON_IMPORT = re.compile(
    r'^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))', re.MULTILINE
)
_JS_TS_IMPORT = re.compile(
    r'(?:import\s+.*?from\s+[\'"](.+?)[\'"]|require\s*\(\s*[\'"](.+?)[\'"]\s*\))',
    re.MULTILINE,
)
_GO_IMPORT = re.compile(r'^\s*"(.+?)"', re.MULTILINE)
_RUST_USE = re.compile(r'^\s*use\s+([\w:]+)', re.MULTILINE)
_JAVA_IMPORT = re.compile(r'^\s*import\s+([\w.]+);', re.MULTILINE)


@dataclass
class DependencyEdge:
    """A directed edge in the dependency graph."""

    source: str  # File that imports
    target: str  # File being imported
    import_name: str = ''  # The import statement
    is_external: bool = False  # Whether the target is an external package


@dataclass
class DependencyNode:
    """A node in the dependency graph with its connections."""

    file_path: str
    imports: list[str] = field(default_factory=list)  # Files this file imports
    imported_by: list[str] = field(default_factory=list)  # Files that import this
    external_deps: list[str] = field(default_factory=list)  # External packages used

    @property
    def fan_out(self) -> int:
        """Number of files this file depends on."""
        return len(self.imports)

    @property
    def fan_in(self) -> int:
        """Number of files that depend on this file."""
        return len(self.imported_by)

    @property
    def coupling_score(self) -> float:
        """Higher score means more coupled (both fan-in and fan-out)."""
        return float(self.fan_in + self.fan_out)


class DependencyGraph:
    """Builds and queries a file dependency graph for a repository.

    Usage:
        graph = DependencyGraph()
        graph.build(repo_index)
        deps = graph.get_dependencies("src/main.py")
        dependents = graph.get_dependents("src/utils.py")
    """

    def __init__(self) -> None:
        self._nodes: dict[str, DependencyNode] = {}
        self._edges: list[DependencyEdge] = []
        self._repo_index: RepoIndex | None = None

    def build(self, repo_index: RepoIndex) -> None:
        """Build the dependency graph from a repo index.

        Args:
            repo_index: The indexed repository
        """
        self._repo_index = repo_index
        self._nodes.clear()
        self._edges.clear()

        # Initialize nodes for all source files
        for path, entry in repo_index.files.items():
            if entry.category in (FileCategory.SOURCE, FileCategory.TEST):
                self._nodes[path] = DependencyNode(file_path=path)

        # Parse imports for each file
        for path, entry in repo_index.files.items():
            if entry.category not in (FileCategory.SOURCE, FileCategory.TEST):
                continue

            imports = self._extract_imports(entry)
            node = self._nodes.get(path)
            if node is None:
                continue

            for imp_name, resolved_path, is_external in imports:
                if is_external:
                    node.external_deps.append(imp_name)
                elif resolved_path:
                    node.imports.append(resolved_path)
                    target_node = self._nodes.get(resolved_path)
                    if target_node:
                        target_node.imported_by.append(path)

                    self._edges.append(
                        DependencyEdge(
                            source=path,
                            target=resolved_path,
                            import_name=imp_name,
                            is_external=is_external,
                        )
                    )

        logger.info(
            f'[DependencyGraph] Built graph: '
            f'{len(self._nodes)} nodes, {len(self._edges)} edges'
        )

    def get_dependencies(self, file_path: str) -> list[str]:
        """Get all files that a given file depends on (imports)."""
        node = self._nodes.get(file_path)
        return list(node.imports) if node else []

    def get_dependents(self, file_path: str) -> list[str]:
        """Get all files that depend on (import) a given file."""
        node = self._nodes.get(file_path)
        return list(node.imported_by) if node else []

    def get_external_deps(self, file_path: str) -> list[str]:
        """Get external package dependencies for a file."""
        node = self._nodes.get(file_path)
        return list(node.external_deps) if node else []

    def get_most_coupled(self, limit: int = 20) -> list[tuple[str, float]]:
        """Get the most coupled files (highest fan-in + fan-out)."""
        scored = [
            (path, node.coupling_score)
            for path, node in self._nodes.items()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def get_transitive_dependencies(
        self, file_path: str, max_depth: int = 5
    ) -> set[str]:
        """Get all transitive dependencies (files depended on, recursively)."""
        visited: set[str] = set()
        self._walk_deps(file_path, visited, max_depth, 0, 'imports')
        visited.discard(file_path)
        return visited

    def get_transitive_dependents(
        self, file_path: str, max_depth: int = 5
    ) -> set[str]:
        """Get all transitive dependents (files that depend on this, recursively)."""
        visited: set[str] = set()
        self._walk_deps(file_path, visited, max_depth, 0, 'imported_by')
        visited.discard(file_path)
        return visited

    def to_dict(self) -> dict[str, list[str]]:
        """Export as adjacency list."""
        return {
            path: node.imports
            for path, node in self._nodes.items()
            if node.imports
        }

    def stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        if not self._nodes:
            return {'nodes': 0, 'edges': 0}

        fan_ins = [n.fan_in for n in self._nodes.values()]
        fan_outs = [n.fan_out for n in self._nodes.values()]

        return {
            'nodes': len(self._nodes),
            'edges': len(self._edges),
            'avg_fan_in': sum(fan_ins) / len(fan_ins) if fan_ins else 0,
            'avg_fan_out': sum(fan_outs) / len(fan_outs) if fan_outs else 0,
            'max_fan_in': max(fan_ins) if fan_ins else 0,
            'max_fan_out': max(fan_outs) if fan_outs else 0,
        }

    # ── Internal ────────────────────────────────────────────────────────

    def _walk_deps(
        self,
        file_path: str,
        visited: set[str],
        max_depth: int,
        current_depth: int,
        direction: str,
    ) -> None:
        """Walk dependency tree recursively."""
        if current_depth >= max_depth or file_path in visited:
            return
        visited.add(file_path)

        node = self._nodes.get(file_path)
        if node is None:
            return

        neighbors = getattr(node, direction, [])
        for neighbor in neighbors:
            self._walk_deps(neighbor, visited, max_depth, current_depth + 1, direction)

    def _extract_imports(
        self, entry: FileEntry
    ) -> list[tuple[str, str, bool]]:
        """Extract imports from a file.

        Returns:
            List of (import_name, resolved_path, is_external) tuples
        """
        try:
            with open(entry.absolute_path, 'r', errors='ignore') as f:
                content = f.read()
        except OSError:
            return []

        if entry.language == 'python':
            return self._parse_python_imports(content, entry)
        elif entry.language in ('javascript', 'typescript'):
            return self._parse_js_ts_imports(content, entry)
        elif entry.language == 'go':
            return self._parse_go_imports(content, entry)
        elif entry.language == 'java':
            return self._parse_java_imports(content, entry)
        elif entry.language == 'rust':
            return self._parse_rust_imports(content, entry)

        return []

    def _parse_python_imports(
        self, content: str, entry: FileEntry
    ) -> list[tuple[str, str, bool]]:
        """Parse Python import statements."""
        results: list[tuple[str, str, bool]] = []
        for match in _PYTHON_IMPORT.finditer(content):
            module = match.group(1) or match.group(2)
            if not module:
                continue

            resolved = self._resolve_python_import(module, entry.path)
            if resolved:
                results.append((module, resolved, False))
            else:
                results.append((module, '', True))

        return results

    def _parse_js_ts_imports(
        self, content: str, entry: FileEntry
    ) -> list[tuple[str, str, bool]]:
        """Parse JavaScript/TypeScript import statements."""
        results: list[tuple[str, str, bool]] = []
        for match in _JS_TS_IMPORT.finditer(content):
            module = match.group(1) or match.group(2)
            if not module:
                continue

            if module.startswith('.'):
                resolved = self._resolve_relative_import(module, entry.path)
                results.append((module, resolved, False))
            else:
                results.append((module, '', True))

        return results

    def _parse_go_imports(
        self, content: str, entry: FileEntry
    ) -> list[tuple[str, str, bool]]:
        """Parse Go import statements."""
        results: list[tuple[str, str, bool]] = []
        for match in _GO_IMPORT.finditer(content):
            module = match.group(1)
            results.append((module, '', True))
        return results

    def _parse_java_imports(
        self, content: str, entry: FileEntry
    ) -> list[tuple[str, str, bool]]:
        """Parse Java import statements."""
        results: list[tuple[str, str, bool]] = []
        for match in _JAVA_IMPORT.finditer(content):
            module = match.group(1)
            results.append((module, '', True))
        return results

    def _parse_rust_imports(
        self, content: str, entry: FileEntry
    ) -> list[tuple[str, str, bool]]:
        """Parse Rust use statements."""
        results: list[tuple[str, str, bool]] = []
        for match in _RUST_USE.finditer(content):
            module = match.group(1)
            results.append((module, '', True))
        return results

    def _resolve_python_import(
        self, module: str, source_path: str
    ) -> str:
        """Try to resolve a Python import to a file path in the repo."""
        if self._repo_index is None:
            return ''

        # Convert module.path to file path
        parts = module.split('.')
        candidates = [
            os.path.join(*parts) + '.py',
            os.path.join(*parts, '__init__.py'),
        ]

        for candidate in candidates:
            if candidate in self._repo_index.files:
                return candidate

        return ''

    def _resolve_relative_import(
        self, module: str, source_path: str
    ) -> str:
        """Try to resolve a relative import (./foo, ../bar)."""
        if self._repo_index is None:
            return ''

        source_dir = os.path.dirname(source_path)
        # Normalize the relative path
        rel = os.path.normpath(os.path.join(source_dir, module))

        # Try common extensions
        for ext in ('.ts', '.tsx', '.js', '.jsx', ''):
            candidate = rel + ext
            if candidate in self._repo_index.files:
                return candidate
            # Try index files
            index_candidate = os.path.join(rel, f'index{ext}')
            if index_candidate in self._repo_index.files:
                return index_candidate

        return ''
