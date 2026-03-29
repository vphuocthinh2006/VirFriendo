"""HTTP API for Godot / external clients: decide action + optional imitation-learning log."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.core.external_game_ai import Emotion, decide_action
from services.core.security import get_current_user_id

router = APIRouter(prefix="/game/external", tags=["External game AI"])


def _demo_log_path() -> Path:
    root = Path(__file__).resolve().parent.parent.parent.parent
    return root / "data" / "raw" / "external_game_demo.jsonl"


class ExternalDecideRequest(BaseModel):
    game_id: str = Field(..., min_length=1, max_length=128)
    state: dict[str, Any]
    actions: list[str] = Field(..., min_length=1)
    emotion: Emotion = "neutral"
    use_llm: bool = False


class ExternalDecideResponse(BaseModel):
    action: str
    source: Literal["rules", "llm", "fallback"]


@router.post("/decide", response_model=ExternalDecideResponse)
async def external_decide(
    body: ExternalDecideRequest,
    current_user_id: str = Depends(get_current_user_id),
) -> ExternalDecideResponse:
    _ = current_user_id
    action, source = await decide_action(
        body.game_id,
        body.state,
        body.actions,
        body.emotion,
        body.use_llm,
    )
    if not action and body.actions:
        action = body.actions[0]
        source = "fallback"
    return ExternalDecideResponse(action=action, source=source)


class DemoLogRequest(BaseModel):
    game_id: str = Field(..., min_length=1, max_length=128)
    state: dict[str, Any]
    action: str = Field(..., min_length=1)
    meta: dict[str, Any] | None = None


@router.post("/demo-log", status_code=204)
async def external_demo_log(
    body: DemoLogRequest,
    current_user_id: str = Depends(get_current_user_id),
) -> None:
    """Append one (state, action) row for future behavioral cloning — file under data/raw (gitignored)."""
    _ = current_user_id
    flag = (os.environ.get("EXTERNAL_GAME_DEMO_LOG", "1") or "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return
    path = _demo_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "game_id": body.game_id,
            "state": body.state,
            "action": body.action,
            "meta": body.meta or {},
        },
        ensure_ascii=False,
    )
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"demo log write failed: {e}") from e
