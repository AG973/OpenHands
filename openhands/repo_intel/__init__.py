"""Repo Intelligence Engine — deep repository understanding before code generation.

This module provides full repository awareness:
- File mapping and structure indexing
- Dependency graph extraction
- Service boundary detection
- API route mapping
- Test ownership mapping
- Change impact analysis

The repo intelligence engine runs BEFORE any code generation to give
the execution engine full situational awareness.
"""

from openhands.repo_intel.indexer import RepoIndexer
from openhands.repo_intel.dependency_graph import DependencyGraph
from openhands.repo_intel.service_mapper import ServiceMapper
from openhands.repo_intel.api_mapper import APIMapper
from openhands.repo_intel.test_mapper import TestMapper
from openhands.repo_intel.impact_analysis import ImpactAnalyzer

__all__ = [
    'APIMapper',
    'DependencyGraph',
    'ImpactAnalyzer',
    'RepoIndexer',
    'ServiceMapper',
    'TestMapper',
]
