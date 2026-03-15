# services/agent_service/graph/emotion.py
"""Emotion detector (keyword-based). Output 7 classes for avatar mapping."""
from typing import Literal

from services.agent_service.graph.state import AgentState

EmotionLabel = Literal[
    "neutral", "happy", "sad", "angry", "anxious", "surprised", "crisis"
]


def _keyword_emotion(text: str) -> EmotionLabel:
    t = text.lower().strip()
    crisis = ["tự tử", "chết", "không muốn sống", "suicide", "kill myself", "end it all"]
    if any(k in t for k in crisis):
        return "crisis"
    sad = ["buồn", "khóc", "mệt", "chán", "thất vọng", "cô đơn", "sad", "lonely"]
    if any(k in t for k in sad):
        return "sad"
    angry = ["tức", "giận", "cay", "ghét", "angry", "mad", "chửi"]
    if any(k in t for k in angry):
        return "angry"
    anxious = ["lo", "sợ", "hồi hộp", "áp lực", "anxious", "worried", "thi"]
    if any(k in t for k in anxious):
        return "anxious"
    surprised = ["wow", "không ngờ", "bất ngờ", "thật à", "really", "omg"]
    if any(k in t for k in surprised):
        return "surprised"
    happy = ["vui", "vui quá", "happy", "yay", "haha", "cảm ơn", "thích"]
    if any(k in t for k in happy):
        return "happy"
    return "neutral"


def emotion_node(state: AgentState) -> dict:
    """Detect emotion from last user message; update state for avatar mapping."""
    if not state.get("messages"):
        return {"emotion": "neutral"}
    last = state["messages"][-1].content
    emotion = _keyword_emotion(last)
    return {"emotion": emotion}
