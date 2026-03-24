"""Reflexion engine — self-reflection and verbal reinforcement learning.

Implements the Reflexion framework (NeurIPS 2023) for agent self-improvement:
- Agent generates output, receives feedback, reflects on failures
- Reflective text stored in episodic memory buffer
- Subsequent attempts use reflections to improve decisions
- Supports both external feedback (test results, errors) and internal self-critique

This transforms the agent from "try once and hope" to
"try, reflect, learn, try better."

Per OPERATING_RULES.md RULE 5: Production-grade — no prototypes.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from openhands.core.logger import openhands_logger as logger

# Reflexion limits
MAX_REFLECTIONS = 50
MAX_TRIALS = 10
MAX_REFLECTION_LENGTH = 5000
MAX_FEEDBACK_LENGTH = 10_000
MAX_MEMORY_ENTRIES = 200


class TrialOutcome(Enum):
    """Outcome of an agent trial/attempt."""

    SUCCESS = 'success'
    PARTIAL = 'partial'  # Some objectives met
    FAILURE = 'failure'
    ERROR = 'error'  # Exception/crash
    TIMEOUT = 'timeout'


class ReflectionType(Enum):
    """Types of reflection the agent can perform."""

    SELF_CRITIQUE = 'self_critique'  # Agent evaluates own output
    ERROR_ANALYSIS = 'error_analysis'  # Analyze why something failed
    STRATEGY_REVISION = 'strategy_revision'  # Revise approach
    KNOWLEDGE_GAP = 'knowledge_gap'  # Identify missing knowledge
    PATTERN_RECOGNITION = 'pattern_recognition'  # Recognize repeated mistakes


class FeedbackSource(Enum):
    """Where feedback comes from."""

    TEST_RESULT = 'test_result'  # Automated test pass/fail
    COMPILER = 'compiler'  # Compilation errors
    RUNTIME = 'runtime'  # Runtime errors/exceptions
    USER = 'user'  # Human feedback
    SELF = 'self'  # Agent self-evaluation
    LINT = 'lint'  # Linter warnings/errors
    CI = 'ci'  # CI pipeline results


@dataclass
class Feedback:
    """Feedback signal for an agent trial."""

    feedback_id: str
    source: FeedbackSource
    content: str
    is_positive: bool = False
    score: float = 0.0  # 0.0 = worst, 1.0 = best
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if len(self.content) > MAX_FEEDBACK_LENGTH:
            self.content = self.content[:MAX_FEEDBACK_LENGTH]


@dataclass
class Reflection:
    """A self-reflection entry from the agent."""

    reflection_id: str
    reflection_type: ReflectionType
    content: str  # The verbal reflection text
    trial_id: str  # Which trial this reflects on
    task_id: str  # Which task this is part of
    lessons: list[str] = field(default_factory=list)
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()
        if len(self.content) > MAX_REFLECTION_LENGTH:
            self.content = self.content[:MAX_REFLECTION_LENGTH]


@dataclass
class Trial:
    """A single attempt at completing a task."""

    trial_id: str
    task_id: str
    trial_number: int  # 1-indexed
    action_taken: str  # What the agent did
    output: str  # What was produced
    outcome: TrialOutcome = TrialOutcome.FAILURE
    feedback: list[Feedback] = field(default_factory=list)
    reflections: list[Reflection] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.started_at == 0.0:
            self.started_at = time.time()

    @property
    def duration_s(self) -> float:
        if self.completed_at > 0:
            return self.completed_at - self.started_at
        return time.time() - self.started_at

    @property
    def aggregate_score(self) -> float:
        """Average feedback score."""
        if not self.feedback:
            return 0.0
        return sum(f.score for f in self.feedback) / len(self.feedback)


@dataclass
class ReflexionTask:
    """A task being worked on with the Reflexion pattern."""

    task_id: str
    description: str
    success_criteria: str = ''
    trials: list[Trial] = field(default_factory=list)
    best_trial_id: str = ''
    is_complete: bool = False
    created_at: float = 0.0
    max_trials: int = MAX_TRIALS

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def current_trial_number(self) -> int:
        return len(self.trials)

    @property
    def has_succeeded(self) -> bool:
        return any(t.outcome == TrialOutcome.SUCCESS for t in self.trials)

    @property
    def best_score(self) -> float:
        if not self.trials:
            return 0.0
        return max(t.aggregate_score for t in self.trials)

    @property
    def is_improving(self) -> bool:
        """Check if scores are trending upward."""
        if len(self.trials) < 2:
            return False
        scores = [t.aggregate_score for t in self.trials]
        return scores[-1] > scores[-2]


class ReflexionEngine:
    """Reflexion-based self-improvement engine for OpenHands agents.

    Implements the core Reflexion loop:
    1. Agent attempts task (Trial)
    2. Receives feedback (external or self-generated)
    3. Reflects on what went wrong and why
    4. Stores reflection in episodic memory
    5. Uses reflections to improve next attempt

    The engine doesn't execute tasks itself — it manages the reflection
    cycle and provides context for the agent loop to make better decisions.
    """

    def __init__(self, max_trials: int = MAX_TRIALS) -> None:
        self._tasks: dict[str, ReflexionTask] = {}
        self._reflections: list[Reflection] = []
        self._max_trials = min(max_trials, MAX_TRIALS)
        self._evaluators: list[Callable[[Trial], Feedback]] = []
        self._on_reflection: list[Callable[[Reflection], None]] = []

    def create_task(
        self,
        description: str,
        success_criteria: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> ReflexionTask:
        """Create a new task to work on with Reflexion.

        Args:
            description: What needs to be accomplished
            success_criteria: How to determine success
            metadata: Additional task context

        Returns:
            New ReflexionTask
        """
        task_id = f'rtask-{uuid.uuid4().hex[:8]}'
        task = ReflexionTask(
            task_id=task_id,
            description=description,
            success_criteria=success_criteria,
            max_trials=self._max_trials,
        )
        self._tasks[task_id] = task
        logger.info(f'Reflexion task created: {task_id} — {description[:100]}')
        return task

    def start_trial(
        self,
        task_id: str,
        action: str,
    ) -> Trial:
        """Start a new trial for a task.

        Args:
            task_id: Task to attempt
            action: Description of what the agent will do

        Returns:
            New Trial object

        Raises:
            ValueError: If task not found or max trials exceeded
        """
        task = self._get_task(task_id)

        if task.current_trial_number >= task.max_trials:
            raise ValueError(
                f'Task {task_id} has reached max trials ({task.max_trials})'
            )

        trial = Trial(
            trial_id=f'trial-{uuid.uuid4().hex[:8]}',
            task_id=task_id,
            trial_number=task.current_trial_number + 1,
            action_taken=action,
            output='',
        )
        task.trials.append(trial)

        logger.info(
            f'Trial {trial.trial_number}/{task.max_trials} started for {task_id}'
        )
        return trial

    def complete_trial(
        self,
        task_id: str,
        trial_id: str,
        output: str,
        outcome: TrialOutcome,
        feedback: list[Feedback] | None = None,
    ) -> Trial:
        """Complete a trial with results and feedback.

        Args:
            task_id: Task ID
            trial_id: Trial to complete
            output: What was produced
            outcome: Success/failure/etc
            feedback: External feedback signals

        Returns:
            Updated Trial
        """
        task = self._get_task(task_id)
        trial = self._find_trial(task, trial_id)

        trial.output = output
        trial.outcome = outcome
        trial.completed_at = time.time()

        if feedback:
            trial.feedback.extend(feedback)

        # Run registered evaluators
        for evaluator in self._evaluators:
            try:
                eval_feedback = evaluator(trial)
                trial.feedback.append(eval_feedback)
            except Exception as e:
                logger.warning(f'Evaluator failed: {e}')

        # Track best trial
        if not task.best_trial_id or trial.aggregate_score > self._get_best_score(task):
            task.best_trial_id = trial_id

        # Mark complete on success
        if outcome == TrialOutcome.SUCCESS:
            task.is_complete = True

        logger.info(
            f'Trial {trial.trial_number} completed: '
            f'outcome={outcome.value}, score={trial.aggregate_score:.2f}'
        )

        return trial

    def reflect(
        self,
        task_id: str,
        trial_id: str,
        reflection_text: str,
        reflection_type: ReflectionType = ReflectionType.SELF_CRITIQUE,
        lessons: list[str] | None = None,
    ) -> Reflection:
        """Record a reflection on a completed trial.

        This is where the "verbal reinforcement learning" happens.
        The reflection text captures:
        - What went wrong
        - Why it went wrong
        - What to do differently next time

        Args:
            task_id: Task ID
            trial_id: Trial being reflected on
            reflection_text: The agent's self-reflection
            reflection_type: Type of reflection
            lessons: Specific lessons learned

        Returns:
            New Reflection object
        """
        task = self._get_task(task_id)
        self._find_trial(task, trial_id)  # Validate trial exists

        reflection = Reflection(
            reflection_id=f'ref-{uuid.uuid4().hex[:8]}',
            reflection_type=reflection_type,
            content=reflection_text,
            trial_id=trial_id,
            task_id=task_id,
            lessons=lessons or [],
        )

        # Add to trial
        for trial in task.trials:
            if trial.trial_id == trial_id:
                trial.reflections.append(reflection)
                break

        # Add to global reflection memory
        if len(self._reflections) >= MAX_MEMORY_ENTRIES:
            self._reflections = self._reflections[-(MAX_MEMORY_ENTRIES - 1):]
        self._reflections.append(reflection)

        # Notify handlers
        for handler in self._on_reflection:
            try:
                handler(reflection)
            except Exception as e:
                logger.warning(f'Reflection handler error: {e}')

        logger.info(
            f'Reflection recorded for trial {trial_id}: '
            f'{reflection_text[:80]}...'
        )
        return reflection

    def get_reflection_context(
        self,
        task_id: str,
        max_reflections: int = 5,
    ) -> str:
        """Get formatted reflection context for the next trial attempt.

        Returns previous reflections as a prompt-friendly string that
        helps the agent avoid repeating past mistakes.

        Args:
            task_id: Task to get reflections for
            max_reflections: Maximum reflections to include

        Returns:
            Formatted reflection context string
        """
        task = self._get_task(task_id)
        parts: list[str] = []

        if not task.trials:
            return ''

        parts.append('## Previous Attempts and Reflections\n')

        for trial in task.trials[-max_reflections:]:
            parts.append(
                f'### Trial {trial.trial_number} '
                f'(outcome: {trial.outcome.value}, '
                f'score: {trial.aggregate_score:.2f})\n'
            )
            parts.append(f'Action: {trial.action_taken[:200]}\n')

            if trial.feedback:
                parts.append('Feedback:\n')
                for fb in trial.feedback[:3]:
                    parts.append(
                        f'  - [{fb.source.value}] {fb.content[:200]}\n'
                    )

            if trial.reflections:
                parts.append('Reflections:\n')
                for ref in trial.reflections:
                    parts.append(f'  - {ref.content[:300]}\n')
                    if ref.lessons:
                        for lesson in ref.lessons[:3]:
                            parts.append(f'    * Lesson: {lesson[:150]}\n')

            parts.append('\n')

        return ''.join(parts)

    def get_lessons_learned(self, task_id: str | None = None) -> list[str]:
        """Get all lessons learned, optionally filtered by task.

        Args:
            task_id: Filter by specific task (None = all tasks)

        Returns:
            List of lesson strings
        """
        lessons: list[str] = []
        reflections = self._reflections

        if task_id:
            reflections = [r for r in reflections if r.task_id == task_id]

        for ref in reflections:
            lessons.extend(ref.lessons)

        return lessons

    def should_continue(self, task_id: str) -> bool:
        """Determine if the agent should continue trying.

        Returns False if:
        - Task is complete (success)
        - Max trials reached
        - No improvement over last 3 trials

        Args:
            task_id: Task to check

        Returns:
            True if agent should try again
        """
        task = self._get_task(task_id)

        if task.is_complete:
            return False

        if task.current_trial_number >= task.max_trials:
            logger.info(f'Task {task_id}: max trials reached')
            return False

        # Check for stagnation (no improvement in 3+ trials)
        if len(task.trials) >= 3:
            recent_scores = [
                t.aggregate_score for t in task.trials[-3:]
            ]
            if all(s == recent_scores[0] for s in recent_scores):
                logger.info(f'Task {task_id}: stagnant scores, stopping')
                return False

        return True

    def register_evaluator(
        self, evaluator: Callable[[Trial], Feedback]
    ) -> None:
        """Register an automatic evaluator that runs on trial completion."""
        self._evaluators.append(evaluator)

    def on_reflection(
        self, handler: Callable[[Reflection], None]
    ) -> None:
        """Register a handler called when reflections are recorded."""
        self._on_reflection.append(handler)

    def get_task(self, task_id: str) -> ReflexionTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def _get_task(self, task_id: str) -> ReflexionTask:
        """Get task or raise."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f'Task {task_id} not found')
        return task

    def _find_trial(self, task: ReflexionTask, trial_id: str) -> Trial:
        """Find a trial in a task or raise."""
        for trial in task.trials:
            if trial.trial_id == trial_id:
                return trial
        raise ValueError(
            f'Trial {trial_id} not found in task {task.task_id}'
        )

    def _get_best_score(self, task: ReflexionTask) -> float:
        """Get the best score from a task's trials."""
        if not task.best_trial_id:
            return 0.0
        for trial in task.trials:
            if trial.trial_id == task.best_trial_id:
                return trial.aggregate_score
        return 0.0

    def stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        total_trials = sum(len(t.trials) for t in self._tasks.values())
        successes = sum(
            1
            for t in self._tasks.values()
            for trial in t.trials
            if trial.outcome == TrialOutcome.SUCCESS
        )

        return {
            'total_tasks': len(self._tasks),
            'completed_tasks': sum(
                1 for t in self._tasks.values() if t.is_complete
            ),
            'total_trials': total_trials,
            'success_rate': successes / total_trials if total_trials > 0 else 0.0,
            'total_reflections': len(self._reflections),
            'total_lessons': sum(
                len(r.lessons) for r in self._reflections
            ),
        }
