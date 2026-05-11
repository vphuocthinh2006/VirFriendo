"""Data models for ML inference metrics."""

from dataclasses import dataclass
from enum import Enum


class ModelType(str, Enum):
    """Classification of inference model deployment type."""

    LOCAL = "local"
    API = "api"


class InferenceStatus(str, Enum):
    """Outcome status of an inference call."""

    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True)
class MetricDataPoint:
    """Single inference measurement.

    Attributes:
        model_name: Identifier for the model (e.g. "bert-intent-emotion").
        model_type: Whether the model runs locally or via API.
        status: Whether the inference succeeded or errored.
        latency_ms: Wall-clock duration in milliseconds.
        timestamp: Unix epoch (seconds) when measurement was taken.
    """

    model_name: str
    model_type: ModelType
    status: InferenceStatus
    latency_ms: float
    timestamp: float
