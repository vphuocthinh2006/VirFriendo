# Rule-based + LLM fallback for turn-based game actions (Ancient RTS wire format).
from __future__ import annotations

import json
import re
from typing import Any, Literal

from loguru import logger

from services.agent_service.llm.client import generate

Emotion = Literal["aggressive", "cautious", "neutral"]


def _dist(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _enemy_base_center(state: dict[str, Any]) -> tuple[int, int] | None:
    for e in state.get("entities") or []:
        if e.get("kind") == "base" and e.get("owner") == 0:
            x, y, w, h = int(e["x"]), int(e["y"]), int(e["w"]), int(e["h"])
            return (x + w // 2, y + h // 2)
    return None


def _nearest_enemy_unit_pos(state: dict[str, Any]) -> tuple[int, int] | None:
    best = None
    best_d = 10**9
    eb = _enemy_base_center(state)
    for e in state.get("entities") or []:
        if e.get("kind") != "unit" or e.get("owner") != 0:
            continue
        p = (int(e["x"]), int(e["y"]))
        if eb:
            d = _dist(p, eb)
            if d < best_d:
                best_d = d
                best = p
    return best


def choose_action_rules(
    state: dict[str, Any],
    actions: list[str],
    emotion: Emotion = "neutral",
) -> str:
    """Emotion-aware heuristic. Designed so emotion can later be injected from NLP."""
    if not actions:
        return ""
    if len(actions) == 1:
        return actions[0]

    def rank_train() -> list[str]:
        trains = [a for a in actions if a.startswith("train:")]
        if not trains:
            return []
        if emotion == "aggressive":
            order = ["train:spearman", "train:villager"]
        elif emotion == "cautious":
            order = ["train:villager", "train:spearman"]
        else:
            order = ["train:villager", "train:spearman", "train:spearman"]
        out = []
        for o in order:
            if o in trains:
                out.append(o)
        for t in trains:
            if t not in out:
                out.append(t)
        return out

    # Train phase
    if any(a.startswith("train:") for a in actions):
        ranked = rank_train()
        if ranked:
            return ranked[0]
        if "skip_train" in actions:
            return "skip_train"

    moves = [a for a in actions if a.startswith("move:")]
    if not moves:
        for a in actions:
            if a in ("skip_train", "ai_turn_complete"):
                return a
        return actions[0]

    target = _nearest_enemy_unit_pos(state)
    base_c = _enemy_base_center(state)
    if emotion == "aggressive":
        goal = target or base_c
    elif emotion == "cautious":
        goal = base_c
    else:
        goal = target or base_c

    if goal is None:
        return moves[0]

    def move_goal(m: str) -> tuple[int, int] | None:
        # move:<id>:<gx>,<gy>
        try:
            _, rest = m.split(":", 1)
            _, coords = rest.rsplit(":", 1)
            gx, gy = coords.split(",")
            return int(gx), int(gy)
        except Exception:
            return None

    best_m = moves[0]
    best_d = 10**9
    for m in moves:
        g = move_goal(m)
        if g is None:
            continue
        d = _dist(g, goal)
        if emotion == "cautious" and target and base_c:
            d += int(0.25 * _dist(g, target))
        if d < best_d:
            best_d = d
            best_m = m
    return best_m


def _parse_llm_action(text: str) -> str | None:
    if not text:
        return None
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "action" in obj:
            return str(obj["action"]).strip()
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{\s*"action"\s*:\s*"([^"]+)"\s*\}', text)
    if m:
        return m.group(1).strip()
    return None


async def choose_action_llm(
    state: dict[str, Any],
    actions: list[str],
    emotion: Emotion = "neutral",
) -> str | None:
    """Ask LLM for strictly JSON { \"action\": \"...\" }; return None on failure."""
    if not actions:
        return None
    system = (
        "You are a game policy head for a small turn-based RTS. "
        "Reply with ONLY a single JSON object, no markdown, no extra keys: "
        '{"action":"<one of the allowed actions>"} '
        "Pick a legal action that fits the emotion style."
    )
    user = json.dumps(
        {
            "emotion": emotion,
            "allowed_actions": actions,
            "state": state,
        },
        ensure_ascii=False,
    )
    try:
        out = await generate(system, user)
    except Exception as e:
        logger.warning("LLM turn game decide failed: {}", e)
        return None
    if not out:
        return None
    act = _parse_llm_action(out)
    if act and act in actions:
        return act
    logger.warning("LLM returned invalid action, got: {}", out[:200])
    return None


async def decide_action(
    state: dict[str, Any],
    actions: list[str],
    emotion: Emotion = "neutral",
    *,
    use_llm: bool = False,
) -> tuple[str, Literal["rules", "llm", "fallback"]]:
    """
    Returns (action, source). Always returns a valid action if actions non-empty
    (rules fallback when LLM fails or returns invalid).
    """
    if not actions:
        return "", "fallback"
    if use_llm:
        llm_a = await choose_action_llm(state, actions, emotion)
        if llm_a:
            return llm_a, "llm"
    rules_a = choose_action_rules(state, actions, emotion)
    if rules_a and rules_a in actions:
        return rules_a, "rules" if not use_llm else "fallback"
    return actions[0], "fallback"
