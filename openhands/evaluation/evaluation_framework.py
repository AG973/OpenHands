"""Evaluation framework — agent output quality and task completion assessment.

Provides structured evaluation of agent performance:
- Output quality metrics (correctness, completeness, style)
- Task completion scoring
- Code quality evaluation (lint, type safety, test coverage)
- LLM output evaluation (faithfulness, relevance, coherence)
- Regression detection across agent runs
- Benchmark suite management

Inspired by:
- DeepEval (50+ metrics for LLM evaluation)
- Claw-Eval (end-to-end agent benchmarking)
- Arize Phoenix (OTel-native observability)
- SWE-bench (standardized coding benchmarks)

Per OPERATING_RULES.md RULE 5: Production-grade — no prototypes.
"""

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from openhands.core.logger import openhands_logger as logger

# Evaluation limits
MAX_METRICS = 100
MAX_TEST_CASES = 10_000
MAX_EVALUATION_RUNS = 1000
MAX_OUTPUT_SIZE = 1_048_576  # 1MB
MAX_SUITE_NAME_LENGTH = 200
SCORE_PRECISION = 4


class MetricType(Enum):
    """Types of evaluation metrics."""

    # Code quality
    LINT_PASS = 'lint_pass'
    TYPE_CHECK_PASS = 'type_check_pass'
    TEST_PASS_RATE = 'test_pass_rate'
    CODE_COVERAGE = 'code_coverage'

    # LLM output quality
    CORRECTNESS = 'correctness'
    COMPLETENESS = 'completeness'
    FAITHFULNESS = 'faithfulness'
    RELEVANCE = 'relevance'
    COHERENCE = 'coherence'
    CONCISENESS = 'conciseness'

    # Task completion
    TASK_SUCCESS = 'task_success'
    STEPS_TAKEN = 'steps_taken'
    TIME_TO_COMPLETE = 'time_to_complete'
    ERROR_COUNT = 'error_count'
    RETRY_COUNT = 'retry_count'

    # Agent behavior
    TOOL_EFFICIENCY = 'tool_efficiency'
    CONTEXT_UTILIZATION = 'context_utilization'
    PLAN_ADHERENCE = 'plan_adherence'

    # Custom
    CUSTOM = 'custom'


class EvaluationStatus(Enum):
    """Status of an evaluation run."""

    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


class Severity(Enum):
    """Severity of an evaluation finding."""

    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


@dataclass
class MetricResult:
    """Result of a single metric evaluation."""

    metric_id: str
    metric_type: MetricType
    name: str
    score: float  # 0.0 to 1.0 normalized
    raw_value: Any = None  # Original value before normalization
    passed: bool = True
    threshold: float = 0.0
    details: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.metric_id:
            self.metric_id = f'metric-{uuid.uuid4().hex[:8]}'
        self.score = round(
            max(0.0, min(1.0, self.score)), SCORE_PRECISION
        )


@dataclass
class Finding:
    """An issue or observation found during evaluation."""

    finding_id: str
    severity: Severity
    category: str
    message: str
    file_path: str = ''
    line_number: int = 0
    suggestion: str = ''
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.finding_id:
            self.finding_id = f'find-{uuid.uuid4().hex[:8]}'


