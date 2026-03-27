"""Escalation Policy — determines when to escalate beyond automation.

When automated retries fail, the escalation policy determines:
- Whether to escalate to a human
- What information to include in the escalation
- Priority and urgency of the escalation
- Fallback strategies before escalation

Patterns extracted from:
    - GPT-Pilot: Human-in-the-loop for complex decisions
    - OpenHands: User confirmation for risky actions
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class EscalationLevel(Enum):
    """Escalation urgency levels."""

    INFO = 'info'  # Informational, no action needed
    WARNING = 'warning'  # Attention recommended
    ACTION_REQUIRED = 'action_required'  # Human action needed
    CRITICAL = 'critical'  # Immediate attention required
    BLOCKED = 'blocked'  # Cannot proceed without human


class EscalationReason(Enum):
    """Reasons for escalation."""

    MAX_RETRIES = 'max_retries'
    RISK_TOO_HIGH = 'risk_too_high'
    AMBIGUOUS_REQUIREMENTS = 'ambiguous_requirements'
    MISSING_CREDENTIALS = 'missing_credentials'
    EXTERNAL_DEPENDENCY = 'external_dependency'
    ARCHITECTURAL_DECISION = 'architectural_decision'
    SECURITY_CONCERN = 'security_concern'
    BUDGET_EXCEEDED = 'budget_exceeded'
    STUCK_LOOP = 'stuck_loop'
    UNKNOWN_ERROR = 'unknown_error'


@dataclass
class EscalationRequest:
    """A request for human escalation."""

    escalation_id: str = ''
    level: EscalationLevel = EscalationLevel.WARNING
    reason: EscalationReason = EscalationReason.UNKNOWN_ERROR
    title: str = ''
    description: str = ''
    task_id: str = ''
    phase: str = ''
    error_summary: str = ''
    attempted_solutions: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'escalation_id': self.escalation_id,
            'level': self.level.value,
            'reason': self.reason.value,
            'title': self.title,
            'description': self.description[:500],
            'task_id': self.task_id,
            'resolved': self.resolved,
        }


class EscalationPolicy:
    """Determines when and how to escalate beyond automation.

    Usage:
        policy = EscalationPolicy()

        # Check if escalation is needed
        decision = policy.should_escalate(
            reason=EscalationReason.MAX_RETRIES,
            retry_count=5,
            error='Tests keep failing',
        )
        if decision:
            request = policy.create_escalation(
                reason=EscalationReason.MAX_RETRIES,
                title='Tests failing after 5 retries',
                task_id='task-123',
            )
            # Send request to human
    """

    def __init__(self) -> None:
        self._escalation_history: list[EscalationRequest] = []
        self._auto_escalate_reasons: set[EscalationReason] = {
            EscalationReason.MISSING_CREDENTIALS,
            EscalationReason.SECURITY_CONCERN,
            EscalationReason.BUDGET_EXCEEDED,
        }
        self._retry_threshold = 3
        self._stuck_threshold_s = 300.0  # 5 minutes without progress

    def should_escalate(
        self,
        reason: EscalationReason,
        retry_count: int = 0,
        error: str = '',
        time_elapsed_s: float = 0.0,
    ) -> bool:
        """Determine if escalation is needed.

        Args:
            reason: Why escalation might be needed
            retry_count: Number of retries attempted
            error: Error message
            time_elapsed_s: Time since task started

        Returns:
            True if escalation should happen
        """
        # Auto-escalate for certain reasons
        if reason in self._auto_escalate_reasons:
            return True

        # Retry-based escalation
        if reason == EscalationReason.MAX_RETRIES:
            return retry_count >= self._retry_threshold

        # Time-based escalation (stuck detection)
        if reason == EscalationReason.STUCK_LOOP:
            return time_elapsed_s >= self._stuck_threshold_s

        # Risk-based escalation
        if reason == EscalationReason.RISK_TOO_HIGH:
            return True  # Always escalate high-risk

        return False

    def create_escalation(
        self,
        reason: EscalationReason,
        title: str,
        task_id: str = '',
        phase: str = '',
        error_summary: str = '',
        attempted_solutions: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> EscalationRequest:
        """Create an escalation request.

        Args:
            reason: Why we're escalating
            title: Short description
            task_id: Task that triggered escalation
            phase: Current phase
            error_summary: Summary of the error
            attempted_solutions: What was already tried
            context: Additional context

        Returns:
            EscalationRequest ready to be sent to human
        """
        level = self._determine_level(reason)
        suggested_actions = self._suggest_actions(reason, error_summary)

        request = EscalationRequest(
            escalation_id=f'esc-{len(self._escalation_history) + 1}',
            level=level,
            reason=reason,
            title=title,
            description=self._build_description(reason, error_summary, attempted_solutions),
            task_id=task_id,
            phase=phase,
            error_summary=error_summary,
            attempted_solutions=attempted_solutions or [],
            suggested_actions=suggested_actions,
            context=context or {},
        )

        self._escalation_history.append(request)

        logger.info(
            f'[EscalationPolicy] Created escalation: {title} '
            f'(level={level.value}, reason={reason.value})'
        )

        return request

    def resolve_escalation(
        self, escalation_id: str, resolution: str
    ) -> bool:
        """Mark an escalation as resolved."""
        for req in self._escalation_history:
            if req.escalation_id == escalation_id:
                req.resolved = True
                req.resolution = resolution
                return True
        return False

    def get_pending_escalations(self) -> list[EscalationRequest]:
        """Get all unresolved escalations."""
        return [r for r in self._escalation_history if not r.resolved]

    def _determine_level(self, reason: EscalationReason) -> EscalationLevel:
        """Determine escalation urgency level."""
        critical_reasons = {
            EscalationReason.SECURITY_CONCERN,
            EscalationReason.BUDGET_EXCEEDED,
        }
        blocked_reasons = {
            EscalationReason.MISSING_CREDENTIALS,
        }
        action_reasons = {
            EscalationReason.MAX_RETRIES,
            EscalationReason.RISK_TOO_HIGH,
            EscalationReason.ARCHITECTURAL_DECISION,
        }

        if reason in blocked_reasons:
            return EscalationLevel.BLOCKED
        if reason in critical_reasons:
            return EscalationLevel.CRITICAL
        if reason in action_reasons:
            return EscalationLevel.ACTION_REQUIRED
        return EscalationLevel.WARNING

    def _suggest_actions(
        self, reason: EscalationReason, error_summary: str
    ) -> list[str]:
        """Suggest actions for the human to take."""
        suggestions: list[str] = []

        if reason == EscalationReason.MAX_RETRIES:
            suggestions.append('Review the error details and provide guidance')
            suggestions.append('Consider simplifying the task scope')
            suggestions.append('Manually fix the blocking issue and resume')

        elif reason == EscalationReason.MISSING_CREDENTIALS:
            suggestions.append('Provide the required credentials or API keys')
            suggestions.append('Set up the necessary access permissions')

        elif reason == EscalationReason.RISK_TOO_HIGH:
            suggestions.append('Review the proposed changes for safety')
            suggestions.append('Approve or modify the risky operation')

        elif reason == EscalationReason.SECURITY_CONCERN:
            suggestions.append('Review the security concern immediately')
            suggestions.append('Determine if the operation should proceed')

        elif reason == EscalationReason.ARCHITECTURAL_DECISION:
            suggestions.append('Make the architectural decision')
            suggestions.append('Provide design guidance for the ambiguous area')

        elif reason == EscalationReason.STUCK_LOOP:
            suggestions.append('Review recent actions for loop patterns')
            suggestions.append('Provide new instructions to break the loop')

        else:
            suggestions.append('Review the error and provide guidance')

        return suggestions

    def _build_description(
        self,
        reason: EscalationReason,
        error_summary: str,
        attempted_solutions: list[str] | None,
    ) -> str:
        """Build a human-readable escalation description."""
        parts: list[str] = []
        parts.append(f'**Reason**: {reason.value}')

        if error_summary:
            parts.append(f'**Error**: {error_summary[:300]}')

        if attempted_solutions:
            parts.append('**Attempted solutions**:')
            for sol in attempted_solutions[:5]:
                parts.append(f'  - {sol}')

        return '\n'.join(parts)

    def set_retry_threshold(self, threshold: int) -> None:
        """Set the retry count threshold for escalation."""
        self._retry_threshold = threshold

    def set_stuck_threshold(self, seconds: float) -> None:
        """Set the time threshold for stuck detection escalation."""
        self._stuck_threshold_s = seconds

    def stats(self) -> dict[str, Any]:
        """Get escalation statistics."""
        total = len(self._escalation_history)
        resolved = sum(1 for r in self._escalation_history if r.resolved)
        return {
            'total_escalations': total,
            'resolved': resolved,
            'pending': total - resolved,
            'by_reason': {},
        }
