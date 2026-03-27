"""Metrics Collector — tracks performance and operational metrics.

Collects quantitative metrics across all subsystems for monitoring,
optimization, and reporting. Supports counters, gauges, histograms,
and timing measurements.

Patterns extracted from:
    - OpenHands: Runtime metrics and telemetry
    - Production observability: Prometheus-style metric collection
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openhands.core.logger import openhands_logger as logger


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = 'counter'  # Monotonically increasing
    GAUGE = 'gauge'  # Current value
    HISTOGRAM = 'histogram'  # Distribution of values
    TIMER = 'timer'  # Duration measurements


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    metric_type: MetricType
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and queries operational metrics.

    Usage:
        metrics = MetricsCollector()

        # Counters
        metrics.increment('tasks_completed', labels={'type': 'bug_fix'})
        metrics.increment('errors_total', labels={'phase': 'test'})

        # Gauges
        metrics.set_gauge('active_tasks', 3)

        # Timers
        metrics.record_duration('phase_duration', 12.5, labels={'phase': 'execute'})

        # Histograms
        metrics.record_value('file_count', 42)

        # Query
        report = metrics.get_report()
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._timers: dict[str, list[float]] = {}
        self._points: list[MetricPoint] = []
        self._timer_starts: dict[str, float] = {}

    # --- Counters ---

    def increment(
        self, name: str, value: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
        self._points.append(MetricPoint(
            name=name,
            metric_type=MetricType.COUNTER,
            value=self._counters[key],
            labels=labels or {},
        ))

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get current counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)

    # --- Gauges ---

    def set_gauge(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Set a gauge value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get current gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0)

    # --- Histograms ---

    def record_value(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        """Record a value in a histogram."""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def get_histogram_stats(
        self, name: str, labels: dict[str, str] | None = None
    ) -> dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {'count': 0, 'min': 0, 'max': 0, 'avg': 0, 'p50': 0, 'p95': 0, 'p99': 0}

        sorted_values = sorted(values)
        count = len(sorted_values)
        return {
            'count': count,
            'min': sorted_values[0],
            'max': sorted_values[-1],
            'avg': sum(sorted_values) / count,
            'p50': sorted_values[int(count * 0.50)],
            'p95': sorted_values[min(int(count * 0.95), count - 1)],
            'p99': sorted_values[min(int(count * 0.99), count - 1)],
        }

    # --- Timers ---

    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        self._timer_starts[name] = time.time()

    def stop_timer(
        self, name: str, labels: dict[str, str] | None = None
    ) -> float:
        """Stop a timer and record the duration."""
        start = self._timer_starts.pop(name, None)
        if start is None:
            return 0.0
        duration = time.time() - start
        self.record_duration(name, duration, labels)
        return duration

    def record_duration(
        self, name: str, duration_s: float, labels: dict[str, str] | None = None
    ) -> None:
        """Record a duration measurement."""
        key = self._make_key(name, labels)
        if key not in self._timers:
            self._timers[key] = []
        self._timers[key].append(duration_s)
        self._points.append(MetricPoint(
            name=name,
            metric_type=MetricType.TIMER,
            value=duration_s,
            labels=labels or {},
        ))

    def get_timer_stats(
        self, name: str, labels: dict[str, str] | None = None
    ) -> dict[str, float]:
        """Get timer statistics."""
        key = self._make_key(name, labels)
        values = self._timers.get(key, [])
        if not values:
            return {'count': 0, 'total': 0, 'avg': 0, 'min': 0, 'max': 0}

        return {
            'count': len(values),
            'total': sum(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
        }

    # --- Reporting ---

    def get_report(self) -> dict[str, Any]:
        """Get a comprehensive metrics report."""
        return {
            'counters': dict(self._counters),
            'gauges': dict(self._gauges),
            'histograms': {
                k: self._get_histogram_summary(v)
                for k, v in self._histograms.items()
            },
            'timers': {
                k: self._get_timer_summary(v)
                for k, v in self._timers.items()
            },
            'total_data_points': len(self._points),
        }

    def get_task_metrics(self, task_id: str) -> dict[str, Any]:
        """Get metrics for a specific task."""
        task_counters = {
            k: v for k, v in self._counters.items() if task_id in k
        }
        task_timers = {
            k: self._get_timer_summary(v)
            for k, v in self._timers.items()
            if task_id in k
        }
        return {
            'counters': task_counters,
            'timers': task_timers,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._timers.clear()
        self._points.clear()
        self._timer_starts.clear()

    # --- Internal ---

    def _make_key(self, name: str, labels: dict[str, str] | None = None) -> str:
        """Create a unique key from name and labels."""
        if not labels:
            return name
        label_str = ','.join(f'{k}={v}' for k, v in sorted(labels.items()))
        return f'{name}{{{label_str}}}'

    def _get_histogram_summary(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {'count': 0}
        return {
            'count': len(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
        }

    def _get_timer_summary(self, values: list[float]) -> dict[str, float]:
        if not values:
            return {'count': 0}
        return {
            'count': len(values),
            'total_s': sum(values),
            'avg_s': sum(values) / len(values),
            'min_s': min(values),
            'max_s': max(values),
        }