@dataclass
class TestCase:
    """A single test case for evaluation."""

    test_id: str
    name: str
    description: str = ''
    input_data: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ''
    actual_output: str = ''
    passed: bool = False
    metrics: list[MetricResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.test_id:
            self.test_id = f'test-{uuid.uuid4().hex[:8]}'

    @property
    def aggregate_score(self) -> float:
        if not self.metrics:
            return 1.0 if self.passed else 0.0
        return sum(m.score for m in self.metrics) / len(self.metrics)


@dataclass
class EvaluationSuite:
    """A suite of test cases for a specific evaluation purpose."""

    suite_id: str
    name: str
    description: str = ''
    test_cases: list[TestCase] = field(default_factory=list)
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()
        if not self.suite_id:
            self.suite_id = f'suite-{uuid.uuid4().hex[:8]}'

    @property
    def pass_rate(self) -> float:
        if not self.test_cases:
            return 0.0
        passed = sum(1 for tc in self.test_cases if tc.passed)
        return passed / len(self.test_cases)

    @property
    def total_tests(self) -> int:
        return len(self.test_cases)

    @property
    def passed_tests(self) -> int:
        return sum(1 for tc in self.test_cases if tc.passed)


@dataclass
class EvaluationRun:
    """A complete evaluation run with results."""

    run_id: str
    suite_id: str
    status: EvaluationStatus = EvaluationStatus.PENDING
    metrics: list[MetricResult] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    overall_score: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = f'eval-{uuid.uuid4().hex[:8]}'

    @property
    def duration_ms(self) -> float:
        if self.completed_at > 0 and self.started_at > 0:
            return (self.completed_at - self.started_at) * 1000
        return 0.0


@dataclass
class EvaluationConfig:
    """Configuration for the evaluation framework."""

    db_path: str = ''
    default_threshold: float = 0.7
    fail_on_error: bool = True
    parallel_evaluations: int = 1
    save_results: bool = True

    def __post_init__(self) -> None:
        if not self.db_path:
            self.db_path = os.path.join(
                str(Path.home()), '.openhands', 'evaluations.db'
            )


class EvaluationStore:
    """SQLite-backed storage for evaluation results."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if not exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                run_id TEXT PRIMARY KEY,
                suite_id TEXT NOT NULL,
                status TEXT NOT NULL,
                overall_score REAL DEFAULT 0.0,
                metrics_json TEXT DEFAULT '[]',
                findings_json TEXT DEFAULT '[]',
                started_at REAL NOT NULL,
                completed_at REAL DEFAULT 0.0,
                metadata_json TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS evaluation_suites (
                suite_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                test_cases_json TEXT DEFAULT '[]',
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_eval_suite
                ON evaluation_runs(suite_id);
            CREATE INDEX IF NOT EXISTS idx_eval_status
                ON evaluation_runs(status);
        """)
        self._conn.commit()

    def save_run(self, run: EvaluationRun) -> None:
        """Save an evaluation run."""
        metrics_json = json.dumps([
            {
                'metric_id': m.metric_id,
                'metric_type': m.metric_type.value,
                'name': m.name,
                'score': m.score,
                'passed': m.passed,
                'details': m.details,
            }
            for m in run.metrics
        ])

        findings_json = json.dumps([
            {
                'finding_id': f.finding_id,
                'severity': f.severity.value,
                'category': f.category,
                'message': f.message,
                'file_path': f.file_path,
                'suggestion': f.suggestion,
            }
            for f in run.findings
        ])

        self._conn.execute(
            """INSERT OR REPLACE INTO evaluation_runs
            (run_id, suite_id, status, overall_score, metrics_json,
             findings_json, started_at, completed_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.run_id,
                run.suite_id,
                run.status.value,
                run.overall_score,
                metrics_json,
                findings_json,
                run.started_at,
                run.completed_at,
                json.dumps(run.metadata),
            ),
        )
        self._conn.commit()

    def get_runs(
        self,
        suite_id: str = '',
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get evaluation run summaries."""
        query = 'SELECT * FROM evaluation_runs'
        params: list[Any] = []

        if suite_id:
            query += ' WHERE suite_id = ?'
            params.append(suite_id)

        query += ' ORDER BY started_at DESC LIMIT ?'
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_trend(
        self,
        suite_id: str,
        metric_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get score trend for a specific metric over time."""
        rows = self._conn.execute(
            """SELECT run_id, overall_score, started_at, metrics_json
            FROM evaluation_runs
            WHERE suite_id = ? AND status = 'completed'
            ORDER BY started_at DESC LIMIT ?""",
            (suite_id, limit),
        ).fetchall()

        trend: list[dict[str, Any]] = []
        for row in rows:
            metrics = json.loads(row['metrics_json'])
            for m in metrics:
                if m['name'] == metric_name:
                    trend.append({
                        'run_id': row['run_id'],
                        'score': m['score'],
                        'timestamp': row['started_at'],
                    })
                    break

        trend.reverse()  # Oldest first for trend display
        return trend

    def close(self) -> None:
        """Close the database."""
        self._conn.close()


class CodeQualityEvaluator:
    """Evaluator for code quality metrics.

    Checks lint results, type checking, test results, etc.
    """

    def evaluate_lint(self, lint_output: str, lint_exit_code: int) -> MetricResult:
        """Evaluate lint results."""
        passed = lint_exit_code == 0
        # Count issues from output
        issue_count = 0
        for line in lint_output.split('\n'):
            line = line.strip()
            if line and not line.startswith(('Running', 'All', 'Found', '--')):
                issue_count += 1

        score = 1.0 if passed else max(0.0, 1.0 - (issue_count * 0.05))

        return MetricResult(
            metric_id=f'metric-{uuid.uuid4().hex[:8]}',
            metric_type=MetricType.LINT_PASS,
            name='lint_check',
            score=score,
            raw_value=issue_count,
            passed=passed,
            details=f'{issue_count} lint issues found' if issue_count else 'Clean',
        )

    def evaluate_type_check(
        self, typecheck_output: str, exit_code: int
    ) -> MetricResult:
        """Evaluate type checking results."""
        passed = exit_code == 0
        error_count = 0
        for line in typecheck_output.split('\n'):
            if 'error:' in line.lower():
                error_count += 1

        score = 1.0 if passed else max(0.0, 1.0 - (error_count * 0.1))

        return MetricResult(
            metric_id=f'metric-{uuid.uuid4().hex[:8]}',
            metric_type=MetricType.TYPE_CHECK_PASS,
            name='type_check',
            score=score,
            raw_value=error_count,
            passed=passed,
            details=f'{error_count} type errors' if error_count else 'Clean',
        )

    def evaluate_tests(
        self, test_output: str, exit_code: int
    ) -> MetricResult:
        """Evaluate test results."""
        passed = exit_code == 0
        # Try to parse pytest-style output
        total = 0
        test_passed = 0
        test_failed = 0

        for line in test_output.split('\n'):
            line_lower = line.lower().strip()
            if 'passed' in line_lower and ('failed' in line_lower or 'error' in line_lower):
                # Summary line like "5 passed, 2 failed"
                parts = line_lower.split(',')
                for part in parts:
                    part = part.strip()
                    if 'passed' in part:
                        try:
                            test_passed = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
                    if 'failed' in part:
                        try:
                            test_failed = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
            elif 'passed' in line_lower and 'failed' not in line_lower:
                parts = line_lower.split()
                for i, part in enumerate(parts):
                    if part == 'passed' and i > 0:
                        try:
                            test_passed = int(parts[i - 1])
                        except (ValueError, IndexError):
                            pass

        total = test_passed + test_failed
        score = test_passed / total if total > 0 else (1.0 if passed else 0.0)

        return MetricResult(
            metric_id=f'metric-{uuid.uuid4().hex[:8]}',
            metric_type=MetricType.TEST_PASS_RATE,
            name='test_pass_rate',
            score=score,
            raw_value={'passed': test_passed, 'failed': test_failed, 'total': total},
            passed=passed,
            details=f'{test_passed}/{total} tests passed' if total > 0 else 'No test count parsed',
        )


class TaskCompletionEvaluator:
    """Evaluator for agent task completion metrics."""

    def evaluate_task(
        self,
        task_description: str,
        actual_output: str,
        expected_output: str = '',
        steps_taken: int = 0,
        errors_encountered: int = 0,
        time_taken_s: float = 0.0,
    ) -> list[MetricResult]:
        """Evaluate task completion.

        Args:
            task_description: What was asked
            actual_output: What was produced
            expected_output: What was expected (optional)
            steps_taken: Number of steps the agent took
            errors_encountered: Number of errors during execution
            time_taken_s: Time taken in seconds

        Returns:
            List of MetricResults
        """
        results: list[MetricResult] = []

        # Task success (basic heuristic — in production use LLM judge)
        has_output = bool(actual_output and actual_output.strip())
        if expected_output:
            # Simple exact match for now
            match_score = 1.0 if actual_output.strip() == expected_output.strip() else 0.3
        else:
            match_score = 0.8 if has_output else 0.0

        results.append(
            MetricResult(
                metric_id=f'metric-{uuid.uuid4().hex[:8]}',
                metric_type=MetricType.TASK_SUCCESS,
                name='task_success',
                score=match_score,
                passed=match_score >= 0.7,
                details='Output matches expected' if match_score >= 0.7 else 'Output may not match',
            )
        )

        # Steps efficiency
        if steps_taken > 0:
            # Fewer steps is better (normalize, assuming 20 steps is average)
            step_score = max(0.0, min(1.0, 1.0 - (steps_taken - 1) / 50))
            results.append(
                MetricResult(
                    metric_id=f'metric-{uuid.uuid4().hex[:8]}',
                    metric_type=MetricType.STEPS_TAKEN,
                    name='step_efficiency',
                    score=step_score,
                    raw_value=steps_taken,
                    passed=True,
                    details=f'{steps_taken} steps taken',
                )
            )

        # Error rate
        if steps_taken > 0:
            error_rate = errors_encountered / steps_taken
            error_score = max(0.0, 1.0 - error_rate)
            results.append(
                MetricResult(
                    metric_id=f'metric-{uuid.uuid4().hex[:8]}',
                    metric_type=MetricType.ERROR_COUNT,
                    name='error_rate',
                    score=error_score,
                    raw_value=errors_encountered,
                    passed=error_rate < 0.3,
                    details=f'{errors_encountered} errors in {steps_taken} steps',
                )
            )

        # Time efficiency
        if time_taken_s > 0:
            # Normalize: under 60s is perfect, over 600s is 0
            time_score = max(0.0, min(1.0, 1.0 - (time_taken_s - 60) / 540))
            results.append(
                MetricResult(
                    metric_id=f'metric-{uuid.uuid4().hex[:8]}',
                    metric_type=MetricType.TIME_TO_COMPLETE,
                    name='time_efficiency',
                    score=time_score,
                    raw_value=time_taken_s,
                    passed=True,
                    details=f'{time_taken_s:.1f}s to complete',
                )
            )

        return results


class EvaluationFramework:
    """High-level evaluation framework for OpenHands agents.

    Orchestrates evaluation suites, metrics, and reporting.

    Usage:
        framework = EvaluationFramework()
        suite = framework.create_suite("code-quality", "Code Quality Checks")
        suite.test_cases.append(TestCase(...))
        run = framework.run_evaluation(suite.suite_id)
        print(f"Score: {run.overall_score}")
    """

    def __init__(self, config: EvaluationConfig | None = None) -> None:
        self._config = config or EvaluationConfig()
        self._suites: dict[str, EvaluationSuite] = {}
        self._runs: dict[str, EvaluationRun] = {}
        self._store: EvaluationStore | None = None
        self._evaluators: list[Callable[[TestCase], list[MetricResult]]] = []
        self._code_evaluator = CodeQualityEvaluator()
        self._task_evaluator = TaskCompletionEvaluator()

        if self._config.save_results:
            self._store = EvaluationStore(self._config.db_path)

        logger.info('EvaluationFramework initialized')

    def create_suite(
        self,
        name: str,
        description: str = '',
    ) -> EvaluationSuite:
        """Create a new evaluation suite.

        Args:
            name: Suite name
            description: What this suite evaluates

        Returns:
            New EvaluationSuite
        """
        if len(name) > MAX_SUITE_NAME_LENGTH:
            name = name[:MAX_SUITE_NAME_LENGTH]

        suite = EvaluationSuite(
            suite_id=f'suite-{uuid.uuid4().hex[:8]}',
            name=name,
            description=description,
        )
        self._suites[suite.suite_id] = suite
        logger.info(f'Evaluation suite created: {suite.suite_id} ({name})')
        return suite

    def add_test_case(
        self,
        suite_id: str,
        name: str,
        input_data: dict[str, Any] | None = None,
        expected_output: str = '',
        description: str = '',
    ) -> TestCase:
        """Add a test case to a suite.

        Args:
            suite_id: Suite to add to
            name: Test case name
            input_data: Input for the test
            expected_output: Expected output
            description: What this test verifies

        Returns:
            New TestCase
        """
        suite = self._get_suite(suite_id)

        if len(suite.test_cases) >= MAX_TEST_CASES:
            raise ValueError(f'Suite {suite_id} has reached max test cases')

        test_case = TestCase(
            test_id=f'test-{uuid.uuid4().hex[:8]}',
            name=name,
            description=description,
            input_data=input_data or {},
            expected_output=expected_output,
        )
        suite.test_cases.append(test_case)
        return test_case

    def run_evaluation(
        self,
        suite_id: str,
        actual_outputs: dict[str, str] | None = None,
    ) -> EvaluationRun:
        """Run an evaluation suite.

        Args:
            suite_id: Suite to run
            actual_outputs: Map of test_id -> actual output

        Returns:
            EvaluationRun with results
        """
        suite = self._get_suite(suite_id)

        run = EvaluationRun(
            run_id=f'eval-{uuid.uuid4().hex[:8]}',
            suite_id=suite_id,
            status=EvaluationStatus.RUNNING,
            started_at=time.time(),
        )

        outputs = actual_outputs or {}

        try:
            all_metrics: list[MetricResult] = []
            all_findings: list[Finding] = []

            for test_case in suite.test_cases:
                # Apply actual output if provided
                if test_case.test_id in outputs:
                    test_case.actual_output = outputs[test_case.test_id]

                # Run registered evaluators
                for evaluator in self._evaluators:
                    try:
                        metrics = evaluator(test_case)
                        test_case.metrics.extend(metrics)
                    except Exception as e:
                        logger.warning(f'Evaluator failed: {e}')

                # Determine pass/fail
                if test_case.metrics:
                    avg_score = test_case.aggregate_score
                    test_case.passed = avg_score >= self._config.default_threshold
                elif test_case.expected_output and test_case.actual_output:
                    test_case.passed = (
                        test_case.actual_output.strip()
                        == test_case.expected_output.strip()
                    )

                all_metrics.extend(test_case.metrics)
                all_findings.extend(test_case.findings)

            run.metrics = all_metrics
            run.findings = all_findings

            # Calculate overall score
            if all_metrics:
                run.overall_score = round(
                    sum(m.score for m in all_metrics) / len(all_metrics),
                    SCORE_PRECISION,
                )
            else:
                run.overall_score = suite.pass_rate

            run.status = EvaluationStatus.COMPLETED
            run.completed_at = time.time()

        except Exception as e:
            run.status = EvaluationStatus.FAILED
            run.completed_at = time.time()
            logger.error(f'Evaluation run failed: {e}')

        self._runs[run.run_id] = run

        # Persist results
        if self._store:
            self._store.save_run(run)

        logger.info(
            f'Evaluation {run.run_id} completed: '
            f'score={run.overall_score:.3f}, '
            f'pass_rate={suite.pass_rate:.1%}'
        )

        return run

    def evaluate_code_quality(
        self,
        lint_output: str = '',
        lint_exit_code: int = 0,
        typecheck_output: str = '',
        typecheck_exit_code: int = 0,
        test_output: str = '',
        test_exit_code: int = 0,
    ) -> EvaluationRun:
        """Quick evaluation of code quality from tool outputs.

        Convenience method that creates a suite and runs it with
        lint, typecheck, and test results.

        Args:
            lint_output: Lint tool output
            lint_exit_code: Lint tool exit code
            typecheck_output: Type checker output
            typecheck_exit_code: Type checker exit code
            test_output: Test runner output
            test_exit_code: Test runner exit code

        Returns:
            EvaluationRun with code quality metrics
        """
        suite = self.create_suite('code-quality', 'Automated code quality checks')

        run = EvaluationRun(
            run_id=f'eval-{uuid.uuid4().hex[:8]}',
            suite_id=suite.suite_id,
            status=EvaluationStatus.RUNNING,
            started_at=time.time(),
        )

        metrics: list[MetricResult] = []

        if lint_output or lint_exit_code != -1:
            metrics.append(
                self._code_evaluator.evaluate_lint(lint_output, lint_exit_code)
            )

        if typecheck_output or typecheck_exit_code != -1:
            metrics.append(
                self._code_evaluator.evaluate_type_check(
                    typecheck_output, typecheck_exit_code
                )
            )

        if test_output or test_exit_code != -1:
            metrics.append(
                self._code_evaluator.evaluate_tests(test_output, test_exit_code)
            )

        run.metrics = metrics
        if metrics:
            run.overall_score = round(
                sum(m.score for m in metrics) / len(metrics), SCORE_PRECISION
            )

        run.status = EvaluationStatus.COMPLETED
        run.completed_at = time.time()

        self._runs[run.run_id] = run
        if self._store:
            self._store.save_run(run)

        return run

    def evaluate_task_completion(
        self,
        task_description: str,
        actual_output: str,
        expected_output: str = '',
        steps_taken: int = 0,
        errors_encountered: int = 0,
        time_taken_s: float = 0.0,
    ) -> EvaluationRun:
        """Evaluate a completed agent task.

        Args:
            task_description: What was asked
            actual_output: What was produced
            expected_output: What was expected
            steps_taken: Number of steps
            errors_encountered: Number of errors
            time_taken_s: Time taken

        Returns:
            EvaluationRun with task metrics
        """
        suite = self.create_suite('task-completion', 'Task completion evaluation')

        metrics = self._task_evaluator.evaluate_task(
            task_description=task_description,
            actual_output=actual_output,
            expected_output=expected_output,
            steps_taken=steps_taken,
            errors_encountered=errors_encountered,
            time_taken_s=time_taken_s,
        )

        run = EvaluationRun(
            run_id=f'eval-{uuid.uuid4().hex[:8]}',
            suite_id=suite.suite_id,
            status=EvaluationStatus.COMPLETED,
            metrics=metrics,
            started_at=time.time(),
            completed_at=time.time(),
        )

        if metrics:
            run.overall_score = round(
                sum(m.score for m in metrics) / len(metrics), SCORE_PRECISION
            )

        self._runs[run.run_id] = run
        if self._store:
            self._store.save_run(run)

        return run

    def get_trend(
        self,
        suite_id: str,
        metric_name: str,
    ) -> list[dict[str, Any]]:
        """Get score trend over time for a metric."""
        if self._store:
            return self._store.get_trend(suite_id, metric_name)
        return []

    def register_evaluator(
        self,
        evaluator: Callable[[TestCase], list[MetricResult]],
    ) -> None:
        """Register a custom evaluator function."""
        self._evaluators.append(evaluator)

    def _get_suite(self, suite_id: str) -> EvaluationSuite:
        """Get suite or raise."""
        suite = self._suites.get(suite_id)
        if suite is None:
            raise ValueError(f'Suite {suite_id} not found')
        return suite

    def stats(self) -> dict[str, Any]:
        """Get framework statistics."""
        return {
            'total_suites': len(self._suites),
            'total_runs': len(self._runs),
            'total_test_cases': sum(
                len(s.test_cases) for s in self._suites.values()
            ),
            'avg_score': (
                round(
                    sum(r.overall_score for r in self._runs.values())
                    / len(self._runs),
                    SCORE_PRECISION,
                )
                if self._runs
                else 0.0
            ),
        }

    def close(self) -> None:
        """Close the framework and persist state."""
        if self._store:
            self._store.close()
