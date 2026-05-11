"""Log ML predictions to S3 for SageMaker Model Monitor.

Captures NLP emotion/dialogue_act predictions and ViT gallery matches
in JSONL format compatible with SageMaker Data Quality monitoring.
"""
from __future__ import annotations

import json
import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from loguru import logger

_BUCKET = os.environ.get("S3_MEDIA_BUCKET", "virfriendo-media-ap-southeast-1")
_PREFIX = "ml-predictions/"
_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
_ENABLED = os.environ.get("ENABLE_ML_PREDICTION_LOG", "true").strip().lower() in ("1", "true", "yes")

_buffer: list[str] = []
_buffer_lock = threading.Lock()
_FLUSH_INTERVAL = 60  # seconds
_FLUSH_SIZE = 1  # flush every single record for reliability
_last_flush = time.time()


def _s3_client():
    return boto3.client("s3", region_name=_REGION)


def log_nlp_prediction(
    *,
    user_text: str,
    emotion_label: str,
    dialogue_act_label: str,
    emotion_prob_top1: float,
    emotion_margin: float,
    act_prob_top1: float,
    act_margin: float,
    final_avatar_emotion: str,
    arbitrator_used: bool = False,
    arbitrator_pick: str | None = None,
) -> None:
    """Log a single NLP prediction for monitoring."""
    if not _ENABLED:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "nlp_multitask_bert",
        "input_length": len(user_text),
        "predictions": {
            "emotion_label": emotion_label,
            "dialogue_act_label": dialogue_act_label,
            "emotion_confidence": round(emotion_prob_top1, 4),
            "emotion_margin": round(emotion_margin, 4),
            "act_confidence": round(act_prob_top1, 4),
            "act_margin": round(act_margin, 4),
        },
        "final_decision": {
            "avatar_emotion": final_avatar_emotion,
            "arbitrator_used": arbitrator_used,
            "arbitrator_pick": arbitrator_pick,
        },
    }

    _append_record(json.dumps(record, ensure_ascii=False))


def log_vit_prediction(
    *,
    top_character: str | None,
    top_similarity: float,
    tier: str | None,
    num_matches: int,
) -> None:
    """Log a ViT gallery prediction for monitoring."""
    if not _ENABLED:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "vit_gallery",
        "predictions": {
            "top_character": top_character,
            "top_similarity": round(top_similarity, 4),
            "tier": tier,
            "num_matches": num_matches,
        },
    }

    _append_record(json.dumps(record, ensure_ascii=False))


def _append_record(line: str) -> None:
    global _last_flush
    with _buffer_lock:
        _buffer.append(line)
        now = time.time()
        # Flush immediately if buffer has any records and 30s passed, or buffer full
        if len(_buffer) >= _FLUSH_SIZE or (now - _last_flush) >= 30:
            _flush_buffer()
            _last_flush = now


def _flush_buffer() -> None:
    """Flush buffer to S3 as JSONL file."""
    if not _buffer:
        return

    lines = _buffer.copy()
    _buffer.clear()

    # S3 key: ml-predictions/YYYY/MM/DD/HH-MM-SS-{count}.jsonl
    now = datetime.now(timezone.utc)
    key = (
        f"{_PREFIX}{now.strftime('%Y/%m/%d')}/"
        f"{now.strftime('%H-%M-%S')}-{len(lines)}.jsonl"
    )

    body = "\n".join(lines) + "\n"

    try:
        s3 = _s3_client()
        s3.put_object(Bucket=_BUCKET, Key=key, Body=body.encode("utf-8"))
        logger.info("Flushed {} prediction records to s3://{}/{}", len(lines), _BUCKET, key)
    except Exception as e:
        logger.error("Failed to flush predictions to S3: {} — bucket={} key={}", e, _BUCKET, key)
        # Put records back
        with _buffer_lock:
            _buffer.extend(lines)


def flush_on_shutdown() -> None:
    """Call at app shutdown to flush remaining records."""
    with _buffer_lock:
        _flush_buffer()
