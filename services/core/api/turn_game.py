"""Turn-based game AI: JSON state in, single action out (for Ancient RTS + future games)."""

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.core.turn_game_ai import decide_action

router = APIRouter(prefix="/game", tags=["Turn game AI"])


class TurnDecideRequest(BaseModel):
    game_id: str = Field(default="ancient_rts", description="Client game identifier")
    state: dict[str, Any]
    actions: list[str] = Field(min_length=0)
    emotion: Literal["aggressive", "cautious", "neutral"] = "neutral"
    use_llm: bool = False


class TurnDecideResponse(BaseModel):
    action: str
    source: Literal["rules", "llm", "fallback"]


@router.post("/turn/decide", response_model=TurnDecideResponse)
async def turn_decide(body: TurnDecideRequest) -> TurnDecideResponse:
    """
    Given opaque JSON state + allowed action strings, return one action.
    Emotion steers rule-based policy; optional LLM with strict JSON fallback.
    """
    action, source = await decide_action(
        body.state,
        body.actions,
        body.emotion,
        use_llm=body.use_llm,
    )
    return TurnDecideResponse(action=action, source=source)
