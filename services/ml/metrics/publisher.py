"""CloudWatch publisher for ML inference metrics.

Handles batching and pushing metrics to AWS CloudWatch under the
Pally/MLInference namespace via a background daemon thread.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import boto3
from loguru import logger

if TYPE_CHECKING:
    from services.ml.metrics import MetricDataPoint

NAMESPACE = "Pally/MLInference"
MAX_BUFFER_SIZE = 150
FLUSH_THRESHOLD = 20
FLUSH_INTERVAL_SECONDS = 60


class CloudWatchPublisher:
    """Background publisher that batches PutMetricData calls."""

    def __init__(self, region: str = "ap-southeast-1") -> None:
        self._client = boto3.client("cloudwatch", region_name=region)
        self._buffer: deque[MetricDataPoint] = deque(maxlen=MAX_BUFFER_SIZE)
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._start_timer()

    def enqueue(self, points: list[MetricDataPoint]) -> None:
        """Add points to buffer; flush if threshold reached."""
        with self._lock:
            for p in points:
                self._buffer.append(p)
            if len(self._buffer) >= FLUSH_THRESHOLD:
                self._flush_locked()

    def _start_timer(self) -> None:
        """Schedule periodic flush every 60 seconds."""
        self._timer = threading.Timer(FLUSH_INTERVAL_SECONDS, self._periodic_flush)
        self._timer.daemon = True
        self._timer.start()

    def _periodic_flush(self) -> None:
        """Timer callback: flush under lock, then reschedule."""
        with self._lock:
            self._flush_locked()
        self._start_timer()

    def _flush_locked(self) -> None:
        """Convert buffer to MetricData and call PutMetricData.

        Must be called while holding self._lock.
        """
        if not self._buffer:
            return

        metric_data: list[dict] = []
        points = list(self._buffer)

        for p in points:
            metric_data.append({
                "MetricName": "InferenceLatencyMs",
                "Dimensions": [
                    {"Name": "ModelName", "Value": p.model_name},
                    {"Name": "ModelType", "Value": p.model_type.value},
                    {"Name": "Status", "Value": p.status.value},
                ],
                "Value": p.latency_ms,
                "Unit": "Milliseconds",
                "Timestamp": datetime.fromtimestamp(p.timestamp, tz=timezone.utc),
            })
            metric_data.append({
                "MetricName": "InferenceCount",
                "Dimensions": [
                    {"Name": "ModelName", "Value": p.model_name},
                    {"Name": "ModelType", "Value": p.model_type.value},
                    {"Name": "Status", "Value": p.status.value},
                ],
                "Value": 1,
                "Unit": "Count",
                "Timestamp": datetime.fromtimestamp(p.timestamp, tz=timezone.utc),
            })

        try:
            # PutMetricData accepts max 1000 items per call
            for i in range(0, len(metric_data), 1000):
                self._client.put_metric_data(
                    Namespace=NAMESPACE,
                    MetricData=metric_data[i : i + 1000],
                )
            self._buffer.clear()
        except Exception as e:
            logger.warning(
                "CloudWatch PutMetricData failed: {} — retaining {} points",
                e,
                len(self._buffer),
            )
            # Points remain in buffer for next attempt
