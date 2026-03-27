"""Artifact Store — persistent storage for execution artifacts.

Stores and retrieves artifact bundles produced by the execution pipeline.
Each artifact is associated with a run and project. Supports querying
by run, project, type, and time range.

Patterns extracted from:
    - MLflow: Artifact logging and retrieval
    - S3: Object storage with metadata
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from openhands.core.logger import openhands_logger as logger


@dataclass
class StoredArtifact:
    """An artifact stored in the artifact store."""

    artifact_id: str = field(default_factory=lambda: f'art-{uuid.uuid4().hex[:12]}')
    run_id: str = ''
    project_id: str = ''
    artifact_type: str = ''
    name: str = ''
    file_path: str = ''
    content_hash: str = ''
    size_bytes: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'artifact_id': self.artifact_id,
            'run_id': self.run_id,
            'project_id': self.project_id,
            'type': self.artifact_type,
            'name': self.name,
            'size_bytes': self.size_bytes,
            'created_at': self.created_at,
        }


class ArtifactStore:
    """Persistent storage for execution artifacts.

    Usage:
        store = ArtifactStore(storage_dir='/data/artifacts')

        # Store an artifact
        artifact = store.store(
            run_id='run-123',
            project_id='proj-1',
            artifact_type='diff',
            name='changes.diff',
            content='--- a/file.py\\n+++ b/file.py\\n...',
        )

        # Retrieve
        content = store.retrieve(artifact.artifact_id)

        # Query
        run_artifacts = store.get_by_run('run-123')
        diffs = store.get_by_type('diff', project_id='proj-1')
    """

    def __init__(self, storage_dir: str = '') -> None:
        self._storage_dir = storage_dir
        self._artifacts: dict[str, StoredArtifact] = {}
        self._by_run: dict[str, list[str]] = {}
        self._by_project: dict[str, list[str]] = {}
        self._by_type: dict[str, list[str]] = {}
        self._content_cache: dict[str, Any] = {}

        if storage_dir:
            os.makedirs(storage_dir, exist_ok=True)

    def store(
        self,
        run_id: str = '',
        project_id: str = '',
        artifact_type: str = '',
        name: str = '',
        content: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredArtifact:
        """Store an artifact.

        Args:
            run_id: Associated run ID
            project_id: Associated project ID
            artifact_type: Type of artifact (diff, test_result, log, etc.)
            name: Human-readable name
            content: Artifact content (str, dict, or bytes)
            metadata: Additional metadata

        Returns:
            StoredArtifact with assigned artifact_id
        """
        # Calculate size
        if isinstance(content, str):
            size = len(content.encode())
        elif isinstance(content, dict):
            size = len(json.dumps(content, default=str).encode())
        elif isinstance(content, bytes):
            size = len(content)
        else:
            size = 0

        artifact = StoredArtifact(
            run_id=run_id,
            project_id=project_id,
            artifact_type=artifact_type,
            name=name,
            size_bytes=size,
            metadata=metadata or {},
        )

        # Store content
        if self._storage_dir:
            artifact.file_path = self._write_to_disk(artifact, content)
        else:
            self._content_cache[artifact.artifact_id] = content

        # Index
        self._artifacts[artifact.artifact_id] = artifact

        if run_id:
            if run_id not in self._by_run:
                self._by_run[run_id] = []
            self._by_run[run_id].append(artifact.artifact_id)

        if project_id:
            if project_id not in self._by_project:
                self._by_project[project_id] = []
            self._by_project[project_id].append(artifact.artifact_id)

        if artifact_type:
            if artifact_type not in self._by_type:
                self._by_type[artifact_type] = []
            self._by_type[artifact_type].append(artifact.artifact_id)

        logger.info(
            f'[ArtifactStore] Stored: {artifact.artifact_id} — '
            f'{name} ({artifact_type}, {size} bytes)'
        )
        return artifact

    def retrieve(self, artifact_id: str) -> Any | None:
        """Retrieve artifact content by ID."""
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            return None

        # Try disk first
        if artifact.file_path and os.path.exists(artifact.file_path):
            return self._read_from_disk(artifact)

        # Try cache
        return self._content_cache.get(artifact_id)

    def get_artifact(self, artifact_id: str) -> StoredArtifact | None:
        """Get artifact metadata by ID."""
        return self._artifacts.get(artifact_id)

    def get_by_run(self, run_id: str) -> list[StoredArtifact]:
        """Get all artifacts for a run."""
        ids = self._by_run.get(run_id, [])
        return [self._artifacts[aid] for aid in ids if aid in self._artifacts]

    def get_by_project(
        self, project_id: str, artifact_type: str = '', limit: int = 100
    ) -> list[StoredArtifact]:
        """Get artifacts for a project, optionally filtered by type."""
        ids = self._by_project.get(project_id, [])
        artifacts = [self._artifacts[aid] for aid in ids if aid in self._artifacts]

        if artifact_type:
            artifacts = [a for a in artifacts if a.artifact_type == artifact_type]

        artifacts.sort(key=lambda a: a.created_at, reverse=True)
        return artifacts[:limit]

    def get_by_type(
        self,
        artifact_type: str,
        project_id: str = '',
        limit: int = 100,
    ) -> list[StoredArtifact]:
        """Get artifacts by type."""
        ids = self._by_type.get(artifact_type, [])
        artifacts = [self._artifacts[aid] for aid in ids if aid in self._artifacts]

        if project_id:
            artifacts = [a for a in artifacts if a.project_id == project_id]

        artifacts.sort(key=lambda a: a.created_at, reverse=True)
        return artifacts[:limit]

    def delete(self, artifact_id: str) -> bool:
        """Delete an artifact."""
        artifact = self._artifacts.pop(artifact_id, None)
        if artifact is None:
            return False

        # Clean up disk
        if artifact.file_path and os.path.exists(artifact.file_path):
            try:
                os.remove(artifact.file_path)
            except OSError:
                pass

        # Clean up cache
        self._content_cache.pop(artifact_id, None)

        return True

    def get_total_size(self, project_id: str = '') -> int:
        """Get total storage size in bytes."""
        if project_id:
            artifacts = self.get_by_project(project_id)
        else:
            artifacts = list(self._artifacts.values())
        return sum(a.size_bytes for a in artifacts)

    @property
    def artifact_count(self) -> int:
        return len(self._artifacts)

    def stats(self) -> dict[str, Any]:
        """Get store statistics."""
        type_counts: dict[str, int] = {}
        for t, ids in self._by_type.items():
            type_counts[t] = len(ids)

        return {
            'total_artifacts': len(self._artifacts),
            'total_size_bytes': sum(a.size_bytes for a in self._artifacts.values()),
            'by_type': type_counts,
            'runs_tracked': len(self._by_run),
            'projects_tracked': len(self._by_project),
            'storage_dir': self._storage_dir or 'memory',
        }

    def _write_to_disk(self, artifact: StoredArtifact, content: Any) -> str:
        """Write artifact content to disk."""
        run_dir = os.path.join(
            self._storage_dir,
            artifact.run_id or 'unassigned',
        )
        os.makedirs(run_dir, exist_ok=True)

        file_path = os.path.join(run_dir, f'{artifact.artifact_id}_{artifact.name}')

        try:
            if isinstance(content, str):
                with open(file_path, 'w') as f:
                    f.write(content)
            elif isinstance(content, dict):
                with open(file_path, 'w') as f:
                    json.dump(content, f, indent=2, default=str)
            elif isinstance(content, bytes):
                with open(file_path, 'wb') as f:
                    f.write(content)
            else:
                with open(file_path, 'w') as f:
                    f.write(str(content))
        except Exception as e:
            logger.warning(f'[ArtifactStore] Failed to write {file_path}: {e}')
            return ''

        return file_path

    def _read_from_disk(self, artifact: StoredArtifact) -> Any | None:
        """Read artifact content from disk."""
        try:
            if artifact.name.endswith('.json'):
                with open(artifact.file_path) as f:
                    return json.load(f)
            else:
                with open(artifact.file_path) as f:
                    return f.read()
        except Exception as e:
            logger.warning(
                f'[ArtifactStore] Failed to read {artifact.file_path}: {e}'
            )
            return None
