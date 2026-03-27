"""Artifact Builder — assembles the final artifact bundle for a task.

Collects all outputs from the execution pipeline and packages them
into a structured artifact bundle: diffs, test results, PR description,
execution trace, logs, and metadata.

Patterns extracted from:
    - GPT-Pilot: ProjectFile artifact system
    - OpenHands: EventStream serialization
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class ArtifactType(Enum):
    """Types of artifacts produced by the system."""

    DIFF = 'diff'
    TEST_RESULT = 'test_result'
    PR_DESCRIPTION = 'pr_description'
    EXECUTION_TRACE = 'execution_trace'
    LOG = 'log'
    CODE_REVIEW = 'code_review'
    IMPACT_REPORT = 'impact_report'
    DEBUG_ANALYSIS = 'debug_analysis'
    METRICS = 'metrics'
    BUNDLE = 'bundle'


@dataclass
class Artifact:
    """A single artifact."""

    artifact_type: ArtifactType
    name: str
    content: Any = None
    file_path: str = ''
    size_bytes: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        art_type = self.artifact_type.value if isinstance(self.artifact_type, ArtifactType) else str(self.artifact_type)
        return {
            'type': art_type,
            'name': self.name,
            'file_path': self.file_path,
            'size_bytes': self.size_bytes,
            'created_at': self.created_at,
        }


@dataclass
class ArtifactBundle:
    """Complete artifact bundle for a task."""

    task_id: str = ''
    artifacts: list[Artifact] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    total_size_bytes: int = 0
    output_dir: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'artifact_count': len(self.artifacts),
            'total_size_bytes': self.total_size_bytes,
            'artifacts': [a.to_dict() for a in self.artifacts],
        }


class ArtifactBuilder:
    """Assembles the final artifact bundle from execution outputs.

    Usage:
        builder = ArtifactBuilder(task_id='task-123')
        builder.add_diff(diff_content)
        builder.add_test_result(test_output)
        builder.add_execution_trace(trace_data)
        bundle = builder.build(output_dir='/workspace/.artifacts/task-123')
    """

    def __init__(self, task_id: str = '') -> None:
        self._task_id = task_id
        self._artifacts: list[Artifact] = []

    def add_diff(self, diff_content: str, name: str = 'changes.diff') -> None:
        """Add a diff artifact."""
        self._artifacts.append(Artifact(
            artifact_type=ArtifactType.DIFF,
            name=name,
            content=diff_content,
            size_bytes=len(diff_content.encode()),
        ))

    def add_test_result(
        self, result: dict[str, Any], name: str = 'test_results.json'
    ) -> None:
        """Add test results artifact."""
        content = json.dumps(result, indent=2, default=str)
        self._artifacts.append(Artifact(
            artifact_type=ArtifactType.TEST_RESULT,
            name=name,
            content=result,
            size_bytes=len(content.encode()),
        ))

    def add_pr_description(
        self, description: str, name: str = 'pr_description.md'
    ) -> None:
        """Add PR description artifact."""
        self._artifacts.append(Artifact(
            artifact_type=ArtifactType.PR_DESCRIPTION,
            name=name,
            content=description,
            size_bytes=len(description.encode()),
        ))

    def add_execution_trace(
        self, trace: dict[str, Any], name: str = 'execution_trace.json'
    ) -> None:
        """Add execution trace artifact."""
        content = json.dumps(trace, indent=2, default=str)
        self._artifacts.append(Artifact(
            artifact_type=ArtifactType.EXECUTION_TRACE,
            name=name,
            content=trace,
            size_bytes=len(content.encode()),
        ))

    def add_log(self, log_content: str, name: str = 'execution.log') -> None:
        """Add log artifact."""
        self._artifacts.append(Artifact(
            artifact_type=ArtifactType.LOG,
            name=name,
            content=log_content,
            size_bytes=len(log_content.encode()),
        ))

    def add_code_review(
        self, review: dict[str, Any], name: str = 'code_review.json'
    ) -> None:
        """Add code review artifact."""
        content = json.dumps(review, indent=2, default=str)
        self._artifacts.append(Artifact(
            artifact_type=ArtifactType.CODE_REVIEW,
            name=name,
            content=review,
            size_bytes=len(content.encode()),
        ))

    def add_impact_report(
        self, report: dict[str, Any], name: str = 'impact_report.json'
    ) -> None:
        """Add impact analysis report artifact."""
        content = json.dumps(report, indent=2, default=str)
        self._artifacts.append(Artifact(
            artifact_type=ArtifactType.IMPACT_REPORT,
            name=name,
            content=report,
            size_bytes=len(content.encode()),
        ))

    def add_custom(
        self, artifact_type: ArtifactType, name: str, content: Any
    ) -> None:
        """Add a custom artifact."""
        if isinstance(content, str):
            size = len(content.encode())
        elif isinstance(content, dict):
            size = len(json.dumps(content, default=str).encode())
        else:
            size = 0

        self._artifacts.append(Artifact(
            artifact_type=artifact_type,
            name=name,
            content=content,
            size_bytes=size,
        ))

    def build(self, output_dir: str = '') -> ArtifactBundle:
        """Build the final artifact bundle.

        If output_dir is provided, writes all artifacts to disk.
        """
        total_size = sum(a.size_bytes for a in self._artifacts)

        bundle = ArtifactBundle(
            task_id=self._task_id,
            artifacts=list(self._artifacts),
            total_size_bytes=total_size,
            output_dir=output_dir,
        )

        if output_dir:
            self._write_to_disk(bundle, output_dir)

        logger.info(
            f'[ArtifactBuilder] Built bundle: {len(self._artifacts)} artifacts, '
            f'{total_size} bytes'
        )

        return bundle

    def _write_to_disk(self, bundle: ArtifactBundle, output_dir: str) -> None:
        """Write all artifacts to disk."""
        os.makedirs(output_dir, exist_ok=True)

        for artifact in bundle.artifacts:
            file_path = os.path.join(output_dir, artifact.name)
            artifact.file_path = file_path

            try:
                if isinstance(artifact.content, str):
                    with open(file_path, 'w') as f:
                        f.write(artifact.content)
                elif isinstance(artifact.content, dict):
                    with open(file_path, 'w') as f:
                        json.dump(artifact.content, f, indent=2, default=str)
                else:
                    with open(file_path, 'w') as f:
                        f.write(str(artifact.content))
            except Exception as e:
                logger.warning(f'[ArtifactBuilder] Failed to write {file_path}: {e}')

        # Write bundle manifest
        manifest_path = os.path.join(output_dir, 'manifest.json')
        try:
            with open(manifest_path, 'w') as f:
                json.dump(bundle.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.warning(f'[ArtifactBuilder] Failed to write manifest: {e}')

    @property
    def artifact_count(self) -> int:
        return len(self._artifacts)

    def list_artifacts(self) -> list[dict[str, Any]]:
        """List all artifacts in the builder."""
        return [a.to_dict() for a in self._artifacts]
