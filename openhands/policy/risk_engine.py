"""Risk Engine — assesses risk before executing operations.

Every tool execution, file modification, and deployment goes through
the risk engine. It evaluates the operation against repo context,
impact analysis, and policy rules to produce a risk score and
approve/deny/escalate decision.

Patterns extracted from:
    - OpenHands: SecurityAnalyzer with ActionSecurityRisk levels
    - GPT-Pilot: Human-in-the-loop for risky operations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class RiskLevel(Enum):
    """Risk levels for operations."""

    NONE = 'none'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class RiskDecision(Enum):
    """Decision after risk assessment."""

    APPROVE = 'approve'
    APPROVE_WITH_WARNING = 'approve_with_warning'
    REQUIRE_CONFIRMATION = 'require_confirmation'
    DENY = 'deny'
    ESCALATE = 'escalate'


@dataclass
class RiskAssessment:
    """Result of a risk assessment."""

    risk_level: RiskLevel = RiskLevel.NONE
    risk_score: float = 0.0  # 0.0 = no risk, 1.0 = maximum risk
    decision: RiskDecision = RiskDecision.APPROVE
    factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'risk_level': self.risk_level.value,
            'risk_score': self.risk_score,
            'decision': self.decision.value,
            'factors': self.factors,
            'recommendations': self.recommendations,
        }


# Risk rules: operation patterns and their risk contributions
RISK_RULES: list[dict[str, Any]] = [
    {
        'name': 'destructive_command',
        'patterns': ['rm -rf', 'drop table', 'delete from', 'truncate', 'format'],
        'risk_contribution': 0.9,
        'description': 'Destructive command detected',
    },
    {
        'name': 'force_push',
        'patterns': ['push --force', 'push -f', 'reset --hard'],
        'risk_contribution': 0.8,
        'description': 'Force push or hard reset',
    },
    {
        'name': 'system_command',
        'patterns': ['sudo', 'chmod 777', 'chown', 'systemctl', 'service'],
        'risk_contribution': 0.7,
        'description': 'System-level command',
    },
    {
        'name': 'network_access',
        'patterns': ['curl', 'wget', 'requests.get', 'fetch(', 'http://'],
        'risk_contribution': 0.3,
        'description': 'Network access',
    },
    {
        'name': 'credential_exposure',
        'patterns': ['password', 'secret', 'api_key', 'token', 'private_key'],
        'risk_contribution': 0.6,
        'description': 'Potential credential exposure',
    },
    {
        'name': 'config_modification',
        'patterns': ['.env', 'config.yaml', 'settings.py', '.toml', 'Dockerfile'],
        'risk_contribution': 0.4,
        'description': 'Configuration file modification',
    },
    {
        'name': 'database_operation',
        'patterns': ['migrate', 'ALTER TABLE', 'CREATE INDEX', 'DROP INDEX'],
        'risk_contribution': 0.5,
        'description': 'Database schema operation',
    },
]


class RiskEngine:
    """Assesses risk for operations before execution.

    Usage:
        engine = RiskEngine()
        assessment = engine.assess(
            operation='shell_exec',
            content='rm -rf /tmp/build',
            context={'phase': 'execute', 'repo_path': '/workspace/app'},
        )
        if assessment.decision == RiskDecision.APPROVE:
            # Safe to proceed
        elif assessment.decision == RiskDecision.DENY:
            # Block operation
    """

    def __init__(self) -> None:
        self._rules = list(RISK_RULES)
        self._risk_threshold_warn = 0.3
        self._risk_threshold_confirm = 0.6
        self._risk_threshold_deny = 0.9
        self._assessment_history: list[RiskAssessment] = []

    def assess(
        self,
        operation: str,
        content: str = '',
        file_path: str = '',
        context: dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Assess the risk of an operation.

        Args:
            operation: Type of operation (shell_exec, file_write, git_push, etc.)
            content: Content of the operation (command, file content, etc.)
            file_path: File being affected (if applicable)
            context: Additional context (phase, repo_path, etc.)

        Returns:
            RiskAssessment with risk level, score, and decision
        """
        context = context or {}
        factors: list[str] = []
        risk_score = 0.0

        # Check against risk rules
        combined = f'{operation} {content} {file_path}'.lower()
        for rule in self._rules:
            for pattern in rule['patterns']:
                if pattern.lower() in combined:
                    risk_score += rule['risk_contribution']
                    factors.append(rule['description'])
                    break

        # Context-based risk adjustments
        phase = context.get('phase', '')
        if phase in ('intake', 'context_build', 'repo_analysis', 'plan'):
            # Early phases should be read-only
            if operation in ('file_write', 'shell_exec', 'git_push'):
                risk_score += 0.3
                factors.append(f'Write operation in read-only phase ({phase})')

        # Impact-based risk
        impact_files = context.get('impact_files', [])
        if len(impact_files) > 20:
            risk_score += 0.2
            factors.append(f'Large impact radius: {len(impact_files)} files')

        # Clamp score
        risk_score = min(1.0, risk_score)

        # Determine risk level
        if risk_score >= 0.8:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 0.6:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 0.3:
            risk_level = RiskLevel.MEDIUM
        elif risk_score > 0:
            risk_level = RiskLevel.LOW
        else:
            risk_level = RiskLevel.NONE

        # Determine decision
        decision, recommendations = self._make_decision(risk_score, factors)

        assessment = RiskAssessment(
            risk_level=risk_level,
            risk_score=risk_score,
            decision=decision,
            factors=factors,
            recommendations=recommendations,
            metadata={'operation': operation, 'phase': phase},
        )

        self._assessment_history.append(assessment)

        if risk_score > 0:
            logger.info(
                f'[RiskEngine] {operation}: score={risk_score:.2f}, '
                f'level={risk_level.value}, decision={decision.value}'
            )

        return assessment

    def _make_decision(
        self, risk_score: float, factors: list[str]
    ) -> tuple[RiskDecision, list[str]]:
        """Make a decision based on risk score."""
        recommendations: list[str] = []

        if risk_score >= self._risk_threshold_deny:
            recommendations.append('Operation blocked — too risky for automated execution')
            recommendations.append('Consider manual execution or breaking into smaller steps')
            return RiskDecision.DENY, recommendations

        if risk_score >= self._risk_threshold_confirm:
            recommendations.append('Operation requires explicit confirmation before proceeding')
            return RiskDecision.REQUIRE_CONFIRMATION, recommendations

        if risk_score >= self._risk_threshold_warn:
            recommendations.append('Proceed with caution — monitor for issues')
            return RiskDecision.APPROVE_WITH_WARNING, recommendations

        return RiskDecision.APPROVE, recommendations

    def add_rule(self, name: str, patterns: list[str], risk_contribution: float, description: str = '') -> None:
        """Add a custom risk rule."""
        self._rules.append({
            'name': name,
            'patterns': patterns,
            'risk_contribution': risk_contribution,
            'description': description or name,
        })

    def set_thresholds(
        self,
        warn: float = 0.3,
        confirm: float = 0.6,
        deny: float = 0.9,
    ) -> None:
        """Configure risk thresholds."""
        self._risk_threshold_warn = warn
        self._risk_threshold_confirm = confirm
        self._risk_threshold_deny = deny

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent assessment history."""
        return [a.to_dict() for a in self._assessment_history[-limit:]]

    def stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        if not self._assessment_history:
            return {'total_assessments': 0}

        decisions: dict[str, int] = {}
        for a in self._assessment_history:
            d = a.decision.value
            decisions[d] = decisions.get(d, 0) + 1

        return {
            'total_assessments': len(self._assessment_history),
            'decisions': decisions,
            'avg_risk_score': sum(a.risk_score for a in self._assessment_history) / len(self._assessment_history),
        }
