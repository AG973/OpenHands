"""Project Registry — manages multiple repositories and project configurations.

Provides project-level isolation for the SaaS platform. Each project
has its own configuration, memory state, and execution history.

Patterns extracted from:
    - GPT-Pilot: Project model with workspace isolation
    - OpenHands: Repository/workspace management
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class ProjectStatus(Enum):
    """Project lifecycle status."""

    ACTIVE = 'active'
    PAUSED = 'paused'
    ARCHIVED = 'archived'
    SETUP = 'setup'
    ERROR = 'error'


@dataclass
class ProjectConfig:
    """Configuration for a project."""

    repo_url: str = ''
    default_branch: str = 'main'
    language: str = ''
    framework: str = ''
    test_command: str = ''
    build_command: str = ''
    lint_command: str = ''
    llm_model: str = ''
    max_concurrent_tasks: int = 3
    auto_merge: bool = False
    require_review: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Project:
    """A registered project."""

    project_id: str = field(default_factory=lambda: f'proj-{uuid.uuid4().hex[:8]}')
    name: str = ''
    description: str = ''
    repo_path: str = ''
    config: ProjectConfig = field(default_factory=ProjectConfig)
    status: ProjectStatus = ProjectStatus.SETUP
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    task_count: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    owner: str = ''
    tags: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.completed_tasks + self.failed_tasks
        if total == 0:
            return 0.0
        return self.completed_tasks / total

    def to_dict(self) -> dict[str, Any]:
        return {
            'project_id': self.project_id,
            'name': self.name,
            'repo_path': self.repo_path,
            'status': self.status.value,
            'task_count': self.task_count,
            'success_rate': self.success_rate,
            'language': self.config.language,
        }


class ProjectRegistry:
    """Manages multiple projects for the SaaS platform.

    Usage:
        registry = ProjectRegistry()

        # Register a project
        project = registry.register(
            name='My App',
            repo_path='/workspace/myapp',
            config=ProjectConfig(
                repo_url='https://github.com/user/myapp',
                language='python',
                test_command='pytest',
            ),
        )

        # Get project
        proj = registry.get(project.project_id)

        # Update task counts
        registry.record_task_completion(project.project_id, success=True)
    """

    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}
        self._by_repo: dict[str, str] = {}  # repo_path -> project_id
        self._by_name: dict[str, str] = {}  # name -> project_id

    def register(
        self,
        name: str,
        repo_path: str = '',
        description: str = '',
        config: ProjectConfig | None = None,
        owner: str = '',
        tags: list[str] | None = None,
    ) -> Project:
        """Register a new project."""
        project = Project(
            name=name,
            description=description,
            repo_path=repo_path,
            config=config or ProjectConfig(),
            owner=owner,
            tags=tags or [],
        )

        self._projects[project.project_id] = project
        if repo_path:
            self._by_repo[repo_path] = project.project_id
        self._by_name[name.lower()] = project.project_id

        logger.info(
            f'[ProjectRegistry] Registered: {project.project_id} — "{name}"'
        )
        return project

    def get(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self._projects.get(project_id)

    def get_by_repo(self, repo_path: str) -> Project | None:
        """Get a project by repository path."""
        pid = self._by_repo.get(repo_path)
        return self._projects.get(pid) if pid else None

    def get_by_name(self, name: str) -> Project | None:
        """Get a project by name."""
        pid = self._by_name.get(name.lower())
        return self._projects.get(pid) if pid else None

    def update_config(
        self, project_id: str, config: ProjectConfig
    ) -> bool:
        """Update a project's configuration."""
        project = self._projects.get(project_id)
        if project is None:
            return False
        project.config = config
        project.updated_at = time.time()
        return True

    def set_status(self, project_id: str, status: ProjectStatus) -> bool:
        """Update a project's status."""
        project = self._projects.get(project_id)
        if project is None:
            return False
        project.status = status
        project.updated_at = time.time()
        return True

    def record_task_submission(self, project_id: str) -> None:
        """Record that a task was submitted for a project."""
        project = self._projects.get(project_id)
        if project:
            project.task_count += 1
            project.updated_at = time.time()

    def record_task_completion(
        self, project_id: str, success: bool = True
    ) -> None:
        """Record task completion (success or failure)."""
        project = self._projects.get(project_id)
        if project:
            if success:
                project.completed_tasks += 1
            else:
                project.failed_tasks += 1
            project.updated_at = time.time()

    def list_projects(
        self,
        status: ProjectStatus | None = None,
        owner: str = '',
        tag: str = '',
    ) -> list[Project]:
        """List projects with optional filters."""
        projects = list(self._projects.values())

        if status is not None:
            projects = [p for p in projects if p.status == status]
        if owner:
            projects = [p for p in projects if p.owner == owner]
        if tag:
            projects = [p for p in projects if tag in p.tags]

        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def archive(self, project_id: str) -> bool:
        """Archive a project."""
        return self.set_status(project_id, ProjectStatus.ARCHIVED)

    def remove(self, project_id: str) -> bool:
        """Remove a project from the registry."""
        project = self._projects.pop(project_id, None)
        if project is None:
            return False

        if project.repo_path in self._by_repo:
            del self._by_repo[project.repo_path]
        name_key = project.name.lower()
        if name_key in self._by_name:
            del self._by_name[name_key]

        return True

    @property
    def project_count(self) -> int:
        return len(self._projects)

    def stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        status_counts: dict[str, int] = {}
        for p in self._projects.values():
            sv = p.status.value
            status_counts[sv] = status_counts.get(sv, 0) + 1

        total_tasks = sum(p.task_count for p in self._projects.values())
        total_completed = sum(p.completed_tasks for p in self._projects.values())

        return {
            'total_projects': len(self._projects),
            'by_status': status_counts,
            'total_tasks': total_tasks,
            'total_completed': total_completed,
        }
