"""MetricsCollector singleton and track_inference decorator.

Provides the central collection point for ML inference timing data
and a decorator factory for instrumenting inference functions.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Callable, TypeVar

from services.ml.metrics import InferenceStatus, MetricDataPoint, ModelType

F = TypeVar("F", bound=Callable)


class MetricsCollector:
    """Singleton that buffers metric data points and forwards to publisher."""

    _instance: MetricsCollector | None = None

    _FLUSH_THRESHOLD = 20

    def __init__(self) -> None:
        self._enabled: bool = False
        self._buffer: list[MetricDataPoint] = []
        self._publisher: "CloudWatchPublisher | None" = None  # noqa: F821

    @classmethod
    def instance(cls) -> MetricsCollector:
        """Return the singleton instance, creating it on first access."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._init_from_env()
        return cls._instance

    def _init_from_env(self) -> None:
        """Read ENABLE_ML_METRICS from os.environ and configure publisher.

        Truthy values: "1", "true", "yes" (case-insensitive)
        Falsy values: "", "0", "false", "no", unset (defaults to False)
        """
        import os

        raw = os.environ.get("ENABLE_ML_METRICS", "").strip().lower()
        self._enabled = raw in ("1", "true", "yes")

        if self._enabled:
            from services.ml.metrics.publisher import CloudWatchPublisher

            region = os.environ.get("AWS_REGION", "ap-southeast-1")
            self._publisher = CloudWatchPublisher(region=region)

    def is_enabled(self) -> bool:
        """Return whether metrics collection is active."""
        return self._enabled

    def record(self, data_point: MetricDataPoint) -> None:
        """Append to buffer; trigger flush when buffer >= threshold."""
        self._buffer.append(data_point)
        if len(self._buffer) >= self._FLUSH_THRESHOLD:
            self.flush()

    def flush(self) -> None:
        """Send buffered points to the publisher and clear the buffer."""
        if not self._buffer or self._publisher is None:
            return
        points = list(self._buffer)
        self._buffer.clear()
        self._publisher.enqueue(points)


def track_inference(
    model_name: str,
    model_type: ModelType,
) -> Callable:
    """Decorator factory that times a function and records a MetricDataPoint.

    Short-circuits with zero overhead when metrics are disabled.
    Supports both sync and async functions.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not MetricsCollector.instance().is_enabled():
                return func(*args, **kwargs)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                MetricsCollector.instance().record(
                    MetricDataPoint(
                        model_name=model_name,
                        model_type=model_type,
                        status=InferenceStatus.SUCCESS,
                        latency_ms=elapsed,
                        timestamp=time.time(),
                    )
                )
                return result
            except Exception:
                elapsed = (time.perf_counter() - start) * 1000
                MetricsCollector.instance().record(
                    MetricDataPoint(
                        model_name=model_name,
                        model_type=model_type,
                        status=InferenceStatus.ERROR,
                        latency_ms=elapsed,
                        timestamp=time.time(),
                    )
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not MetricsCollector.instance().is_enabled():
                return await func(*args, **kwargs)
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                MetricsCollector.instance().record(
                    MetricDataPoint(
                        model_name=model_name,
                        model_type=model_type,
                        status=InferenceStatus.SUCCESS,
                        latency_ms=elapsed,
                        timestamp=time.time(),
                    )
                )
                return result
            except Exception:
                elapsed = (time.perf_counter() - start) * 1000
                MetricsCollector.instance().record(
                    MetricDataPoint(
                        model_name=model_name,
                        model_type=model_type,
                        status=InferenceStatus.ERROR,
                        latency_ms=elapsed,
                        timestamp=time.time(),
                    )
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator
