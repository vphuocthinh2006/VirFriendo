"""
Generic external game AI (Godot / web / any client): pick one action from a list.

- Rules + optional emotion bias (aggressive / cautious / neutral)
- Optional LLM (strict JSON) with rule fallback
"""
from __future__ import annotations

import json
import random
import re
from typing import Any, Literal

from loguru import logger

from services.agent_service.llm.client import generate

Emotion = Literal["aggressive", "cautious", "neutral"]
Source = Literal["rules", "llm", "fallback"]

_AGGR_PAT = re.compile(
    r"(attack|hit|strike|slash|fire|cast_offensive|skill_damage|melee|charge)", re.I
)
_CAUT_PAT = re.compile(
    r"(defend|block|dodge|heal|retreat|flee|buff_def|guard|wait|skip)", re.I
)


def _score_action(a: str, emotion: Emotion) -> float:
    s = 0.0
    if emotion == "aggressive":
        if _AGGR_PAT.search(a):
            s += 3.0
        if _CAUT_PAT.search(a):
            s -= 1.5
    elif emotion == "cautious":
        if _CAUT_PAT.search(a):
            s += 3.0
        if _AGGR_PAT.search(a):
            s -= 0.8
    else:
        s += random.random() * 0.01
    return s


def choose_action_rules(actions: list[str], emotion: Emotion = "neutral") -> str | None:
    if not actions:
        return None
    best = actions[0]
    best_s = _score_action(best, emotion)
    for a in actions[1:]:
        sc = _score_action(a, emotion)
        if sc > best_s:
            best_s = sc
            best = a
    return best


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                return None
    return None


async def choose_action_llm(
    game_id: str,
    state: dict[str, Any],
    actions: list[str],
    emotion: Emotion,
) -> str | None:
    if not actions:
        return None
    system = (
        "You choose exactly one action for a game bot. Reply with ONLY valid JSON, no markdown: "
        '{"action":"<string>"} where <string> is copied exactly from the allowed list.'
    )
    user = json.dumps(
        {
            "game_id": game_id,
            "emotion": emotion,
            "allowed_actions": actions,
            "state": state,
        },
        ensure_ascii=False,
    )
    raw = await generate(system, user)
    if not raw:
        return None
    obj = _extract_json_object(raw)
    if not obj:
        logger.warning("external_game_ai: LLM did not return JSON object")
        return None
    action = obj.get("action")
    if not isinstance(action, str):
        return None
    action = action.strip()
    if action in actions:
        return action
    for a in actions:
        if a.lower() == action.lower():
            return a
    logger.warning("external_game_ai: LLM action not in list: {}", action)
    return None


async def decide_action(
    game_id: str,
    state: dict[str, Any],
    actions: list[str],
    emotion: Emotion = "neutral",
    use_llm: bool = False,
) -> tuple[str, Source]:
    """Returns (action, source). Never raises — falls back to first action."""
    clean = [a for a in actions if isinstance(a, str) and a.strip()]
    if not clean:
        return ("", "fallback")

    if use_llm:
        picked = await choose_action_llm(game_id, state, clean, emotion)
        if picked:
            return (picked, "llm")

    rules = choose_action_rules(clean, emotion)
    if rules:
        return (rules, "rules")

    return (clean[0], "fallback")
