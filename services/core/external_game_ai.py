"""Rules + optional LLM helper for /game/external/decide."""
from __future__ import annotations

import random
from typing import Any, Literal

Emotion = Literal["neutral", "happy", "sad", "angry", "calm"]


async def decide_action(
    game_id: str,
    state: dict[str, Any],
    actions: list[str],
    emotion: Emotion,
    use_llm: bool,
) -> tuple[str, Literal["rules", "llm", "fallback"]]:
    if not actions:
        return "", "fallback"
    if use_llm:
        # Optional: wire LLM here; until then fall back to rules.
        pass
    # Simple rule: stochastic choice over allowed actions (stub policy).
    _ = (game_id, state, emotion)
    return random.choice(actions), "rules"
