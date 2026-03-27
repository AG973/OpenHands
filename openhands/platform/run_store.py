"""Run Store — persists execution history and run records.

Every task execution is recorded as a "run" with full metadata:
input parameters, output results, timing, phase outcomes, and
references to artifacts. Supports querying by project, status,
time range, and more.

Patterns extracted from:
    - LangGraph: Checkpoint persistence
    - MLflow: Run tracking and metadata
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class RunStatus(Enum):
    """Status of an execution run."""

    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    TIMEOUT = 'timeout'


@dataclass
class RunRecord:
    """A single execution run record."""

    run_id: str = field(default_factory=lambda: f'run-{uuid.uuid4().hex[:12]}')
    task_id: str = ''
    project_id: str = ''
    title: str = ''
    status: RunStatus = RunStatus.QUEUED
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    duration_s: float = 0.0
    phases_completed: list[str] = field(default_factory=list)
    phases_failed: list[str] = field(default_factory=list)
    roles_executed: list[str] = field(default_factory=list)
    error: str = ''
    retry_count: int = 0
    files_changed: list[str] = field(default_factory=list)
    test_passed: bool = False
    review_score: float = 0.0
    artifact_ids: list[str] = field(default_factory=list)
    commit_sha: str = ''
    pr_url: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'task_id': self.task_id,
            'project_id': self.project_id,
            'title': self.title,
            'status': self.status.value,
            'duration_s': self.duration_s,
            'phases_completed': self.phases_completed,
            'files_changed': len(self.files_changed),
            'test_passed': self.test_passed,
            'review_score': self.review_score,
            'pr_url': self.pr_url,
        }


class RunStore:
    """Persists execution history for querying and analytics.

    Usage:
        store = RunStore()

        # Create a run
        run = store.create_run(
            task_id='task-1',
            project_id='proj-1',
            title='Fix login bug',
        )

        # Update run status
        store.update_status(run.run_id, RunStatus.RUNNING)
        store.add_phase(run.run_id, 'execute')
        store.complete_run(run.run_id, success=True)

        # Query runs
        recent = store.get_recent(limit=10)
        by_project = store.get_by_project('proj-1')
    """

    def __init__(self, max_records: int = 10000) -> None:
        self._records: dict[str, RunRecord] = {}
        self._max_records = max_records
        self._by_project: dict[str, list[str]] = {}
        self._by_task: dict[str, str] = {}

    def create_run(
        self,
        task_id: str = '',
        project_id: str = '',
        title: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        """Create a new run record."""
        if len(self._records) >= self._max_records:
            self._evict_oldest()

        run = RunRecord(
            task_id=task_id,
            project_id=project_id,
            title=title,
            metadata=metadata or {},
        )

        self._records[run.run_id] = run

        if project_id:
            if project_id not in self._by_project:
                self._by_project[project_id] = []
            self._by_project[project_id].append(run.run_id)

        if task_id:
            self._by_task[task_id] = run.run_id

        logger.info(f'[RunStore] Created run: {run.run_id} — "{title}"')
        return run

    def get_run(self, run_id: str) -> RunRecord | None:
        """Get a run record by ID."""
        return self._records.get(run_id)

    def get_by_task(self, task_id: str) -> RunRecord | None:
        """Get the run for a specific task."""
        run_id = self._by_task.get(task_id)
        return self._records.get(run_id) if run_id else None

    def update_status(self, run_id: str, status: RunStatus) -> bool:
        """Update a run's status."""
        run = self._records.get(run_id)
        if run is None:
            return False
        run.status = status
        if status == RunStatus.RUNNING and not run.started_at:
            run.started_at = time.time()
        return True

    def add_phase(self, run_id: str, phase: str, success: bool = True) -> None:
        """Record a completed phase."""
        run = self._records.get(run_id)
        if run:
            if success:
                run.phases_completed.append(phase)
            else:
                run.phases_failed.append(phase)

    def add_role(self, run_id: str, role: str) -> None:
        """Record an executed role."""
        run = self._records.get(run_id)
        if run:
            run.roles_executed.append(role)

    def set_test_result(self, run_id: str, passed: bool) -> None:
        """Record test result."""
        run = self._records.get(run_id)
        if run:
            run.test_passed = passed

    def set_review_score(self, run_id: str, score: float) -> None:
        """Record review score."""
        run = self._records.get(run_id)
        if run:
            run.review_score = score

    def set_files_changed(self, run_id: str, files: list[str]) -> None:
        """Record changed files."""
        run = self._records.get(run_id)
        if run:
            run.files_changed = files

    def set_pr_url(self, run_id: str, url: str) -> None:
        """Record the PR URL."""
        run = self._records.get(run_id)
        if run:
            run.pr_url = url

    def set_commit_sha(self, run_id: str, sha: str) -> None:
        """Record the commit SHA."""
        run = self._records.get(run_id)
        if run:
            run.commit_sha = sha

    def add_artifact(self, run_id: str, artifact_id: str) -> None:
        """Associate an artifact with a run."""
        run = self._records.get(run_id)
        if run:
            run.artifact_ids.append(artifact_id)

    def complete_run(
        self, run_id: str, success: bool = True, error: str = ''
    ) -> bool:
        """Mark a run as completed."""
        run = self._records.get(run_id)
        if run is None:
            return False

        run.status = RunStatus.COMPLETED if success else RunStatus.FAILED
        run.completed_at = time.time()
        run.duration_s = run.completed_at - run.started_at
        run.error = error

        logger.info(
            f'[RunStore] Run {"completed" if success else "failed"}: '
            f'{run_id} ({run.duration_s:.2f}s)'
        )
        return True

    def get_recent(self, limit: int = 20) -> list[RunRecord]:
        """Get the most recent runs."""
        runs = sorted(
            self._records.values(),
            key=lambda r: r.started_at,
            reverse=True,
        )
        return runs[:limit]

    def get_by_project(
        self, project_id: str, limit: int = 50
    ) -> list[RunRecord]:
        """Get runs for a specific project."""
        run_ids = self._by_project.get(project_id, [])
        runs = [
            self._records[rid]
            for rid in run_ids
            if rid in self._records
        ]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[:limit]

    def get_by_status(self, status: RunStatus) -> list[RunRecord]:
        """Get runs with a specific status."""
        return [
            r for r in self._records.values()
            if r.status == status
        ]

    def get_failed_runs(self, limit: int = 20) -> list[RunRecord]:
        """Get recent failed runs for analysis."""
        failed = [
            r for r in self._records.values()
            if r.status == RunStatus.FAILED
        ]
        failed.sort(key=lambda r: r.started_at, reverse=True)
        return failed[:limit]

    def search(
        self,
        query: str = '',
        project_id: str = '',
        status: RunStatus | None = None,
        limit: int = 50,
    ) -> list[RunRecord]:
        """Search runs with filters."""
        results = list(self._records.values())

        if project_id:
            results = [r for r in results if r.project_id == project_id]
        if status:
            results = [r for r in results if r.status == status]
        if query:
            q = query.lower()
            results = [
                r for r in results
                if q in r.title.lower() or q in r.task_id.lower()
            ]

        results.sort(key=lambda r: r.started_at, reverse=True)
        return results[:limit]

    @property
    def total_runs(self) -> int:
        return len(self._records)

    def stats(self) -> dict[str, Any]:
        """Get store statistics."""
        status_counts: dict[str, int] = {}
        total_duration = 0.0
        completed_count = 0

        for r in self._records.values():
            sv = r.status.value
            status_counts[sv] = status_counts.get(sv, 0) + 1
            if r.status == RunStatus.COMPLETED:
                total_duration += r.duration_s
                completed_count += 1

        avg_duration = total_duration / completed_count if completed_count else 0

        return {
            'total_runs': len(self._records),
            'by_status': status_counts,
            'avg_duration_s': avg_duration,
            'projects_tracked': len(self._by_project),
        }

    def _evict_oldest(self) -> None:
        """Remove the oldest completed run."""
        completed = [
            r for r in self._records.values()
            if r.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED)
        ]
        if not completed:
            return
        oldest = min(completed, key=lambda r: r.started_at)
        del self._records[oldest.run_id]
