from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from graph.pipeline import run_pipeline
from graph.state import AgentState


router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1)


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None
    conversation_history: list[ChatMessage] = Field(default_factory=list)


class AgentChatResponse(BaseModel):
    reply: str
    intent: str
    emotion: str
    avatar_action: str


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    state: AgentState = {
        "message": request.message,
        "conversation_id": request.conversation_id,
        "conversation_history": [item.model_dump() for item in request.conversation_history],
    }
    updates = run_pipeline(state)

    return AgentChatResponse(
        reply=updates.get("reply", f"[Agent Service] Bạn vừa nói: {request.message}"),
        intent=updates.get("intent", "greeting_chitchat"),
        emotion=updates.get("emotion", "neutral"),
        avatar_action=updates.get("avatar_action", "typing"),
    )