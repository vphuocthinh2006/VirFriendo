"""
RLHF-lite: User feedback collection for reinforcement learning.

Stores thumbs up/down + optional text feedback per bot message.
Data saved to S3 as JSONL for future fine-tuning / reward model training.

Flow:
1. User clicks 👍/👎 on bot message → POST /chat/feedback
2. Feedback stored in DB (immediate) + buffered to S3 (batch)
3. Future: use feedback data to fine-tune LLM or train reward model
"""
from __future__ import annotations

import json
import os
import time
import threading
from datetime import datetime, timezone
from typing import Any

import boto3
from loguru import logger

_BUCKET = os.environ.get("S3_MEDIA_BUCKET", "virfriendo-media-ap-southeast-1")
_PREFIX = "ml-feedback/"
_REGION = os.environ.get("AWS_REGION", "ap-southeast-1")
_ENABLED = os.environ.get("ENABLE_ML_FEEDBACK_LOG", "true").strip().lower() in ("1", "true", "yes")

_buffer: list[str] = []
_buffer_lock = threading.Lock()
_FLUSH_SIZE = 20
_FLUSH_INTERVAL = 120  # seconds
_last_flush = time.time()


def log_feedback(
    *,
    user_id: str,
    message_id: str,
    conversation_id: str,
    bot_reply: str,
    user_message: str,
    rating: str,  # "up" or "down"
    feedback_text: str | None = None,
    detected_emotion: str | None = None,
    detected_intent: str | None = None,
    model_info: dict[str, Any] | None = None,
) -> None:
    """Log a single user feedback for RLHF training data."""
    if not _ENABLED:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "message_id": message_id,
        "conversation_id": conversation_id,
        "rating": rating,
        "feedback_text": feedback_text,
        "bot_reply": bot_reply[:2000],
        "user_message": user_message[:500],
        "detected_emotion": detected_emotion,
        "detected_intent": detected_intent,
        "model_info": model_info,
    }

    _append_record(json.dumps(record, ensure_ascii=False))
    logger.info("Feedback logged: msg={} rating={}", message_id[:8], rating)


def _append_record(line: str) -> None:
    global _last_flush
    with _buffer_lock:
        _buffer.append(line)
        now = time.time()
        if len(_buffer) >= _FLUSH_SIZE or (now - _last_flush) >= _FLUSH_INTERVAL:
            _flush_buffer()
            _last_flush = now


def _flush_buffer() -> None:
    if not _buffer:
        return
    lines = _buffer.copy()
    _buffer.clear()

    now = datetime.now(timezone.utc)
    key = f"{_PREFIX}{now.strftime('%Y/%m/%d')}/{now.strftime('%H-%M-%S')}-{len(lines)}.jsonl"
    body = "\n".join(lines) + "\n"

    try:
        s3 = boto3.client("s3", region_name=_REGION)
        s3.put_object(Bucket=_BUCKET, Key=key, Body=body.encode("utf-8"))
        logger.debug("Flushed {} feedback records to s3://{}/{}", len(lines), _BUCKET, key)
    except Exception as e:
        logger.warning("Failed to flush feedback to S3: {}", e)
        with _buffer_lock:
            _buffer.extend(lines)
