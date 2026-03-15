from __future__ import annotations

from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from config import settings
from graph.state import AgentState, EmotionLabel


VALID_EMOTIONS = {
	"neutral",
	"happy",
	"sad",
	"angry",
	"anxious",
	"surprised",
	"crisis",
}

DEFAULT_EMOTION: EmotionLabel = "neutral"

SYSTEM_PROMPT = (
	"You are an emotion classifier. "
	"Return exactly one label from this set and nothing else: "
	"neutral, happy, sad, angry, anxious, surprised, crisis"
)

_llm: ChatGroq | None = None
_llm_failed_once = False


def _keyword_emotion_fallback(text: str) -> EmotionLabel:
	normalized = text.lower().strip()

	if any(term in normalized for term in ["tự tử", "muốn chết", "không muốn sống", "kill myself", "suicide"]):
		return "crisis"
	if any(term in normalized for term in ["lo", "lo lắng", "sợ", "hoang mang", "anxious", "nervous"]):
		return "anxious"
	if any(term in normalized for term in ["tức", "cay", "điên", "ghét", "angry", "mad"]):
		return "angry"
	if any(term in normalized for term in ["buồn", "mệt", "chán", "cô đơn", "sad", "lonely"]):
		return "sad"
	if any(term in normalized for term in ["vui", "thích", "đỉnh", "awesome", "happy", "yay"]):
		return "happy"
	if any(term in normalized for term in ["what", "hả", "không ngờ", "surprised", "wow"]):
		return "surprised"
	return "neutral"


def _get_llm() -> ChatGroq | None:
	global _llm, _llm_failed_once
	if _llm is not None:
		return _llm
	if _llm_failed_once:
		return None

	try:
		_llm = ChatGroq(model=settings.GROQ_MODEL, api_key=settings.GROQ_API_KEY, temperature=0)
		return _llm
	except Exception:
		_llm_failed_once = True
		return None


def predict_emotion(text: str) -> EmotionLabel:
	llm = _get_llm()
	if llm is None:
		if settings.ENABLE_EMOTION_KEYWORD_FALLBACK:
			return _keyword_emotion_fallback(text)
		return DEFAULT_EMOTION

	try:
		response = llm.invoke([
			SystemMessage(content=SYSTEM_PROMPT),
			HumanMessage(content=text),
		])
		output = (response.content or "").strip().lower()
		for label in VALID_EMOTIONS:
			if label in output:
				return cast(EmotionLabel, label)
	except Exception:
		pass

	if settings.ENABLE_EMOTION_KEYWORD_FALLBACK:
		return _keyword_emotion_fallback(text)
	return DEFAULT_EMOTION


def emotion_node(state: AgentState) -> AgentState:
	message = state.get("message", "").strip()
	if not message:
		return {"emotion": DEFAULT_EMOTION}
	return {"emotion": predict_emotion(message)}
