"""Execution Engine — deterministic task lifecycle for the engineering operating system.

This is the CORE of the system. All tasks flow through the execution engine's
state machine: INTAKE -> CONTEXT_BUILD -> REPO_ANALYSIS -> PLAN -> EXECUTE ->
TEST -> FAILURE_ANALYSIS -> RETRY_OR_FIX -> REVIEW -> ARTIFACT_GENERATION -> COMPLETE.

This module replaces the reactive AgentController loop with a deterministic,
graph-driven execution pipeline.
"""

from openhands.execution.task_models import (
    Task,
    TaskArtifact,
    TaskContext,
    TaskPriority,
    TaskResult,
)
from openhands.execution.task_state_machine import TaskPhase, TaskStateMachine
from openhands.execution.task_runner import TaskRunner
from openhands.execution.task_engine import TaskEngine

__all__ = [
    'Task',
    'TaskArtifact',
    'TaskContext',
    'TaskEngine',
    'TaskPhase',
    'TaskPriority',
    'TaskResult',
    'TaskRunner',
    'TaskStateMachine',
]
