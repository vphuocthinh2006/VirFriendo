"""Log ML predictions to S3 for SageMaker Model Monitor.

Captures NLP emotion/dialogue_act predictions and ViT gallery matches
in JSONL format compatible with SageMaker Data Quality monitoring.

Enhanced: per-conversation analytics with dialogue_act %, emotion %,
intent_model accuracy, and reasoning why BERT intent_model is chosen over Groq.
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
_ANALYTICS_PREFIX = "ml-analytics/"
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
    conversation_id: str | None = None,
    message_id: str | None = None,
    intent_label: str | None = None,
    intent_source: str | None = None,
    intent_model_confidence: float | None = None,
    groq_intent_label: str | None = None,
    groq_latency_ms: float | None = None,
    bert_latency_ms: float | None = None,
    fusion_meta: dict[str, Any] | None = None,
) -> None:
    """Log a single NLP prediction for monitoring with full conversation context."""
    if not _ENABLED:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "nlp_multitask_bert",
        "conversation_id": conversation_id,
        "message_id": message_id,
        "input_length": len(user_text),
        "input_preview": user_text[:80],
        "predictions": {
            "emotion": {
                "label": emotion_label,
                "confidence_pct": round(emotion_prob_top1 * 100, 2),
                "margin": round(emotion_margin, 4),
                "final_avatar_emotion": final_avatar_emotion,
            },
            "dialogue_act": {
                "label": dialogue_act_label,
                "confidence_pct": round(act_prob_top1 * 100, 2),
                "margin": round(act_margin, 4),
            },
            "intent": {
                "label": intent_label,
                "source": intent_source,
                "model_confidence": round(intent_model_confidence * 100, 2) if intent_model_confidence else None,
            },
        },
        "model_comparison": {
            "intent_model_vs_groq": {
                "intent_model_label": intent_label,
                "groq_label": groq_intent_label,
                "chosen": intent_source or "keyword_fallback",
                "reasoning": _build_intent_reasoning(
                    intent_source=intent_source,
                    bert_latency_ms=bert_latency_ms,
                    groq_latency_ms=groq_latency_ms,
                    intent_model_confidence=intent_model_confidence,
                ),
            },
            "latency": {
                "bert_inference_ms": round(bert_latency_ms, 2) if bert_latency_ms else None,
                "groq_inference_ms": round(groq_latency_ms, 2) if groq_latency_ms else None,
            },
        },
        "arbitrator": {
            "used": arbitrator_used,
            "pick": arbitrator_pick,
        },
        "fusion": fusion_meta,
    }

    _append_record(json.dumps(record, ensure_ascii=False))


def _build_intent_reasoning(
    *,
    intent_source: str | None,
    bert_latency_ms: float | None,
    groq_latency_ms: float | None,
    intent_model_confidence: float | None,
) -> str:
    """Build human-readable reasoning for why intent_model was chosen over Groq."""
    reasons: list[str] = []

    if intent_source == "bert_model":
        reasons.append("BERT intent_model selected over Groq")
        if bert_latency_ms is not None and groq_latency_ms is not None:
            if bert_latency_ms < groq_latency_ms:
                reasons.append(
                    f"Latency: BERT {bert_latency_ms:.1f}ms vs Groq {groq_latency_ms:.1f}ms "
                    f"(BERT {groq_latency_ms/bert_latency_ms:.1f}x faster)"
                )
            else:
                reasons.append(
                    f"Latency: BERT {bert_latency_ms:.1f}ms vs Groq {groq_latency_ms:.1f}ms"
                )
        elif bert_latency_ms is not None:
            reasons.append(f"BERT local inference: {bert_latency_ms:.1f}ms (no network round-trip)")
        reasons.append("Zero API cost — runs on ECS task CPU, no token billing")
        reasons.append("Deterministic output — same input always produces same label")
        reasons.append("No rate-limit or quota risk compared to Groq API")
        if intent_model_confidence and intent_model_confidence > 0.7:
            reasons.append(f"High confidence: {intent_model_confidence*100:.1f}%")
    elif intent_source == "keyword_fallback":
        reasons.append("Keyword fallback used (BERT model not loaded or ENABLE_INTENT_MODEL_RUNTIME=false)")
        reasons.append("Groq LLM hybrid disabled — too unreliable for production intent classification")
        reasons.append("Keyword rules provide instant, deterministic classification with zero cost")
    elif intent_source == "groq_llm":
        reasons.append("Groq LLM used for intent (fallback when BERT unavailable)")
        if groq_latency_ms:
            reasons.append(f"Groq latency: {groq_latency_ms:.1f}ms (network + inference)")
        reasons.append("Consumes API tokens — has rate-limit and cost implications")

    if not reasons:
        reasons.append("Intent source not specified")

    return " | ".join(reasons)


def log_conversation_analytics(
    *,
    conversation_id: str,
    user_id: str | None = None,
    total_messages: int,
    emotion_distribution: dict[str, int],
    dialogue_act_distribution: dict[str, int],
    intent_distribution: dict[str, int],
    avg_emotion_confidence: float,
    avg_act_confidence: float,
    intent_model_properties: dict[str, Any] | None = None,
) -> None:
    """Log aggregated per-conversation analytics to S3.

    Format: structured JSONL with readable summary sections.
    Path: ml-analytics/{conversation_id}/{timestamp}.jsonl
    """
    if not _ENABLED:
        return

    total = max(total_messages, 1)

    # Build percentage distributions
    emotion_pcts = {k: round(v / total * 100, 1) for k, v in sorted(emotion_distribution.items(), key=lambda x: -x[1])}
    act_pcts = {k: round(v / total * 100, 1) for k, v in sorted(dialogue_act_distribution.items(), key=lambda x: -x[1])}
    intent_pcts = {k: round(v / total * 100, 1) for k, v in sorted(intent_distribution.items(), key=lambda x: -x[1])}

    record = {
        "type": "conversation_analytics",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "summary": {
            "total_messages_analyzed": total_messages,
            "avg_emotion_confidence_pct": round(avg_emotion_confidence * 100, 2),
            "avg_dialogue_act_confidence_pct": round(avg_act_confidence * 100, 2),
        },
        "emotion_analysis": {
            "distribution_pct": emotion_pcts,
            "distribution_count": dict(sorted(emotion_distribution.items(), key=lambda x: -x[1])),
            "dominant_emotion": max(emotion_distribution, key=emotion_distribution.get) if emotion_distribution else "unknown",
        },
        "dialogue_act_analysis": {
            "distribution_pct": act_pcts,
            "distribution_count": dict(sorted(dialogue_act_distribution.items(), key=lambda x: -x[1])),
            "dominant_act": max(dialogue_act_distribution, key=dialogue_act_distribution.get) if dialogue_act_distribution else "unknown",
        },
        "intent_analysis": {
            "distribution_pct": intent_pcts,
            "distribution_count": dict(sorted(intent_distribution.items(), key=lambda x: -x[1])),
            "dominant_intent": max(intent_distribution, key=intent_distribution.get) if intent_distribution else "unknown",
        },
        "intent_model_properties": intent_model_properties or {
            "model_name": "bert-base-uncased (multitask fine-tuned)",
            "model_file": "intent_emotion_model.pth",
            "architecture": "BERT + dual classification heads (emotion + dialogue_act)",
            "advantages_over_groq": [
                "Zero API cost — inference runs locally on ECS CPU",
                "Deterministic — same input always same output (no temperature/sampling)",
                "No rate-limit / quota exhaustion risk",
                "Low latency (~15-50ms) vs Groq API (~200-800ms)",
                "No network dependency — works even if external APIs are down",
                "Privacy — user text never leaves the container for classification",
                "Consistent accuracy on trained domain (emotion + dialogue act)",
            ],
            "limitations": [
                "Fixed label set — cannot classify new intents without retraining",
                "Requires model file in container (~438MB intent_emotion_model.pth)",
                "CPU-only inference on Fargate (no GPU acceleration)",
                "Domain-specific — trained on VirFriendo conversation data only",
            ],
            "groq_comparison": {
                "groq_pros": [
                    "Flexible — can classify arbitrary intents with prompt engineering",
                    "No local model file needed",
                    "Can explain reasoning (chain-of-thought)",
                ],
                "groq_cons": [
                    "~$0.05-0.10 per 1K classifications (token cost)",
                    "200-800ms latency per call (network round-trip)",
                    "Non-deterministic — same input can produce different labels",
                    "Rate-limited — can fail under high load",
                    "Unreliable for production intent classification (observed in testing)",
                ],
                "decision": "BERT intent_model chosen for production: cost=0, latency<50ms, deterministic, no external dependency",
            },
        },
    }

    body = json.dumps(record, ensure_ascii=False, indent=2)
    now = datetime.now(timezone.utc)
    key = (
        f"{_ANALYTICS_PREFIX}{conversation_id}/"
        f"{now.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    )

    try:
        s3 = _s3_client()
        s3.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Flushed conversation analytics to s3://{}/{}", _BUCKET, key)
    except Exception as e:
        logger.error("Failed to flush conversation analytics to S3: {} — key={}", e, key)


def log_vit_prediction(
    *,
    top_character: str | None,
    top_similarity: float,
    tier: str | None,
    num_matches: int,
    conversation_id: str | None = None,
) -> None:
    """Log a ViT gallery prediction for monitoring."""
    if not _ENABLED:
        return

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": "vit_gallery",
        "conversation_id": conversation_id,
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
