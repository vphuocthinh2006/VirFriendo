"""Emotion Fusion: Combine BERT (user text) + Groq LLM (bot reply) for smarter Live2D emotions.

Pipeline:
1. BERT detects emotion from user message (fast, local)
2. Groq detects emotion from bot reply (understands context better)
3. Fusion: weighted combination → final avatar emotion

This replaces the old single-signal approach where only user text was analyzed.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from groq import Groq
from loguru import logger

from services.core.config import settings
from services.ml.metrics.models import ModelType
from services.ml.metrics.collector import track_inference

# Valid Live2D emotions
VALID_EMOTIONS = {"happy", "sad", "angry", "surprised", "sleepy", "blush", "neutral", "idle"}

# Emotion priority weights: Groq (bot context) > BERT (user text) > heuristic
WEIGHT_GROQ_BOT = 0.6
WEIGHT_BERT_USER = 0.3
WEIGHT_HEURISTIC = 0.1


@track_inference(model_name="groq-emotion-fusion", model_type=ModelType.API)
async def detect_bot_reply_emotion(bot_reply: str, user_message: str) -> str | None:
    """Use Groq to detect the dominant emotion in the bot's reply given user context.

    Returns one of: happy, sad, angry, surprised, sleepy, blush, neutral
    """
    key = (os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "") or "").strip()
    if not key:
        return None

    model = "llama-3.1-8b-instant"  # Fast, cheap, good enough for emotion classification

    system = (
        "You are an emotion classifier for a chat companion's avatar expressions. "
        "Given the user's message and the bot's reply, determine what emotion the BOT is expressing. "
        "Output ONLY one word from: happy, sad, angry, surprised, sleepy, blush, neutral\n"
        "Rules:\n"
        "- Focus on the BOT's tone and emotion, not the user's\n"
        "- 'blush' = shy, embarrassed, flirty\n"
        "- 'surprised' = amazed, curious, shocked\n"
        "- 'happy' = cheerful, excited, amused, grateful\n"
        "- 'sad' = empathetic, concerned, disappointed\n"
        "- 'angry' = frustrated, annoyed (rare for a companion)\n"
        "- 'neutral' = calm, informative, no strong emotion\n"
        "Output ONLY the emotion word, nothing else."
    )

    user_prompt = f"User: {user_message[:200]}\nBot reply: {bot_reply[:400]}\n\nBot emotion:"

    def _sync_call() -> str:
        cli = Groq(api_key=key)
        r = cli.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        return (r.choices[0].message.content or "").strip().lower()

    try:
        raw = await asyncio.to_thread(_sync_call)
        # Parse — should be a single word
        emotion = raw.split()[0] if raw else "neutral"
        emotion = re.sub(r"[^a-z]", "", emotion)
        if emotion in VALID_EMOTIONS:
            return emotion
        # Fuzzy match
        for valid in VALID_EMOTIONS:
            if valid in emotion or emotion in valid:
                return valid
        return "neutral"
    except Exception as e:
        logger.warning("Groq emotion detection failed: {}", e)
        return None


def fuse_emotions(
    *,
    bert_emotion: str | None,
    groq_bot_emotion: str | None,
    heuristic_emotion: str | None,
) -> tuple[str, dict[str, Any]]:
    """Fuse multiple emotion signals into final avatar emotion.

    Priority: groq_bot (0.6) > bert_user (0.3) > heuristic (0.1)
    If signals agree → high confidence.
    If disagree → weighted vote.

    Returns (final_emotion, debug_meta).
    """
    meta: dict[str, Any] = {
        "bert_emotion": bert_emotion,
        "groq_bot_emotion": groq_bot_emotion,
        "heuristic_emotion": heuristic_emotion,
        "fusion_method": "weighted_vote",
    }

    # Normalize None → neutral
    bert = (bert_emotion or "neutral").lower()
    groq = (groq_bot_emotion or "neutral").lower()
    heur = (heuristic_emotion or "neutral").lower()

    # Map to valid set
    def _normalize(e: str) -> str:
        if e in VALID_EMOTIONS:
            return e
        if "happy" in e or "joy" in e or "excit" in e:
            return "happy"
        if "sad" in e or "down" in e:
            return "sad"
        if "angry" in e or "frustrat" in e:
            return "angry"
        if "surpris" in e or "shock" in e or "curious" in e:
            return "surprised"
        if "blush" in e or "shy" in e or "embarrass" in e:
            return "blush"
        if "sleep" in e or "tired" in e or "bored" in e:
            return "sleepy"
        return "neutral"

    bert = _normalize(bert)
    groq = _normalize(groq)
    heur = _normalize(heur)

    # If all agree → instant decision
    if bert == groq == heur:
        meta["fusion_method"] = "unanimous"
        meta["confidence"] = "high"
        logger.info("[EMOTION FUSION] unanimous={}", bert)
        return bert, meta

    # If groq and bert agree → strong signal
    if groq == bert and groq != "neutral":
        meta["fusion_method"] = "groq_bert_agree"
        meta["confidence"] = "high"
        logger.info("[EMOTION FUSION] groq+bert agree={}", groq)
        return groq, meta

    # Weighted vote
    scores: dict[str, float] = {}
    for emotion, weight in [(groq, WEIGHT_GROQ_BOT), (bert, WEIGHT_BERT_USER), (heur, WEIGHT_HEURISTIC)]:
        scores[emotion] = scores.get(emotion, 0) + weight

    # Pick highest score, but prefer non-neutral
    best = max(scores, key=lambda e: (scores[e], e != "neutral"))

    # If best is neutral but there's a non-neutral with decent score, prefer it
    if best == "neutral":
        non_neutral = {e: s for e, s in scores.items() if e != "neutral"}
        if non_neutral:
            alt = max(non_neutral, key=non_neutral.get)  # type: ignore
            if non_neutral[alt] >= 0.3:
                best = alt
                meta["fusion_method"] = "prefer_non_neutral"

    meta["scores"] = scores
    meta["final"] = best
    meta["confidence"] = "high" if scores.get(best, 0) >= 0.6 else "medium"
    logger.info("[EMOTION FUSION] final={} scores={} method={}", best, scores, meta["fusion_method"])
    return best, meta
