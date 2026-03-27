"""PR Generator — creates pull requests from task execution results.

Generates structured PR descriptions with:
- What changed and why
- Test results
- Impact analysis summary
- Execution trace summary
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class PRDescription:
    """Structured PR description."""

    title: str = ''
    body: str = ''
    labels: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)
    base_branch: str = 'main'
    head_branch: str = ''
    draft: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'title': self.title,
            'body': self.body[:5000],
            'labels': self.labels,
            'reviewers': self.reviewers,
            'base_branch': self.base_branch,
            'head_branch': self.head_branch,
            'draft': self.draft,
        }


class PRGenerator:
    """Generates pull request descriptions from task results.

    Usage:
        gen = PRGenerator()
        pr = gen.generate(
            task_title="Fix login bug",
            changed_files=["src/auth/login.py"],
            test_results={"passed": 15, "failed": 0},
            impact_summary="Low risk, 2 files affected",
        )
        print(pr.title, pr.body)
    """

    def __init__(self) -> None:
        self._template_sections: list[str] = []

    def generate(
        self,
        task_title: str,
        task_description: str = '',
        task_type: str = 'custom',
        changed_files: list[str] | None = None,
        test_results: dict[str, Any] | None = None,
        impact_summary: str = '',
        execution_trace: str = '',
        base_branch: str = 'main',
        head_branch: str = '',
        labels: list[str] | None = None,
    ) -> PRDescription:
        """Generate a PR description.

        Args:
            task_title: Title of the task
            task_description: Full description
            task_type: Type of task
            changed_files: List of modified files
            test_results: Test execution results
            impact_summary: Impact analysis summary
            execution_trace: Execution trace summary
            base_branch: Target branch
            head_branch: Source branch
            labels: PR labels

        Returns:
            PRDescription ready for submission
        """
        changed_files = changed_files or []
        test_results = test_results or {}
        labels = labels or []

        # Generate title
        title = self._generate_title(task_title, task_type)

        # Generate body
        body_parts: list[str] = []

        # Summary section
        body_parts.append('## Summary')
        body_parts.append(task_description or task_title)
        body_parts.append('')

        # Changes section
        if changed_files:
            body_parts.append('## Changes')
            for f in changed_files[:30]:
                body_parts.append(f'- `{f}`')
            if len(changed_files) > 30:
                body_parts.append(f'- ... and {len(changed_files) - 30} more files')
            body_parts.append('')

        # Test results section
        if test_results:
            body_parts.append('## Test Results')
            passed = test_results.get('passed_count', test_results.get('passed', 0))
            failed = test_results.get('failed_count', test_results.get('failed', 0))
            total = test_results.get('total_tests', test_results.get('total', 0))
            body_parts.append(f'- **Passed**: {passed}/{total}')
            if failed:
                body_parts.append(f'- **Failed**: {failed}')
            body_parts.append('')

        # Impact analysis section
        if impact_summary:
            body_parts.append('## Impact Analysis')
            body_parts.append(impact_summary)
            body_parts.append('')

        # Execution trace section
        if execution_trace:
            body_parts.append('## Execution Trace')
            body_parts.append(f'```\n{execution_trace[:2000]}\n```')
            body_parts.append('')

        # Auto-generated label
        if task_type and task_type not in labels:
            labels.append(task_type)

        body = '\n'.join(body_parts)

        pr = PRDescription(
            title=title,
            body=body,
            labels=labels,
            base_branch=base_branch,
            head_branch=head_branch,
        )

        logger.info(f'[PRGenerator] Generated PR: {title}')
        return pr

    def _generate_title(self, task_title: str, task_type: str) -> str:
        """Generate a PR title from task info."""
        prefix_map = {
            'bug_fix': 'fix',
            'feature': 'feat',
            'refactor': 'refactor',
            'test': 'test',
            'documentation': 'docs',
            'deployment': 'deploy',
            'review': 'review',
            'custom': 'feat',
            'investigation': 'chore',
        }
        prefix = prefix_map.get(task_type, 'feat')
        return f'{prefix}: {task_title}'
