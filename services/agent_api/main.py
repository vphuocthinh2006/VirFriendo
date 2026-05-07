from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from services.agent_service.claude_agent import run_claude_agent


class AgentMessage(BaseModel):
    role: str
    content: str


class AgentRunRequest(BaseModel):
    agent_id: str = "tuq27"
    messages: list[AgentMessage]


app = FastAPI(title="VirFriendo Agent Service", version="0.1.0")


def _to_lc_message(msg: AgentMessage):
    role = (msg.role or "").strip().lower()
    if role == "system":
        return SystemMessage(content=msg.content)
    if role == "assistant":
        return AIMessage(content=msg.content)
    return HumanMessage(content=msg.content)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agent"}


@app.post("/run")
async def run_agent(payload: AgentRunRequest):
    lc_messages = [_to_lc_message(m) for m in payload.messages]
    return await run_claude_agent(lc_messages, agent_id=payload.agent_id or "tuq27")
