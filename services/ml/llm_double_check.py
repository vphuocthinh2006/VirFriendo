"""Small JSON-only completion to arbitrate heuristic vs NLP emotion — Groq/OpenAI-compatible."""

from __future__ import annotations

import json
import os
import re

from groq import Groq
from loguru import logger

from services.core.config import settings
from services.ml.metrics import ModelType
from services.ml.metrics.collector import track_inference


@track_inference(model_name="groq-llm", model_type=ModelType.API)
async def arbitrator_pick_emotion(
    *,
    user_snippet: str,
    heuristic_emotion: str,
    nlp_emotion: str,
    nlp_p_top: float,
) -> tuple[str | None, str | None]:
    """
    Returns (final_avatar_emotion, raw_json_snippet_if_any).

    Avatar emotion vocabulary must match Claude mapping: neutral|happy|sad|surprised|crisis
    """
    key = (os.environ.get("GROQ_API_KEY") or settings.GROQ_API_KEY or "").strip()
    if not key:
        logger.debug("arbitrator: no GROQ_API_KEY — skip")
        return None, None

    model = (getattr(settings, "DOUBLE_CHECK_MODEL", "") or "llama-3.1-8b-instant").strip()
    max_tokens = int(getattr(settings, "DOUBLE_CHECK_MAX_TOKENS", 64))

    snippet = user_snippet[:400]
    system = (
        "You pick one token for avatar mood. Output ONLY compact JSON "
        "{\"final\":\"neutral|happy|sad|surprised|crisis|uncertain\"}."
        "Prefer agreement with NLP when softmax context suggests high confidence;"
        " use uncertain if ambiguous."
    )
    user = (
        f"user:\"{snippet}\"\n"
        f"heuristic_avatar_emotion:{heuristic_emotion}\n"
        f"nlp_emotion_label:{nlp_emotion}\n"
        f"nlp_prob_top:{nlp_p_top:.3f}"
    )

    def _sync_call() -> str:
        cli = Groq(api_key=key)
        r = cli.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return (r.choices[0].message.content or "").strip()

    import asyncio

    raw = await asyncio.to_thread(_sync_call)
    m = re.search(r"\{[^{}]+\}", raw)
    blob = m.group(0) if m else raw
    try:
        d = json.loads(blob)
        fin = str(d.get("final", "") or "").strip().lower()
        ok = {"neutral", "happy", "sad", "surprised", "crisis", "uncertain"}
        return (fin if fin in ok else None), raw[:500]
    except Exception as e:
        logger.warning("arbitrator parse failed: {} raw={}", e, raw[:200])
        return None, raw[:500]


def arbitration_to_avatar_emotion(parsed: str | None, fallback: str) -> str:
    if parsed is None:
        return fallback
    if parsed == "uncertain":
        return fallback
    return parsed
