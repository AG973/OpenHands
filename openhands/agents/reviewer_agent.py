"""Reviewer Agent — validates code quality before finalization.

The reviewer checks all changes made by the coder for quality,
correctness, security, and consistency. It acts as the final gate
before artifact generation.

Patterns extracted from:
    - GPT-Pilot: CodeReviewer with structured review output
    - CrewAI: Quality gate agent in pipeline
"""

from __future__ import annotations

import os
from typing import Any

from openhands.agents.base_role import AgentRole, RoleContext, RoleName, RoleOutput
from openhands.core.logger import openhands_logger as logger


class ReviewerAgent(AgentRole):
    """Validates code quality, security, and consistency.

    The reviewer:
    - Checks code against design constraints
    - Validates naming conventions and patterns
    - Detects potential security issues
    - Ensures test coverage for changes
    - Scores the review on a 0-1 scale
    - Gates progression to artifact generation
    """

    # Quality checks
    SECURITY_PATTERNS: list[str] = [
        'eval(',
        'exec(',
        'os.system(',
        'subprocess.call(shell=True',
        '__import__(',
        'pickle.loads(',
        'yaml.load(',  # without SafeLoader
        'password',
        'secret',
        'api_key',
        'token',
    ]

    @property
    def role_name(self) -> RoleName:
        return RoleName.REVIEWER

    @property
    def description(self) -> str:
        return (
            'Validates code quality, security, and consistency. '
            'Gates progression to artifact generation with scored review.'
        )

    def execute(self, context: RoleContext) -> RoleOutput:
        """Review all changes for quality and correctness."""
        comments: list[str] = []
        score = 1.0  # Start with perfect score, deduct for issues

        # Check 1: Design constraint compliance
        constraint_issues = self._check_constraints(context)
        if constraint_issues:
            comments.extend(constraint_issues)
            score -= 0.1 * len(constraint_issues)

        # Check 2: Security scan
        security_issues = self._check_security(context)
        if security_issues:
            comments.extend(security_issues)
            score -= 0.2 * len(security_issues)

        # Check 3: Test coverage
        coverage_issues = self._check_test_coverage(context)
        if coverage_issues:
            comments.extend(coverage_issues)
            score -= 0.1 * len(coverage_issues)

        # Check 4: Code quality
        quality_issues = self._check_quality(context)
        if quality_issues:
            comments.extend(quality_issues)
            score -= 0.05 * len(quality_issues)

        # Clamp score
        score = max(0.0, min(1.0, score))

        # Determine pass/fail
        passed = score >= 0.5 and not security_issues

        # Update context
        context.review_passed = passed
        context.review_comments = comments
        context.review_score = score

        logger.info(
            f'[Reviewer] Score: {score:.2f}, '
            f'{"PASSED" if passed else "FAILED"}, '
            f'{len(comments)} comments'
        )

        return RoleOutput(
            role=self.role_name,
            success=passed,
            error='' if passed else f'Review failed (score: {score:.2f}): {len(comments)} issues',
            output_data={
                'score': score,
                'passed': passed,
                'comments': comments,
                'constraint_issues': len(constraint_issues),
                'security_issues': len(security_issues),
                'coverage_issues': len(coverage_issues),
                'quality_issues': len(quality_issues),
            },
            artifacts=[{
                'type': 'review',
                'name': 'code_review',
                'content': {
                    'score': score,
                    'passed': passed,
                    'comments': comments,
                },
            }],
        )

    def _check_constraints(self, context: RoleContext) -> list[str]:
        """Check if changes comply with design constraints."""
        issues: list[str] = []

        # Verify all planned files were actually changed
        planned_creates = set(context.files_to_create)
        planned_modifies = set(context.files_to_modify)
        actual_changes = set(context.applied_patches)

        missing = (planned_creates | planned_modifies) - actual_changes
        if missing:
            issues.append(
                f'Planned changes not applied: {", ".join(sorted(missing)[:5])}'
            )

        return issues

    def _check_security(self, context: RoleContext) -> list[str]:
        """Scan for potential security issues in changes."""
        issues: list[str] = []

        for change in context.code_changes:
            content = str(change.get('content', ''))
            file_path = change.get('file', '')

            for pattern in self.SECURITY_PATTERNS:
                if pattern in content:
                    # Only flag if it's not in a test file
                    if 'test' not in file_path.lower():
                        issues.append(
                            f'Security concern in {file_path}: '
                            f'contains "{pattern}" — verify this is safe'
                        )
                        break

        return issues

    def _check_test_coverage(self, context: RoleContext) -> list[str]:
        """Check if changes have adequate test coverage."""
        issues: list[str] = []

        # Check if tests were run
        if not context.test_passed and context.failed_tests:
            issues.append(
                f'Tests failing: {len(context.failed_tests)} test(s) failed'
            )

        # Check if new files have corresponding tests
        test_map = context.test_map
        for file_path in context.files_to_create:
            if (
                file_path.endswith('.py')
                and 'test' not in file_path.lower()
                and '__init__' not in file_path
            ):
                if file_path not in test_map:
                    issues.append(
                        f'Missing tests for new file: {file_path}'
                    )

        return issues

    def _check_quality(self, context: RoleContext) -> list[str]:
        """Check code quality of changes."""
        issues: list[str] = []

        # Check for very large changes (possible scope creep)
        if len(context.applied_patches) > 20:
            issues.append(
                f'Large changeset: {len(context.applied_patches)} files modified — '
                f'consider splitting into smaller PRs'
            )

        return issues
