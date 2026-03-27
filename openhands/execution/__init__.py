"""Execution Engine — the canonical task lifecycle for CODEIT OS.

This package contains the core execution pipeline that drives every task
from intake to completion. It replaces the legacy AgentController step loop
with a deterministic, phase-driven execution graph.

Modules:
    task_models: Core data structures (Task, TaskContext, TaskResult)
    task_state_machine: Deterministic phase transitions
    task_runner: Phase handler execution
    task_engine: Central orchestrator
"""

from openhands.execution.task_engine import TaskEngine
from openhands.execution.task_models import (
    Task,
    TaskArtifact,
    TaskContext,
    TaskPriority,
    TaskResult,
    TaskType,
)
from openhands.execution.task_runner import PhaseResult, TaskRunner
from openhands.execution.task_state_machine import (
    TaskPhase,
    TaskStateMachine,
    TransitionError,
)

__all__ = [
    'TaskEngine',
    'TaskRunner',
    'TaskStateMachine',
    'TaskPhase',
    'TransitionError',
    'Task',
    'TaskContext',
    'TaskResult',
    'TaskArtifact',
    'TaskType',
    'TaskPriority',
    'PhaseResult',
]
