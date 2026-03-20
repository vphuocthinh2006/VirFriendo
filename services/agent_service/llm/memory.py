import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from services.agent_service.llm.client import generate_with_history


MEMORY_EXTRACT_SYSTEM = """You are a data extractor. You will be given a short Vietnamese chat history between a user and an assistant (tuq27).

Task: extract up to 3 stable, helpful long-term memories about the USER that could improve future replies.

Rules:
- ONLY extract things that are likely to remain true or be useful later (preferences, goals, recurring worries, relationships, boundaries).
- Do NOT extract transient details (today's weather, one-off plans) unless it is clearly a lasting preference/goal.
- Do NOT repeat the conversation; output only JSON.
- If there is nothing worth saving, output exactly: NONE

Output JSON format (a list):
[
  {"type": "preference|goal|fact|boundary|trigger_negative", "content": "<short Vietnamese sentence, 8-20 words>"},
  ...
]
"""


def _safe_json_loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        return None


async def extract_user_memories(history: List[BaseMessage]) -> List[Dict[str, str]]:
    """
    Return list of {type, content}. Empty list if NONE/unparseable.
    """
    reply = await generate_with_history(MEMORY_EXTRACT_SYSTEM, history)
    if not reply:
        return []
    if reply.strip().upper() == "NONE":
        return []
    data = _safe_json_loads(reply)
    if not isinstance(data, list):
        return []
    out: List[Dict[str, str]] = []
    for item in data[:3]:
        if not isinstance(item, dict):
            continue
        t = str(item.get("type") or "").strip()[:32]
        c = str(item.get("content") or "").strip()
        if not t or not c:
            continue
        out.append({"type": t, "content": c})
    return out

