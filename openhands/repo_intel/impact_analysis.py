"""Impact Analysis — determines the blast radius of code changes.

Given a set of changed files, computes which other files, tests,
services, and API endpoints are affected. This drives intelligent
test selection and review scoping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger
from openhands.repo_intel.dependency_graph import DependencyGraph
from openhands.repo_intel.service_mapper import ServiceBoundary, ServiceMapper
from openhands.repo_intel.test_mapper import TestMapper


@dataclass
class ImpactReport:
    """Report of change impact across the repository."""

    changed_files: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    affected_endpoints: list[str] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 (safe) to 1.0 (high risk)
    risk_factors: list[str] = field(default_factory=list)

    @property
    def total_affected(self) -> int:
        return len(self.affected_files) + len(self.affected_tests)

    def to_dict(self) -> dict[str, Any]:
        return {
            'changed_files': self.changed_files,
            'affected_files': self.affected_files[:50],
            'affected_tests': self.affected_tests[:50],
            'affected_services': self.affected_services,
            'affected_endpoints': self.affected_endpoints[:20],
            'risk_score': self.risk_score,
            'risk_factors': self.risk_factors,
            'total_affected': self.total_affected,
        }


class ImpactAnalyzer:
    """Analyzes the impact of code changes across the repository.

    Usage:
        analyzer = ImpactAnalyzer(dep_graph, test_mapper, service_mapper)
        report = analyzer.analyze(["src/auth/login.py", "src/auth/token.py"])
        print(report.risk_score, report.affected_tests)
    """

    def __init__(
        self,
        dependency_graph: DependencyGraph | None = None,
        test_mapper: TestMapper | None = None,
        service_mapper: ServiceMapper | None = None,
    ) -> None:
        self._dep_graph = dependency_graph
        self._test_mapper = test_mapper
        self._service_mapper = service_mapper

    def set_dependency_graph(self, dep_graph: DependencyGraph) -> None:
        self._dep_graph = dep_graph

    def set_test_mapper(self, test_mapper: TestMapper) -> None:
        self._test_mapper = test_mapper

    def set_service_mapper(self, service_mapper: ServiceMapper) -> None:
        self._service_mapper = service_mapper

    def analyze(
        self, changed_files: list[str], max_depth: int = 3
    ) -> ImpactReport:
        """Analyze the impact of a set of file changes.

        Args:
            changed_files: List of changed file paths (relative to repo root)
            max_depth: Maximum depth for transitive dependency traversal

        Returns:
            ImpactReport with all affected files, tests, and services
        """
        report = ImpactReport(changed_files=list(changed_files))

        # 1. Find transitively affected files via dependency graph
        if self._dep_graph:
            affected: set[str] = set()
            for f in changed_files:
                deps = self._dep_graph.get_transitive_dependents(f, max_depth)
                affected.update(deps)
            # Remove the changed files themselves
            affected -= set(changed_files)
            report.affected_files = sorted(affected)

        # 2. Find affected tests
        if self._test_mapper:
            all_affected = list(changed_files) + report.affected_files
            report.affected_tests = self._test_mapper.get_affected_tests(
                all_affected
            )

        # 3. Find affected services
        if self._service_mapper:
            services: set[str] = set()
            for f in changed_files:
                svc = self._service_mapper.get_service_for_file(f)
                if svc:
                    services.add(svc.name)
            report.affected_services = sorted(services)

        # 4. Compute risk score
        report.risk_score = self._compute_risk(report, changed_files)
        report.risk_factors = self._identify_risk_factors(report, changed_files)

        logger.info(
            f'[ImpactAnalysis] {len(changed_files)} changes -> '
            f'{len(report.affected_files)} affected files, '
            f'{len(report.affected_tests)} affected tests, '
            f'risk={report.risk_score:.2f}'
        )

        return report

    def _compute_risk(
        self, report: ImpactReport, changed_files: list[str]
    ) -> float:
        """Compute a risk score (0.0 to 1.0) for the change set."""
        score = 0.0

        # More affected files = higher risk
        affected_count = report.total_affected
        if affected_count > 50:
            score += 0.3
        elif affected_count > 20:
            score += 0.2
        elif affected_count > 5:
            score += 0.1

        # Multiple services affected = higher risk
        if len(report.affected_services) > 2:
            score += 0.2
        elif len(report.affected_services) > 1:
            score += 0.1

        # Config file changes = higher risk
        config_patterns = (
            'config',
            '.env',
            'settings',
            'pyproject.toml',
            'package.json',
        )
        for f in changed_files:
            if any(p in f.lower() for p in config_patterns):
                score += 0.15
                break

        # Infrastructure file changes = higher risk
        infra_patterns = (
            'dockerfile',
            'docker-compose',
            'terraform',
            'kubernetes',
            'k8s',
            'helm',
            'ci',
            'cd',
        )
        for f in changed_files:
            if any(p in f.lower() for p in infra_patterns):
                score += 0.15
                break

        # No test coverage = higher risk
        if not report.affected_tests and changed_files:
            score += 0.2

        return min(score, 1.0)

    def _identify_risk_factors(
        self, report: ImpactReport, changed_files: list[str]
    ) -> list[str]:
        """Identify specific risk factors for the change."""
        factors: list[str] = []

        if report.total_affected > 20:
            factors.append(
                f'High blast radius: {report.total_affected} files affected'
            )

        if len(report.affected_services) > 1:
            factors.append(
                f'Cross-service change: {", ".join(report.affected_services)}'
            )

        if not report.affected_tests:
            factors.append('No test coverage for changed files')

        for f in changed_files:
            if 'migration' in f.lower() or 'schema' in f.lower():
                factors.append(f'Database schema/migration change: {f}')
                break

        for f in changed_files:
            if any(p in f.lower() for p in ('auth', 'security', 'permission', 'token')):
                factors.append(f'Security-sensitive file changed: {f}')
                break

        return factors
